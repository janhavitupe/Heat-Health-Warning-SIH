# Downscaling Validation (Phase 2)

How grid weather is adjusted to each ward, what evidence the parameters rest on, and what it does not do. Implementation: [heatrisk/downscale.py](../heatrisk/downscale.py); parameters: `config.yaml` → `downscaling`.

## Method

```
T_ward = T_grid + β × (LST_ward − LST_city mean)
```

- **Night:** MODIS night LST anomaly, **β_night = 0.3** (literature default).
- **Day:** Landsat daytime LST anomaly, **β_day = 0** (switched off; see below).
- **Morning transition:** after sunrise the offset moves linearly from the night value to the day value as GHI rises to 400 W/m². Without this, the daily minimum (around sunrise) lost its night adjustment.
- **Humidity:** dew point is held fixed (same air mass); RH is recomputed.
- **Tree shade:** in the MRT model, the direct beam is reduced by `tree_cover × 0.5`. The 0.5 allows for people not always standing in shade. WBGT (Liljegren) has no shade term and is not adjusted.
- Wards with missing LST get no adjustment, and the gap is reported in `score_ward(...)["downscaling"]["missing"]`.

## Evidence

### Station check: Ahmedabad Airport (IMD 42647, ward AMC-14)

The station is compared with the Open-Meteo archive grid at the station location over April–June of 2022–2025 (8,736 hourly pairs, aligned in UTC). AMC-14's LST anomaly is +1.12 °C by day and +0.61 °C by night.

| | Station − grid, mean | Hourly MAE, raw grid |
|---|---|---|
| Night (GHI = 0) | +0.78 °C | 1.49 °C |
| Day (GHI > 0) | −0.68 °C | 1.56 °C |

Hourly MAE at the station for different β values:

| β_day | β_night | MAE all | MAE day | MAE night |
|---|---|---|---|---|
| 0 | 0 (raw grid) | 1.529 | 1.560 | 1.487 |
| **0** | **0.3** | **1.498** | **1.560** | **1.414** |
| 0 | 0.5 | 1.480 | 1.560 | 1.372 |
| 0.3 | 0.3 | 1.574 | 1.692 | 1.414 |

- The night anomaly has the right sign, and adding it helps. A larger β would help more at this station, but one station cannot separate the urban effect from grid bias, so the literature value is kept.
- The day anomaly has the wrong sign: the station is cooler than the grid although its LST is above the city mean. Adding it makes daytime error worse.

Script: a one-off comparison run during Phase 2; it can be repeated with `heatrisk.weather.fetch_archive(..., tz="UTC")` against `data/raw/web/meteostat_42647.csv.gz`. Station hours are UTC, which falls on :30 in IST.

### Cross-ward satellite relationships (48 wards)

| LST anomaly vs | Night R² (slope) | Day R² |
|---|---|---|
| built-up share | **0.81** (+3.19 °C per unit) | 0.01 |
| NDVI | 0.54 (−11.3 °C per unit) | 0.01 |
| tree cover | 0.32 (−6.9 °C per unit) | 0.02 |

Daytime LST peaks in the bare-soil fringe and does not follow land cover, so it is not a usable proxy for daytime air temperature. Night LST follows built-up share closely. NDVI and built-up share are collinear (r = −0.88). Fitting both together gives a positive NDVI coefficient at night, which would make "add trees" warm a ward. The scenario fits in `config.yaml` → `downscaling.lst_regression` are therefore single-predictor fits.

## Effect on scores (23 May 2024, same grid weather for all 48 wards)

| | Min across wards | Max across wards |
|---|---|---|
| Daily Tmin | 30.3 °C (AMC-34) | 31.3 °C (AMC-23) |
| Night offset | −0.70 °C | +0.27 °C |
| Daily Tmax | 46.5 °C | 46.5 °C |
| UTCI (3 hottest h) | 51.5 °C | 51.6 °C |
| P_night | 7.7 | 10.0 |

## Limitations

- **The exit criterion is not met.** Phase 2 asked for at least a 2 °C spread on a hot afternoon. The evidence does not support any daytime air-temperature spread, and the night spread is about 1 °C. Showing a larger afternoon spread would mean overriding the only station data available.
- β is not fitted. Only one station has data on disk. The CPCB (Maninagar, Vatva) and SAFAR stations in `data/manual/stations.csv` would allow a real fit with a held-out station. Gandhinagar (42654) would give an urban–rural contrast.
- The grid is treated as the city mean. Open-Meteo cells (about 0.1–0.25°) are coarser than wards, but not coarser than the whole city.
- Day-to-day variation in the heat island (calm, clear nights vs windy ones) is ignored; the offset is fixed per ward.
- On 23 May 2024, HTSI is already capped at 100 in every ward. Ward differences in heat only become visible once Phase 3 fixes that saturation.
