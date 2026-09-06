"""Config flow for Solar Panel Insights."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import DEFAULT_DIFFUSE_PERCENTAGE, DOMAIN


def _get_config_value(config_entry: config_entries.ConfigEntry, key: str, default):
    """Return a value from options with fallback to data."""
    if key in config_entry.options:
        return config_entry.options[key]
    return config_entry.data.get(key, default)


class SolarPanelInsightsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Panel Insights."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Solar Panel Insights", data=user_input)

        schema = vol.Schema(
            {
                vol.Required("panel_height"): vol.Coerce(int),
                vol.Required("panel_width"): vol.Coerce(int),
                vol.Required("panel_amount"): vol.Coerce(int),
                vol.Required(
                    "panel_tilt",
                    default=0,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.Required(
                    "panel_azimuth",
                    default=180,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.Required(
                    "efficiency_percentage",
                    default=15.0,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required("max_power"): vol.Coerce(float),
                vol.Required(
                    "diffuse_percentage",
                    default=DEFAULT_DIFFUSE_PERCENTAGE,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required("input_power_entity"): selector.selector(
                    {
                        "entity": {
                            "domain": "sensor",
                            "device_class": "power",
                        }
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SolarPanelInsightsOptionsFlowHandler()


class SolarPanelInsightsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Solar Panel Insights options."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    "panel_height",
                    default=_get_config_value(self.config_entry, "panel_height", 0),
                ): vol.Coerce(int),
                vol.Required(
                    "panel_width",
                    default=_get_config_value(self.config_entry, "panel_width", 0),
                ): vol.Coerce(int),
                vol.Required(
                    "panel_amount",
                    default=_get_config_value(self.config_entry, "panel_amount", 0),
                ): vol.Coerce(int),
                vol.Required(
                    "panel_tilt",
                    default=_get_config_value(self.config_entry, "panel_tilt", 0),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.Required(
                    "panel_azimuth",
                    default=_get_config_value(self.config_entry, "panel_azimuth", 180),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.Required(
                    "efficiency_percentage",
                    default=_get_config_value(
                        self.config_entry, "efficiency_percentage", 15.0
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    "max_power",
                    default=_get_config_value(self.config_entry, "max_power", 0),
                ): vol.Coerce(float),
                vol.Required(
                    "diffuse_percentage",
                    default=_get_config_value(
                        self.config_entry,
                        "diffuse_percentage",
                        DEFAULT_DIFFUSE_PERCENTAGE,
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    "input_power_entity",
                    default=_get_config_value(
                        self.config_entry, "input_power_entity", None
                    ),
                ): selector.selector(
                    {
                        "entity": {
                            "domain": "sensor",
                            "device_class": "power",
                        }
                    }
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)
