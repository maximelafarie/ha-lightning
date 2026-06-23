"""DataUpdateCoordinator for fetching lightning strikes

Supports both HTTP JSON feeds and the lightningmaps.org websocket feed.
If feed_url starts with ws:// or wss:// the coordinator will connect to the
websocket and receive live strokes.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import ATTR_STRIKES

_LOGGER = logging.getLogger(__name__)


class LightningCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches lightning strikes from HTTP or websocket."""

    def __init__(self, hass: HomeAssistant, *, feed_url: Optional[str], update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="ha_lightning_coordinator",
            update_interval=update_interval,
        )
        self.feed_url = feed_url
        self.data: Dict[str, Any] = {ATTR_STRIKES: []}

        self._ws_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fallback polling update for HTTP feeds (kept for compatibility)."""
        if not self.feed_url or self.feed_url.startswith("ws"):
            # no-op when using websocket
            return self.data

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.feed_url, timeout=15) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Fetch failed: {resp.status}")
                    payload = await resp.json()
        except Exception as exc:
            raise UpdateFailed(exc)

        strikes: List[Dict[str, Any]] = []
        # try to normalize payload into list of strikes
        if isinstance(payload, dict) and "strikes" in payload:
            items = payload.get("strikes")
        else:
            items = payload

        for it in items or []:
            lat = it.get("lat") or it.get("latitude") or it.get("y")
            lon = it.get("lon") or it.get("longitude") or it.get("x")
            t = it.get("time") or it.get("timestamp") or it.get("t")
            if lat is None or lon is None:
                continue
            # normalize time
            ts = None
            try:
                if isinstance(t, (int, float)):
                    ts = datetime.fromtimestamp(int(t))
                elif isinstance(t, str):
                    try:
                        ts = datetime.fromisoformat(t)
                    except Exception:
                        from datetime import datetime as _dt

                        ts = _dt.strptime(t, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                ts = datetime.utcnow()

            strikes.append({"latitude": float(lat), "longitude": float(lon), "time": ts.isoformat(), "raw": it})

        # keep only recent strikes (last 30 minutes)
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        recent = [s for s in strikes if datetime.fromisoformat(s["time"]) >= cutoff]

        self.data = {ATTR_STRIKES: recent}
        return self.data

    async def async_start_ws(self, bbox: Optional[List[float]] = None, initial_payload: Optional[dict] = None) -> None:
        """Start websocket listener in background if feed_url is a ws:// URL.

        bbox: [max_lat, max_lon, min_lat, min_lon]
        initial_payload: optional dict to send after connection.
        """
        if not self.feed_url or not self.feed_url.startswith("ws"):
            return

        if self._ws_task and not self._ws_task.done():
            return

        self._running = True
        self._ws_task = asyncio.create_task(self._run_ws(bbox=bbox, initial_payload=initial_payload))

    async def async_stop_ws(self) -> None:
        """Stop the websocket listener."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        if self._session:
            await self._session.close()
            self._session = None

    async def _run_ws(self, bbox: Optional[List[float]] = None, initial_payload: Optional[dict] = None) -> None:
        """Background task connecting to websocket and processing messages."""
        url = self.feed_url
        retry_delay = 5
        # maintain a dict of strikes keyed by id to deduplicate
        strikes_by_id: Dict[int, Dict[str, Any]] = {}

        while self._running:
            try:
                self._session = aiohttp.ClientSession()
                async with self._session.ws_connect(url, heartbeat=30) as ws:
                    _LOGGER.info("Connected to lightning websocket %s", url)

                    # send initial payload: either provided or the lightningmaps.org-shaped default
                    if initial_payload is None:
                        # default payload closely matching lightningmaps.org examples
                        # p: [max_lat, max_lon, min_lat, min_lon]
                        payload = {
                            "v": 24,
                            "i": {},
                            "s": False,
                            "x": 0,
                            "w": 0,
                            "tx": 0,
                            "tw": 1,
                            "a": 4,
                            "z": 10,
                            "b": True,
                            # h contains center/zoom metadata; will be filled if center available
                            "h": "#m=oss;t=3;s=0;o=1;b=0.00;ts=0;y=0;x=0;z=10;d=2;dl=2;dc=0;",
                            "l": 1,
                            "t": 1,
                            "from_lightningmaps_org": True,
                            "r": "A",
                        }
                        if bbox:
                            # ensure order [max_lat, max_lon, min_lat, min_lon]
                            payload["p"] = bbox
                            # compute rough center for h field
                            try:
                                max_lat, max_lon, min_lat, min_lon = bbox
                                center_lat = (max_lat + min_lat) / 2.0
                                center_lon = (max_lon + min_lon) / 2.0
                                payload["h"] = f"#m=oss;t=3;s=0;o=1;b=0.00;ts=0;y={center_lat:.4f};x={center_lon:.4f};z={payload.get('z',10)};d=2;dl=2;dc=0;"
                            except Exception:
                                pass
                        else:
                            # example default bbox used by many clients
                            payload["p"] = [46.2, 11.9, 45.3, 9.5]
                    else:
                        payload = initial_payload

                    try:
                        await ws.send_str(json.dumps(payload))
                    except Exception:
                        _LOGGER.debug("Failed to send initial subscription payload")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except Exception:
                                continue

                            # heartbeat or clock messages might be simple {"time":...}
                            if "strokes" in data and isinstance(data["strokes"], list):
                                for s in data["strokes"]:
                                    try:
                                        sid = int(s.get("id") or 0)
                                        lat = float(s.get("lat") or s.get("latitude"))
                                        lon = float(s.get("lon") or s.get("longitude"))
                                        ts_ms = int(s.get("time") or s.get("t") or 0)
                                        # lightningmaps uses ms timestamps
                                        if ts_ms > 1e11:  # ms
                                            ts = datetime.fromtimestamp(ts_ms / 1000.0)
                                        else:
                                            ts = datetime.fromtimestamp(int(ts_ms))
                                        entry = {"latitude": lat, "longitude": lon, "time": ts.isoformat(), "raw": s}
                                        if sid:
                                            strikes_by_id[sid] = entry
                                        else:
                                            # fallback: use timestamp-based key
                                            strikes_by_id[hash(ts_ms) % (10 ** 9)] = entry
                                    except Exception:
                                        continue

                                # prune old
                                cutoff = datetime.utcnow() - timedelta(minutes=30)
                                recent = [v for v in strikes_by_id.values() if datetime.fromisoformat(v["time"]) >= cutoff]
                                self.data = {ATTR_STRIKES: recent}
                                # notify listeners
                                self.async_set_updated_data(self.data)

                            # ignore other messages
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.warning("Websocket error: %s", msg)
                            break

            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.warning("Websocket connection failed: %s", exc)
                await asyncio.sleep(retry_delay)
                retry_delay = min(60, retry_delay * 2)
                continue
            finally:
                if self._session:
                    await self._session.close()
                    self._session = None

        _LOGGER.info("Websocket listener stopped")
