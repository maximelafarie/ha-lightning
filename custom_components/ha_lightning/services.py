"""Optional services for ha_lightning (single-zone runtime management)

This implementation exposes two runtime services:
 - ha_lightning.set_zone (set a single zone dict)
 - ha_lightning.clear_zone (clear the runtime zone)

These services modify the in-memory zone (hass.data[DOMAIN]['zone']) and are not persisted. Use the UI Options flow to save configuration persistently.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN


async def async_setup_services(hass: HomeAssistant) -> None:
    async def set_zone(call: ServiceCall) -> None:
        data = call.data
        # set single zone in memory (not persisted)
        hass.data[DOMAIN]["zone"] = data

    async def clear_zone(call: ServiceCall) -> None:
        hass.data[DOMAIN]["zone"] = None

    hass.services.async_register(DOMAIN, "set_zone", set_zone)
    hass.services.async_register(DOMAIN, "clear_zone", clear_zone)
