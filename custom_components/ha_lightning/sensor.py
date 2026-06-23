"""Sensor entity exposing recent lightning strikes as an attribute"""
from __future__ import annotations

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.const import TEMP_C

from .coordinator import LightningCoordinator
from .const import DOMAIN, ATTR_STRIKES


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    coordinator: LightningCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([LightningSensor(coordinator)], True)


class LightningSensor(CoordinatorEntity, Entity):
    """Sensor that holds recent strikes in attributes"""

    def __init__(self, coordinator: LightningCoordinator):
        super().__init__(coordinator)
        self._attr_name = "HA Lightning Strikes"
        self._attr_unique_id = "ha_lightning_strikes"
        self._attr_state = "idle"

    @property
    def state(self):
        return self._attr_state

    @property
    def extra_state_attributes(self):
        return {ATTR_STRIKES: self.coordinator.data.get(ATTR_STRIKES, [])}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
