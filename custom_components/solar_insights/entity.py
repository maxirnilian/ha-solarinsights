"""Shared entity helpers for Solar Insights."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util.unit_conversion import PowerConverter

from . import (
    DEFAULT_DIFFUSE_PERCENTAGE,
    DEFAULT_MEDIAN_WINDOW_MINUTES,
    DEFAULT_SUNSHINE_THRESHOLD,
    DOMAIN,
)

SUN_ENTITY = "sun.sun"
MEDIAN_RECOMPUTE_INTERVAL = timedelta(seconds=30)


def _get_config_value(config_entry: ConfigEntry, key: str, default: Any) -> Any:
    """Return a value from options with fallback to data."""
    if key in config_entry.options:
        return config_entry.options[key]
    return config_entry.data.get(key, default)


def time_weighted_median(
    samples: Sequence[tuple[float, float]],
    now: float,
    window_seconds: float,
) -> float | None:
    """Return the time-weighted median of (timestamp, value) samples.

    Each sample is held until the next sample (last value held until ``now``).
    Segments are clipped to ``[now - window_seconds, now]``.
    """
    if not samples or window_seconds <= 0:
        return None

    window_start = now - window_seconds
    segments: list[tuple[float, float]] = []

    for index, (timestamp, value) in enumerate(samples):
        end = samples[index + 1][0] if index + 1 < len(samples) else now
        clipped_start = max(timestamp, window_start)
        clipped_end = min(end, now)
        duration = clipped_end - clipped_start
        if duration > 0:
            segments.append((value, duration))

    if not segments:
        return None

    total = sum(duration for _value, duration in segments)
    if total <= 0:
        return None

    ordered = sorted(segments, key=lambda item: item[0])
    accumulated = 0.0
    halfway = total / 2.0
    for value, duration in ordered:
        accumulated += duration
        if accumulated >= halfway:
            return value
    return ordered[-1][0]


class BasePanelEntity:
    """Base class for solar panel entities."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self.hass = hass
        self.config_entry = config_entry
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
        self._sunshine_threshold = _get_config_value(
            config_entry, "sunshine_threshold", None
        )
        if self._sunshine_threshold is None:
            self._sunshine_threshold = _get_config_value(
                config_entry, "sunny_percentage", DEFAULT_SUNSHINE_THRESHOLD
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
        """Update the entity value."""

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
        """Return the current input power of the linked entity in watts.

        Converts from the linked sensor's unit of measurement (e.g. kW) to W.
        Sensors without a unit are treated as watts for backward compatibility.
        """
        if not self._input_power_entity:
            return None

        input_power_state = self.hass.states.get(self._input_power_entity)
        if not input_power_state or input_power_state.state in (
            "unknown",
            "unavailable",
        ):
            return None

        try:
            value = float(input_power_state.state)
        except (TypeError, ValueError):
            return None

        unit = input_power_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit is None or unit == UnitOfPower.WATT:
            return value

        try:
            return PowerConverter.convert(value, unit, UnitOfPower.WATT)
        except HomeAssistantError:
            return None

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

        return min(100.0, round((power / potential_power) * 100, 1))

    def is_sunny(self) -> bool | None:
        """Return True when incident-normalized irradiance meets the sunshine threshold."""
        sun_states = self._sun_states()
        if sun_states is not None and sun_states[0] <= 0:
            return False

        irradiance = self.incident_normalized_irradiance()
        if irradiance is None:
            return None
        return irradiance >= self._sunshine_threshold


class MedianWindowMixin:
    """Rolling time-weighted median of incident-normalized irradiance."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the median window buffer."""
        super().__init__(*args, **kwargs)
        self._median_window_minutes = int(
            _get_config_value(
                self.config_entry,
                "median_window_minutes",
                DEFAULT_MEDIAN_WINDOW_MINUTES,
            )
        )
        self._median_samples: deque[tuple[float, float]] = deque()

    @property
    def _median_window_seconds(self) -> float:
        """Return the configured median window in seconds."""
        return self._median_window_minutes * 60

    async def async_added_to_hass(self) -> None:
        """Recompute the median as the window slides, even without new samples."""
        await super().async_added_to_hass()

        @callback
        def handle_interval(_now) -> None:
            self._update_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(
                self.hass, handle_interval, MEDIAN_RECOMPUTE_INTERVAL
            )
        )

    def _prune_median_samples(self, now: float) -> None:
        """Drop samples that can no longer affect the current window."""
        window_start = now - self._median_window_seconds
        while (
            len(self._median_samples) >= 2
            and self._median_samples[1][0] <= window_start
        ):
            self._median_samples.popleft()

    def _record_median_sample(self, now: float, value: float | None) -> None:
        """Record a live sample, skipping consecutive duplicates."""
        self._prune_median_samples(now)
        if value is None:
            return
        if self._median_samples and self._median_samples[-1][1] == value:
            return
        self._median_samples.append((now, value))

    def _clear_median_samples(self) -> None:
        """Forget recorded samples (used at sunset)."""
        self._median_samples.clear()

    def median_incident_normalized_irradiance(self) -> float | None:
        """Return time-weighted median incident-normalized irradiance."""
        now = time.monotonic()
        sun_states = self._sun_states()
        if sun_states is not None and sun_states[0] <= 0:
            self._clear_median_samples()
            return None

        self._record_median_sample(now, self.incident_normalized_irradiance())
        median = time_weighted_median(
            self._median_samples, now, self._median_window_seconds
        )
        if median is None:
            return None
        return round(median, 1)

    def is_sunny_median(self) -> bool | None:
        """Return True when the median irradiance meets the sunshine threshold."""
        sun_states = self._sun_states()
        if sun_states is not None and sun_states[0] <= 0:
            self._clear_median_samples()
            return False

        irradiance = self.median_incident_normalized_irradiance()
        if irradiance is None:
            return None
        return irradiance >= self._sunshine_threshold
