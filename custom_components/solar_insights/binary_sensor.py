"""Binary sensor platform for Solar Insights."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BasePanelEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Insights binary sensors from a config entry."""
    async_add_entities([SunnyBinarySensor(hass, config_entry)])


class SunnyBinarySensor(BasePanelEntity, BinarySensorEntity):
    """Binary sensor that is on when incident-normalized irradiance is sunny."""

    _attr_device_class = BinarySensorDeviceClass.LIGHT
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sunny binary sensor."""
        super().__init__(hass, config_entry)
        self._attr_translation_key = "sunny"
        self._attr_unique_id = f"{config_entry.entry_id}_sunny"
        self._attr_is_on = None

    def _update_state(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._attr_is_on = self.is_sunny()
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)
