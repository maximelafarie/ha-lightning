"""HA Lightning integration init

Sets up coordinator and registers services.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .coordinator import LightningCoordinator
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    conf = config.get(DOMAIN)
    if conf is None:
        # allow config via UI in the future
        _LOGGER.debug("ha_lightning not configured in YAML")
        return True

    feed_url = conf.get("feed_url")
    scan = int(conf.get("scan_interval", DEFAULT_SCAN_INTERVAL))

    coordinator = LightningCoordinator(hass, feed_url=feed_url, update_interval=timedelta(seconds=scan))
    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator
    hass.data[DOMAIN]["zones"] = conf.get("zones", [])

    # prime coordinator in background so platforms receive data shortly after HA boot
    hass.async_create_task(coordinator.async_refresh())

    # register services
    await services.async_setup_services(hass)

    # forward platform setup
    hass.async_create_task(discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {}, config))

    return True
