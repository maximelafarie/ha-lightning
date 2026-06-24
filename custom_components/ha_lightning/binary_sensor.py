"""Binary sensor for the configured single zone; switches 'on' when a strike occurs inside the zone."""
from __future__ import annotations

from math import radians, cos, sin, asin, sqrt
import logging
from typing import Any, Dict, List
from datetime import timedelta, datetime

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN, EVENT_ZONE_STRIKE

_LOGGER = logging.getLogger(__name__)


def _haversine_km(lat1, lon1, lat2, lon2):
    # haversine formula
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    coordinator = hass.data[DOMAIN]["coordinator"]
    zone = hass.data[DOMAIN].get("zone")

    if not zone:
        _LOGGER.debug("No zone configured for ha_lightning, not creating binary_sensor")
        return

    try:
        name = zone.get("name")
        lat = float(zone.get("latitude"))
        lon = float(zone.get("longitude"))
        radius = float(zone.get("radius_km", 10))
        cooldown = int(zone.get("cooldown_s", 300))
    except Exception as exc:
        _LOGGER.exception("Invalid zone config: %s", zone)
        return

    entity = LightningZoneBinarySensor(coordinator, name, lat, lon, radius, cooldown, hass)
    async_add_entities([entity])


class LightningZoneBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, name: str, lat: float, lon: float, radius_km: float, cooldown_s: int, hass: HomeAssistant):
        super().__init__(coordinator)
        self._name = f"Lightning Zone {name}"
        self._unique_id = f"ha_lightning_zone_{name}"
        self._lat = lat
        self._lon = lon
        self._radius = radius_km
        self._cooldown = timedelta(seconds=cooldown_s)
        self._last_strike_time = None
        self._is_on = False
        self._hass = hass

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        # If we had a recent strike within cooldown, report ON
        if self._last_strike_time and datetime.utcnow() - self._last_strike_time <= self._cooldown:
            return True
        return False

    @property
    def extra_state_attributes(self):
        return {"center": {"latitude": self._lat, "longitude": self._lon}, "radius_km": self._radius}

    async def async_added_to_hass(self):
        # subscribe to coordinator updates
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        await super().async_added_to_hass()

    @property
    def unique_id(self):
        return self._unique_id

    async def _handle_coordinator_update(self):
        data = self.coordinator.data or {}
        strikes = data.get("strikes", [])
        triggered = False
        for s in strikes:
            lat = float(s.get("latitude"))
            lon = float(s.get("longitude"))
            dist = _haversine_km(self._lat, self._lon, lat, lon)
            if dist <= self._radius:
                # convert time
                try:
                    st = datetime.fromisoformat(s.get("time"))
                except Exception:
                    st = datetime.utcnow()
                # only trigger if new
                if (self._last_strike_time is None) or (st > self._last_strike_time):
                    self._last_strike_time = st
                    triggered = True
                    # fire event
                    self._hass.bus.async_fire(EVENT_ZONE_STRIKE, {"zone": self._name, "strike": s})
                    _LOGGER.debug("Zone %s triggered by strike %s", self._name, s)
        # update state
        self.async_write_ha_state()
