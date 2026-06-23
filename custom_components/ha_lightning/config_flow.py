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
                    vol.Optional("zones", default=""): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        # validate feed_url
        try:
            await async_validate_feed(self.hass, user_input.get("feed_url", ""))
        except ValueError as exc:
            errors["feed_url"] = str(exc)

        # validate zones JSON if provided
        zones_raw = user_input.get("zones", "")
        zones = []
        if zones_raw:
            try:
                parsed = json.loads(zones_raw)
                if not isinstance(parsed, list):
                    raise ValueError("zones must be a JSON list")
                zones = parsed
            except Exception:
                errors["zones"] = "invalid_json"

        if errors:
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=user_input.get("feed_url")): str,
                    vol.Optional("scan_interval", default=user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                    vol.Optional("zones", default=zones_raw): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        data = {
            "feed_url": user_input.get("feed_url"),
            "scan_interval": int(user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
            "zones": zones,
        }

        return self.async_create_entry(title="HA Lightning", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Manage options for the integration (zones editor)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        # work copy of zones
        self._zones = list(self.config_entry.options.get("zones", self.config_entry.data.get("zones", [])))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Initial step: edit basic settings or manage zones."""
        if user_input is None:
            data = self.config_entry.options or self.config_entry.data
            zones = self._zones
            zones_text = json.dumps(zones, indent=2) if zones else ""
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=data.get("feed_url", "")): str,
                    vol.Optional("scan_interval", default=data.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                    vol.Optional("manage_zones", default=False): bool,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        # if user requested to manage zones, go to zones step
        if user_input.get("manage_zones"):
            return await self.async_step_zones()

        # otherwise validate feed and save options
        errors = {}
        try:
            await async_validate_feed(self.hass, user_input.get("feed_url", ""))
        except ValueError as exc:
            errors["feed_url"] = str(exc)

        if errors:
            data = self.config_entry.options or self.config_entry.data
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=user_input.get("feed_url", data.get("feed_url", ""))): str,
                    vol.Optional("scan_interval", default=user_input.get("scan_interval", data.get("scan_interval", DEFAULT_SCAN_INTERVAL))): int,
                    vol.Optional("manage_zones", default=False): bool,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

        options = {
            "feed_url": user_input.get("feed_url"),
            "scan_interval": int(user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
            "zones": self._zones,
        }
        return self.async_create_entry(title="", data=options)

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage zones list: add/edit/remove."""
        if user_input is None:
            # build choices
            choices = [("add", "Add zone")]
            for idx, z in enumerate(self._zones):
                name = z.get("name") or f"Zone {idx+1}"
                choices.append((f"edit_{idx}", f"Edit: {name}"))
                choices.append((f"remove_{idx}", f"Remove: {name}"))
            choices.append(("done", "Done"))
            schema = vol.Schema({vol.Required("action", default="done"): vol.In([c[0] for c in choices])})
            # present a friendly label list via description_placeholders
            placeholders = {k: v for k, v in choices}
            return self.async_show_form(step_id="zones", data_schema=schema)

        action = user_input.get("action")
        if action == "add":
            return await self.async_step_zone_edit()
        if action and action.startswith("edit_"):
            idx = int(action.split("_")[1])
            return await self.async_step_zone_edit({"index": idx})
        if action and action.startswith("remove_"):
            idx = int(action.split("_")[1])
            try:
                self._zones.pop(idx)
            except Exception:
                pass
            return await self.async_step_zones()
        # done -> back to init
        return await self.async_step_init({"feed_url": self.config_entry.options.get("feed_url", self.config_entry.data.get("feed_url")), "scan_interval": self.config_entry.options.get("scan_interval", self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)), "manage_zones": False})

    async def async_step_zone_edit(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add or edit a single zone."""
        index = None
        if user_input and isinstance(user_input.get("index"), int):
            index = user_input.get("index")
        if user_input is None or (user_input is not None and "name" not in user_input):
            # initial form
            if index is not None and 0 <= index < len(self._zones):
                z = self._zones[index]
                defaults = {
                    "name": z.get("name", ""),
                    "latitude": z.get("latitude", ""),
                    "longitude": z.get("longitude", ""),
                    "radius_km": z.get("radius_km", 10),
                    "cooldown_s": z.get("cooldown_s", 300),
                }
            else:
                defaults = {"name": "", "latitude": "", "longitude": "", "radius_km": 10, "cooldown_s": 300}
            schema = vol.Schema(
                {
                    vol.Required("name", default=defaults["name"]): str,
                    vol.Required("latitude", default=defaults["latitude"]): str,
                    vol.Required("longitude", default=defaults["longitude"]): str,
                    vol.Optional("radius_km", default=defaults["radius_km"]): vol.Coerce(float),
                    vol.Optional("cooldown_s", default=defaults["cooldown_s"]): int,
                }
            )
            return self.async_show_form(step_id="zone_edit", data_schema=schema)

        # process submission
        try:
            z = {
                "name": str(user_input.get("name")),
                "latitude": float(user_input.get("latitude")),
                "longitude": float(user_input.get("longitude")),
                "radius_km": float(user_input.get("radius_km", 10)),
                "cooldown_s": int(user_input.get("cooldown_s", 300)),
            }
        except Exception:
            return await self.async_step_zone_edit(user_input)

        if index is not None and 0 <= index < len(self._zones):
            self._zones[index] = z
        else:
            self._zones.append(z)

        return await self.async_step_zones()
