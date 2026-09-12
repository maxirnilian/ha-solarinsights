"""The Solar Insights integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "solar_insights"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
# Diffuse share of clear-sky potential so incident-normalized irradiance stays
# bounded when beam geometry (cos θ) approaches zero at sunrise/sunset.
DEFAULT_DIFFUSE_PERCENTAGE = 11.5
DEFAULT_SUNSHINE_THRESHOLD = 40.0
DEFAULT_MEDIAN_WINDOW_MINUTES = 3

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Insights from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
