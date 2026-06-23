"""DataUpdateCoordinator for fetching lightning strikes"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import ATTR_STRIKES

_LOGGER = logging.getLogger(__name__)


class LightningCoordinator(DataUpdateCoordinator):
    """Coordinator that polls a JSON feed of recent lightning strikes.

    The expected feed is a JSON list of objects with at least:
      - lat or latitude
      - lon or longitude
      - time (unix timestamp seconds or ISO string)

    If the user's feed differs, the README explains how to provide a proxy.
    """

    def __init__(self, hass: HomeAssistant, *, feed_url: Optional[str], update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="ha_lightning_coordinator",
            update_interval=update_interval,
        )
        self.feed_url = feed_url
        self.data: Dict[str, Any] = {ATTR_STRIKES: []}

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self.feed_url:
            _LOGGER.debug("No feed_url configured for ha_lightning")
            return {ATTR_STRIKES: []}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.feed_url, timeout=15) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Fetch failed: {resp.status}")
                    payload = await resp.json()
        except Exception as exc:
            raise UpdateFailed(exc)

        strikes = []
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
                        ts = datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                ts = datetime.utcnow()

            strikes.append({"latitude": float(lat), "longitude": float(lon), "time": ts.isoformat(), "raw": it})

        # keep only recent strikes (last 30 minutes)
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        recent = [s for s in strikes if datetime.fromisoformat(s["time"]) >= cutoff]

        self.data = {ATTR_STRIKES: recent}
        return self.data
