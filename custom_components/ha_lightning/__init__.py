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

    # try to normalize zones from YAML
    zones = conf.get("zones", [])
    hass.data[DOMAIN]["zones"] = zones

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

    data = entry.data
    feed_url = data.get("feed_url")
    scan = int(data.get("scan_interval", DEFAULT_SCAN_INTERVAL))

    # parse zones if provided
    zones = data.get("zones", [])
    if isinstance(zones, str):
        try:
            zones = json.loads(zones)
        except Exception:
            _LOGGER.warning("Could not parse zones for entry %s", entry.entry_id)
            zones = []

    coordinator = LightningCoordinator(hass, feed_url=feed_url, update_interval=timedelta(seconds=scan))

    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator
    hass.data[DOMAIN]["zones"] = zones
    hass.data[DOMAIN]["entry_id"] = entry.entry_id

    # register services (idempotent)
    await services.async_setup_services(hass)

    # forward platforms
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    await hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")

    # prime coordinator
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
