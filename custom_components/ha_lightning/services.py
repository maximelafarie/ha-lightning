"""Optional services for ha_lightning (zone management)

This minimal implementation exposes two services (YAML-only integration):
 - ha_lightning.add_zone
 - ha_lightning.remove_zone

Zones are stored in hass.data[DOMAIN]['zones'] and are not persisted; users should manage zones in configuration.yaml for persistence.
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
