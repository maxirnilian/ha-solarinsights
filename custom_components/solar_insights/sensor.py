"""Sensor platform for Solar Insights."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import DEFAULT_DIFFUSE_PERCENTAGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

SUN_ENTITY = "sun.sun"


def _get_config_value(config_entry: ConfigEntry, key: str, default: Any) -> Any:
    """Return a value from options with fallback to data."""
    if key in config_entry.options:
        return config_entry.options[key]
    return config_entry.data.get(key, default)


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
        ]
    )


class BasePanelSensor(SensorEntity):
    """Base class for solar panel sensors."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.config_entry = config_entry
        self._attr_native_value = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="Solar Insights",
        )

        self._panel_height = _get_config_value(config_entry, "panel_height", 0)
        self._panel_width = _get_config_value(config_entry, "panel_width", 0)
        self._panel_amount = _get_config_value(config_entry, "panel_amount", 0)
        self._panel_tilt = _get_config_value(config_entry, "panel_tilt", 0.0)
        self._panel_azimuth = _get_config_value(config_entry, "panel_azimuth", 180.0)
        self._efficiency_percentage = _get_config_value(
            config_entry, "efficiency_percentage", 15.0
        )
        self._max_power = _get_config_value(config_entry, "max_power", 0.0)
        self._diffuse_percentage = _get_config_value(
            config_entry, "diffuse_percentage", DEFAULT_DIFFUSE_PERCENTAGE
        )
        self._input_power_entity = _get_config_value(
            config_entry, "input_power_entity", None
        )

    async def async_added_to_hass(self) -> None:
        """Update when sun or input power changes."""
        await super().async_added_to_hass()

        tracked_entities = [SUN_ENTITY]
        if self._input_power_entity:
            tracked_entities.append(self._input_power_entity)

        @callback
        def handle_state_change(_event) -> None:
            self._update_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, tracked_entities, handle_state_change)
        )
        self._update_state()

    def _update_state(self) -> None:
        """Update the sensor value."""

    @property
    def panel_area_m2(self) -> float:
        """Return the total panel area in square meters."""
        return (
            (self._panel_height / 1000)
            * (self._panel_width / 1000)
            * self._panel_amount
        )

    @property
    def rated_power_w(self) -> float:
        """Return the total rated array power in watts."""
        return self._max_power * self._panel_amount

    def _sun_states(self) -> tuple[float, float] | None:
        """Return sun elevation and azimuth in degrees."""
        sun_state = self.hass.states.get(SUN_ENTITY)
        if not sun_state or sun_state.state in ("unknown", "unavailable"):
            return None

        elevation = sun_state.attributes.get("elevation")
        azimuth = sun_state.attributes.get("azimuth")
        if elevation is None or azimuth is None:
            return None

        return float(elevation), float(azimuth)

    def _raw_cos_theta(self) -> float | None:
        """Return unclamped cos of the angle between sun and panel normal."""
        sun_states = self._sun_states()
        if sun_states is None:
            return None

        sun_elevation, sun_azimuth = sun_states
        sun_elevation_rad = math.radians(sun_elevation)
        sun_azimuth_rad = math.radians(sun_azimuth)
        panel_tilt_rad = math.radians(self._panel_tilt)
        panel_azimuth_rad = math.radians(self._panel_azimuth)

        return (
            math.sin(sun_elevation_rad) * math.cos(panel_tilt_rad)
            + math.cos(sun_elevation_rad)
            * math.sin(panel_tilt_rad)
            * math.cos(sun_azimuth_rad - panel_azimuth_rad)
        )

    def cos_theta(self) -> float | None:
        """Return beam geometry factor, clamped to [0, 1] for irradiance math."""
        cos_theta = self._raw_cos_theta()
        if cos_theta is None:
            return None
        return max(0.0, min(1.0, cos_theta))

    def _aoi_normal_deg(self) -> float | None:
        """Return angle of incidence from the panel normal in degrees."""
        cos_theta = self._raw_cos_theta()
        if cos_theta is None:
            return None
        cos_theta = max(-1.0, min(1.0, cos_theta))
        return math.degrees(math.acos(cos_theta))

    def effective_geometry(self) -> float | None:
        """Return beam+diffuse geometry factor for incident-normalized irradiance.

        Uses front-side beam plus isotropic sky view, scaled so on-normal
        geometry stays 1. Softens near-zero / behind-panel beam while the sun
        is up. Returns None when the sun is below the horizon.
        """
        sun_states = self._sun_states()
        if sun_states is None:
            return None

        sun_elevation, _sun_azimuth = sun_states
        if sun_elevation <= 0:
            return None

        cos_theta = self._raw_cos_theta()
        if cos_theta is None:
            return None

        beam = max(0.0, cos_theta)
        f_sky = (1.0 + math.cos(math.radians(self._panel_tilt))) / 2.0
        k_d = self._diffuse_percentage / 100
        numerator = (1.0 - k_d) * beam + k_d * f_sky
        denominator = (1.0 - k_d) + k_d * f_sky
        if denominator <= 0:
            return None
        return numerator / denominator

    def incidence_angle(self) -> float | None:
        """Return surface incidence angle (90° − AOI from normal)."""
        sun_states = self._sun_states()
        if sun_states is None:
            return None

        sun_elevation, _sun_azimuth = sun_states
        if sun_elevation <= 0:
            return None

        aoi = self._aoi_normal_deg()
        if aoi is None:
            return None
        return round(90.0 - aoi, 2)

    def input_power(self) -> float | None:
        """Return the current input power of the linked entity."""
        if not self._input_power_entity:
            return None

        input_power_state = self.hass.states.get(self._input_power_entity)
        if not input_power_state or input_power_state.state in (
            "unknown",
            "unavailable",
        ):
            return None

        return float(input_power_state.state)

    def absolute_irradiance(self) -> float | None:
        """Return effective plane-of-array irradiance in W/m²."""
        power = self.input_power()
        if power is None:
            return None

        area = self.panel_area_m2
        efficiency = self._efficiency_percentage / 100
        if area <= 0 or efficiency <= 0:
            return None

        cos_theta_value = self.cos_theta()
        if cos_theta_value is None or cos_theta_value <= 0:
            return None

        return round(power / (area * efficiency), 1)

    def incident_normalized_irradiance(self) -> float | None:
        """Return irradiance normalized for incidence angle (ideal-beam equivalent)."""
        power = self.input_power()
        if power is None:
            return None

        geometry = self.effective_geometry()
        if geometry is None:
            return None

        potential_power = self.rated_power_w * geometry
        if potential_power <= 0:
            return None

        return round((power / potential_power) * 100, 1)


class IncidenceAngleSensor(BasePanelSensor):
    """Sensor for the solar incidence angle on the panel."""

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
