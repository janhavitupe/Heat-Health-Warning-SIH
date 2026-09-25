# Phase 2 — Urban Heat Downscaling

**Effort:** M · **MVP:** ✅ · **Depends on:** Phase 0 · **Unblocks:** Phases 3, 8 · **Runs in parallel with:** Phase 1 · **Status:** ✅ complete with literature β (station fit pending more station data; see [validation note](../docs/downscaling_validation.md))

## Goal
Make thermal stress itself vary between wards by adjusting grid-level weather with satellite land surface temperature, vegetation, and built-up density (§6.1). Also fit the LST–vegetation relationship that the what-if simulator will use in Phase 8.

## Why here
Without this, most wards receive nearly identical weather and the map shows one colour — undermining the "hyper-local" claim. It is independent of the scoring code, so a geospatial team member can build it alongside Phase 1.

## Tasks

### Satellite composites (Google Earth Engine)
- [x] Landsat 8/9 summer (Apr–Jun) daytime LST composite, cloud-masked, multi-year median.
- [x] MODIS night-time LST composite (1 km; daytime MODIS not exported — Landsat covers daytime) for the same months — night-time LST supports the P_night and indoor-heat logic.
- [x] Sentinel-2 NDVI summer median (10 m).
- [x] ESA WorldCover / GHSL built-up fraction.
- [x] Zonal statistics per ward → add `lst_day`, `lst_night`, `ndvi`, `builtup_frac`, `tree_cover` columns to `wards.parquet`.
- [x] Save scripts in `gee/` so composites are reproducible.

### Downscaling model
> **Phase 0 finding:** in Ahmedabad, daytime LST peaks in the bare-soil fringe and barely tracks built-up share (r = −0.11), while night-time LST tracks it strongly (r = +0.90). Downscale night-time/minimum temperature from night LST; test whether daytime LST improves daytime air temperature at all before using it.
- [x] Compute each ward's anomaly separately for day and night: `LST_ward − LST_city`.
- [ ] Pair ground-station air temperatures (IMD AWS, CPCB) with the Open-Meteo grid value at the same time; fit β in `T_ward = T_grid + β × (LST_ward − LST_city)`. *Only the airport (IMD 42647) has data: paired 2022–2025 Apr–Jun as a check, too few stations to fit.*
- [x] Hold out at least one station for validation; report MAE before and after adjustment. *Airport: night MAE 1.49 → 1.41 °C with β_night 0.3; daytime anomaly makes it worse (1.56 → 1.69), so β_day = 0.*
- [x] If stations are too few, use literature default β ≈ 0.3 and document it.
- [x] Mean radiant temperature adjustment for tree cover (reduced direct radiation in shaded fraction).
- [x] `downscale.py`: function taking a `WeatherFrame` + ward row → ward-adjusted `WeatherFrame`. Called inside `pipeline.score_ward` by default.

### Scenario groundwork (for Innovation 3)
- [x] Fit a simple regression across wards: `LST_anomaly ~ ndvi + builtup_frac`. Store coefficients in config — the what-if simulator uses them to translate "add 10% tree cover" into a temperature change. *NDVI and built-up are collinear (r = −0.88), so single-predictor night fits are stored (built-up R² 0.81, NDVI R² 0.54); daytime R² ≈ 0.01, left null.*

## Deliverables
- `gee/` scripts and exported per-ward satellite attributes
- `heatrisk/downscale.py` with tests
- Downscaling validation note: β value, MAE before/after, station list, limitations
- LST–NDVI–built-up regression coefficients in `config.yaml`

## Outcome
- Night-time Tmin varies by about 1 °C across wards; afternoon air temperature does not vary (β_day = 0), and tree shade changes UTCI by under 0.2 °C.
- **The 2 °C afternoon-spread criterion is not met**, because the station evidence does not support a daytime adjustment. MAE is reported honestly, as the second criterion requires.

## Exit criteria
- Ward-adjusted temperatures differ meaningfully across demo wards (e.g., a spread of 2°C or more on a hot afternoon).
- Validation MAE is reported honestly, whether or not it improves on the raw grid.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| Cloud cover limits Landsat scenes | Use MODIS and multi-year medians. |
| Station data hard to obtain | Literature β, clearly labeled; show sensitivity to β in Phase 3. |
| Earth Engine account approval delay | Apply on day 1 of Phase 0. |
