<img src="custom_components/solar_insights/brand/icon.png" alt="Solar Insights" width="40" height="40">

# Solar Insights

Home Assistant custom integration that calculates detailed solar panel metrics using panel geometry, the built-in [sun](https://www.home-assistant.io/integrations/sun/) integration, and a linked power sensor.

## Features

- Calculates the angle between incoming sunlight and your panel surface
- Estimates absolute plane-of-array irradiation from measured power
- Estimates incident-normalized irradiance (ideal-beam equivalent) using beam plus isotropic sky view
- Uses elevation and azimuth from the built-in `sun.sun` entity
- Configurable panel dimensions, tilt, azimuth, efficiency, and linked power sensor

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations**
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/maxirnilian/ha-solarinsights` with category **Integration**
4. Search for **Solar Insights**, install, and restart Home Assistant

### Manual

Copy the `custom_components/solar_insights` folder into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Configuration

Add the integration via **Settings** → **Devices & services** → **Add integration** → **Solar Insights**.

| Field | Description |
| --- | --- |
| Panel height (mm) | Height of a single panel |
| Panel width (mm) | Width of a single panel |
| Amount of panels | Number of panels in the array |
| Panel tilt (°) | Tilt angle from horizontal (0° = flat, 90° = vertical) |
| Panel azimuth (°) | Compass direction the panels face (180° = south in the northern hemisphere) |
| Efficiency (%) | Panel efficiency percentage |
| Maximum power per panel (Wp) | Rated peak power per panel |
| Diffuse fraction (%) | Diffuse share of clear-sky potential for incident-normalized irradiance (default `11.5`) |
| Input power sensor | Power sensor for your installation |

Settings can be updated later via **Configure** on the integration entry.

## Entities

| Entity | Unit | Description |
| --- | --- | --- |
| Incidence angle | ° | Angle between the sun ray and the panel surface (0° = grazing, 90° = perpendicular) |
| Absolute irradiance | W/m² | Effective plane-of-array irradiance implied by measured power |
| Incident-normalized irradiance | % | Measured power vs rated power with incidence angle compensated (ideal-beam equivalent) |

### Calculations

- **Absolute irradiance:** `P / (A × η)` where `P` is input power (W), `A` is total panel area (m²), and `η` is module efficiency
- **Incident-normalized irradiance:** `(P / (P_rated × f)) × 100` where `P_rated` is total rated power (Wp) and

```text
beam = max(0, cos θ)
F_sky = (1 + cos β) / 2
f = [ (1 − k_d) × beam + k_d × F_sky ] / [ (1 − k_d) + k_d × F_sky ]
```

with configurable `k_d` (diffuse fraction, default `11.5%`). `β` is panel tilt. `F_sky` is the isotropic sky view factor (flat ≈ 1, vertical ≈ 0.5). Dividing by `f` removes incidence-angle losses so midday (`cos θ = 1`) maps to full `P_rated`. When the sun is up but behind the panel (`cos θ < 0`), beam is zero and only the diffuse sky term remains.

`cos θ` is the sun-to-panel-normal geometry factor.

- **Incidence angle:** `90° − acos(cos θ)` — the angle between the sun ray and the panel surface, not the panel normal.

The incidence angle and incident-normalized irradiance sensors are unavailable when the sun is below the horizon (elevation ≤ 0). Absolute irradiance is unavailable when the sun is behind the panel (`cos θ ≤ 0`) or required inputs are missing.

## Requirements

- Home Assistant 2023.1.0 or newer
- The [sun](https://www.home-assistant.io/integrations/sun/) integration (installed automatically as a dependency)

## License

MIT — see [LICENSE](LICENSE).
