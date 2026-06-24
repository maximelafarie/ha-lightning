from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_validate_feed(hass: HomeAssistant, url: str) -> None:
    """Validate the provided feed URL by performing a simple GET and checking JSON shape."""
    if not url:
        raise ValueError("empty")

    # websocket URLs are accepted without probing
    if url.startswith(("ws://", "wss://")):
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    raise ValueError(f"http_{resp.status}")
                try:
                    payload = await resp.json()
                except Exception:
                    raise ValueError("not_json")
    except Exception as exc:
        _LOGGER.debug("Feed validation failed: %s", exc)
        raise ValueError("unreachable")

    # basic structural checks
    items = None
    if isinstance(payload, dict) and "strikes" in payload:
        items = payload.get("strikes")
    elif isinstance(payload, list):
        items = payload
    else:
        # try minimal heuristic
        if isinstance(payload, dict):
            items = [payload]

    if not items:
        raise ValueError("no_items")

    # check first item has lat/lon/time
    first = items[0]
    if not isinstance(first, dict):
        raise ValueError("invalid_item")
    if not any(k in first for k in ("lat", "latitude", "y")):
        raise ValueError("no_lat")
    if not any(k in first for k in ("lon", "longitude", "x")):
        raise ValueError("no_lon")
    if not any(k in first for k in ("time", "timestamp", "t")):
        raise ValueError("no_time")


class HaLightningConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Lightning."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=""): str,
                    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
                    # single zone fields
                    vol.Optional("zone_name", default=""): str,
                    vol.Optional("latitude", default=""): str,
                    vol.Optional("longitude", default=""): str,
                    vol.Optional("radius_km", default=10): vol.Coerce(float),
                    vol.Optional("cooldown_s", default=300): int,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        # validate feed_url
        try:
            await async_validate_feed(self.hass, user_input.get("feed_url", ""))
        except ValueError as exc:
            errors["feed_url"] = str(exc)

        # assemble single zone if provided
        zone = None
        if user_input.get("latitude") and user_input.get("longitude"):
            try:
                zone = {
                    "name": user_input.get("zone_name") or "Home",
                    "latitude": float(user_input.get("latitude")),
                    "longitude": float(user_input.get("longitude")),
                    "radius_km": float(user_input.get("radius_km", 10)),
                    "cooldown_s": int(user_input.get("cooldown_s", 300)),
                }
            except Exception:
                errors["latitude"] = "invalid"
                errors["longitude"] = "invalid"

        if errors:
            # re-present same form with errors
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=user_input.get("feed_url")): str,
                    vol.Optional("scan_interval", default=user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                    vol.Optional("zone_name", default=user_input.get("zone_name", "")): str,
                    vol.Optional("latitude", default=user_input.get("latitude", "")): str,
                    vol.Optional("longitude", default=user_input.get("longitude", "")): str,
                    vol.Optional("radius_km", default=user_input.get("radius_km", 10)): vol.Coerce(float),
                    vol.Optional("cooldown_s", default=user_input.get("cooldown_s", 300)): int,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        data = {
            "feed_url": user_input.get("feed_url"),
            "scan_interval": int(user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
            "zone": zone,
        }

        return self.async_create_entry(title="HA Lightning", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Manage options for the integration (single-zone editor)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        # work copy of single zone
        opt_zone = self.config_entry.options.get("zone") if isinstance(self.config_entry.options.get("zone"), dict) else None
        data_zone = self.config_entry.data.get("zone") if isinstance(self.config_entry.data.get("zone"), dict) else None
        # fallback for legacy 'zones' list
        legacy_zones = self.config_entry.options.get("zones") or self.config_entry.data.get("zones")
        if isinstance(legacy_zones, list) and len(legacy_zones) > 0:
            legacy_zone = legacy_zones[0]
        else:
            legacy_zone = None
        self._zone = opt_zone or data_zone or legacy_zone

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Initial step: edit basic settings or manage zones."""
        if user_input is None:
            data = self.config_entry.options or self.config_entry.data
            z = self._zone or {}
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=data.get("feed_url", "")): str,
                    vol.Optional("scan_interval", default=data.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                    vol.Optional("zone_name", default=z.get("name", "")): str,
                    vol.Optional("latitude", default=z.get("latitude", "")): str,
                    vol.Optional("longitude", default=z.get("longitude", "")): str,
                    vol.Optional("radius_km", default=z.get("radius_km", 10)): vol.Coerce(float),
                    vol.Optional("cooldown_s", default=z.get("cooldown_s", 300)): int,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        # validate feed and assemble zone
        errors = {}
        try:
            await async_validate_feed(self.hass, user_input.get("feed_url", ""))
        except ValueError as exc:
            errors["feed_url"] = str(exc)

        zone = None
        if user_input.get("latitude") and user_input.get("longitude"):
            try:
                zone = {
                    "name": user_input.get("zone_name") or "Home",
                    "latitude": float(user_input.get("latitude")),
                    "longitude": float(user_input.get("longitude")),
                    "radius_km": float(user_input.get("radius_km", 10)),
                    "cooldown_s": int(user_input.get("cooldown_s", 300)),
                }
            except Exception:
                errors["latitude"] = "invalid"
                errors["longitude"] = "invalid"

        if errors:
            data = self.config_entry.options or self.config_entry.data
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=user_input.get("feed_url", data.get("feed_url", ""))): str,
                    vol.Optional("scan_interval", default=user_input.get("scan_interval", data.get("scan_interval", DEFAULT_SCAN_INTERVAL))): int,
                    vol.Optional("zone_name", default=user_input.get("zone_name", "")): str,
                    vol.Optional("latitude", default=user_input.get("latitude", "")): str,
                    vol.Optional("longitude", default=user_input.get("longitude", "")): str,
                    vol.Optional("radius_km", default=user_input.get("radius_km", 10)): vol.Coerce(float),
                    vol.Optional("cooldown_s", default=user_input.get("cooldown_s", 300)): int,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

        options = {
            "feed_url": user_input.get("feed_url"),
            "scan_interval": int(user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
            "zone": zone,
        }
        return self.async_create_entry(title="", data=options)

