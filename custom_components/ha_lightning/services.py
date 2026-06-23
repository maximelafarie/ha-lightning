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
    async def add_zone(call: ServiceCall) -> None:
        data = call.data
        zones = hass.data[DOMAIN].setdefault("zones", [])
        zones.append(data)

    async def remove_zone(call: ServiceCall) -> None:
        name = call.data.get("name")
        zones = hass.data[DOMAIN].get("zones", [])
        hass.data[DOMAIN]["zones"] = [z for z in zones if z.get("name") != name]

    hass.services.async_register(DOMAIN, "add_zone", add_zone)
    hass.services.async_register(DOMAIN, "remove_zone", remove_zone)
