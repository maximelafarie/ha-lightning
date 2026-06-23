from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HaLightningConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Lightning."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=""): str,
                    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
                    vol.Optional("zones", default=""): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        # validate zones if provided (expect JSON list)
        zones_raw = user_input.get("zones", "")
        zones = []
        if zones_raw:
            try:
                parsed = json.loads(zones_raw)
                if not isinstance(parsed, list):
                    raise ValueError("zones must be a JSON list of zone objects")
                zones = parsed
            except Exception as exc:
                _LOGGER.exception("Invalid zones format in config flow: %s", exc)
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("feed_url", default=user_input.get("feed_url")): str,
                            vol.Optional("scan_interval", default=user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                            vol.Optional("zones", default=zones_raw): str,
                        }
                    ),
                    errors={"zones": "invalid_json"},
                )

        # create entry
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


from homeassistant import config_entries as _ce  # type: ignore
from homeassistant.core import callback


class OptionsFlowHandler(_ce.OptionsFlow):
    def __init__(self, config_entry: _ce.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            # present current options/data
            data = self.config_entry.data
            zones = data.get("zones", [])
            zones_text = json.dumps(zones) if zones else ""
            schema = vol.Schema(
                {
                    vol.Required("feed_url", default=data.get("feed_url", "")): str,
                    vol.Optional("scan_interval", default=data.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                    vol.Optional("zones", default=zones_text): str,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        # parse zones
        zones_raw = user_input.get("zones", "")
        zones = []
        if zones_raw:
            try:
                parsed = json.loads(zones_raw)
                if isinstance(parsed, list):
                    zones = parsed
            except Exception:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(
                        {
                            vol.Required("feed_url", default=user_input.get("feed_url")): str,
                            vol.Optional("scan_interval", default=user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                            vol.Optional("zones", default=zones_raw): str,
                        }
                    ),
                    errors={"zones": "invalid_json"},
                )

        options = {"feed_url": user_input.get("feed_url"), "scan_interval": int(user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)), "zones": zones}
        return self.async_create_entry(title="", data=options)
