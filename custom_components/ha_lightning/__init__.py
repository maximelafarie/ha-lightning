"""HA Lightning integration init

Sets up coordinator and registers services.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.config_entries import ConfigEntry

from .coordinator import LightningCoordinator
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (legacy)."""
    conf = config.get(DOMAIN)
    if conf is None:
        # allow config via UI in the future
        _LOGGER.debug("ha_lightning not configured in YAML")
        return True

    feed_url = conf.get("feed_url")
    scan = int(conf.get("scan_interval", DEFAULT_SCAN_INTERVAL))

    coordinator = LightningCoordinator(hass, feed_url=feed_url, update_interval=timedelta(seconds=scan))
    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator

    # try to normalize zone from YAML (legacy supports 'zones' list; pick first)
    zone = conf.get("zone")
    if zone is None:
        legacy = conf.get("zones", [])
        if isinstance(legacy, list) and len(legacy) > 0:
            zone = legacy[0]
    hass.data[DOMAIN]["zone"] = zone

    # register services
    await services.async_setup_services(hass)

    # forward platform setup (legacy)
    hass.async_create_task(discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {}, config))

    # prime coordinator
    hass.async_create_task(coordinator.async_refresh())

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry (UI)."""

    # prefer options over data so OptionsFlow updates take effect
    # prefer options over data so OptionsFlow updates take effect
    data = entry.options or entry.data
    feed_url = data.get("feed_url")
    scan = int(data.get("scan_interval", DEFAULT_SCAN_INTERVAL))

    # parse single zone if provided
    zone = data.get("zone")
    if isinstance(zone, str):
        try:
            zone = json.loads(zone)
        except Exception:
            _LOGGER.warning("Could not parse zone for entry %s", entry.entry_id)
            zone = None
    # legacy support: if 'zones' list exists, use first
    legacy = data.get("zones")
    if zone is None and isinstance(legacy, list) and len(legacy) > 0:
        zone = legacy[0]

    coordinator = LightningCoordinator(hass, feed_url=feed_url, update_interval=timedelta(seconds=scan))

    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator
    hass.data[DOMAIN]["zone"] = zone
    hass.data[DOMAIN]["entry_id"] = entry.entry_id

    # register services (idempotent)
    await services.async_setup_services(hass)

    # forward platforms
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    await hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")

    # if websocket URL requested, start ws listener using zones to compute bbox
    if feed_url and str(feed_url).startswith(("ws://", "wss://")):
        # compute bbox [max_lat, max_lon, min_lat, min_lon] from zones if available
        bbox = None
        try:
            zones = zones or []
            if zones:
                lats = []
                lons = []
                for z in zones:
                    try:
                        lat = float(z.get("latitude"))
                        lon = float(z.get("longitude"))
                        radius_km = float(z.get("radius_km", 10))
                    except Exception:
                        continue
                    # approximate degree extents
                    lat_deg = radius_km / 111.0
                    lon_deg = radius_km / max(0.1, (111.320 * abs(lat) / 45 + 1))
                    lats.extend([lat + lat_deg, lat - lat_deg])
                    lons.extend([lon + lon_deg, lon - lon_deg])
                if lats and lons:
                    bbox = [max(lats), max(lons), min(lats), min(lons)]
        except Exception:
            bbox = None
        # start websocket background task
        hass.async_create_task(coordinator.async_start_ws(bbox=bbox))
    else:
        # prime coordinator polling for HTTP feeds
        hass.async_create_task(coordinator.async_refresh())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    unloaded_bs = await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")

    # clean up data
    hass.data.get(DOMAIN, {}).pop("coordinator", None)
    hass.data.get(DOMAIN, {}).pop("zones", None)
    hass.data.get(DOMAIN, {}).pop("entry_id", None)

    return bool(unloaded and unloaded_bs)
