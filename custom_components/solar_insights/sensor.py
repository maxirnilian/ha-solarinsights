"""Sensor platform for Solar Insights."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BasePanelEntity, MedianWindowMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Insights sensors from a config entry."""
    async_add_entities(
        [
            IncidenceAngleSensor(hass, config_entry),
            AbsoluteIrradianceSensor(hass, config_entry),
            IncidentNormalizedIrradianceSensor(hass, config_entry),
            IncidentNormalizedIrradianceMedianSensor(hass, config_entry),
        ]
    )


class BasePanelSensor(BasePanelEntity, SensorEntity):
    """Base class for solar panel sensors."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(hass, config_entry)
        self._attr_native_value = None


class IncidenceAngleSensor(BasePanelSensor):
    """Sensor for the solar incidence angle on the panel."""

    _attr_icon = "mdi:sun-angle"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the incidence angle sensor."""
        super().__init__(hass, config_entry)
        self._attr_translation_key = "incidence_angle"
        self._attr_unique_id = f"{config_entry.entry_id}_incidence_angle"
        self._attr_native_unit_of_measurement = "°"

    def _update_state(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = self.incidence_angle()
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)


class AbsoluteIrradianceSensor(BasePanelSensor):
    """Sensor for absolute solar irradiation on the panel."""

    _attr_icon = "mdi:sun-wireless-outline"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the absolute irradiance sensor."""
        super().__init__(hass, config_entry)
        self._attr_translation_key = "absolute_irradiation"
        self._attr_unique_id = f"{config_entry.entry_id}_absolute_irradiation"
        self._attr_device_class = SensorDeviceClass.IRRADIANCE
        self._attr_native_unit_of_measurement = "W/m²"

    def _update_state(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = self.absolute_irradiance()
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)


class IncidentNormalizedIrradianceSensor(BasePanelSensor):
    """Sensor for incidence-angle-normalized irradiance (ideal-beam equivalent)."""

    _attr_icon = "mdi:sun-wireless-outline"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the incident-normalized irradiance sensor."""
        super().__init__(hass, config_entry)
        self._attr_translation_key = "incident_normalized_irradiance"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_incident_normalized_irradiance"
        )
        self._attr_native_unit_of_measurement = "%"

    def _update_state(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = self.incident_normalized_irradiance()
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)


class IncidentNormalizedIrradianceMedianSensor(MedianWindowMixin, BasePanelSensor):
    """Sensor for the time-weighted median of incident-normalized irradiance."""

    _attr_icon = "mdi:sun-wireless-outline"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the median incident-normalized irradiance sensor."""
        super().__init__(hass, config_entry)
        self._attr_translation_key = "incident_normalized_irradiance_median"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_incident_normalized_irradiance_median"
        )
        self._attr_native_unit_of_measurement = "%"

    def _update_state(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._attr_native_value = self.median_incident_normalized_irradiance()
        except Exception as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)
