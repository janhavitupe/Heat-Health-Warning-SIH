# Phase 1 — Core Scoring Library

**Effort:** M · **MVP:** ✅ · **Depends on:** Phase 0 · **Unblocks:** Phase 3 · **Runs in parallel with:** Phase 2 · **Status:** ✅ complete (calibration issues handed to Phase 3)

## Goal
Build `heatrisk`, a pure-Python library that turns weather for one ward into every score the platform needs — thermal stress, HTSI (including indoor heat), PVI, MRI, HRI, alert level, and an exact factor-by-factor explanation.

## Why here
This is the most scrutinized part of the project. Building it as plain functions — with no server, database, or UI — makes it fast to test, and ensures that the API, dashboard, backtest, and simulator all share one source of truth.

## Tasks

### Weather input
- [x] `weather.py`: Open-Meteo forecast (`fetch_forecast`) and reanalysis archive (`fetch_archive`) for a lat/lon.
- [x] Single `WeatherFrame` schema (hourly, tz-aware, 9 columns) so ERA5 and ensemble inputs plug in unchanged.

### Thermal stress (§6.2)
- [x] `thermal.py`: solar position (NOAA equations, evaluated mid-hour because Open-Meteo radiation is a preceding-hour mean) and a simplified standing-person MRT model. thermofeel's MRT needs longwave fluxes Open-Meteo does not provide; model parameters are in `config.yaml` → `thermal_stress.mrt`.
- [x] UTCI (thermofeel polynomial), WBGT (thermofeel Liljegren), Heat Index (NWS Rothfusz, adjusted).
- [x] Cross-checks: UTCI vs pythermalcomfort ≤ 0.1 °C; Heat Index vs pythermalcomfort ≤ 0.3 °C (23 May 2024 data); WBGT Liljegren vs thermofeel's simpler Stull/BoM method within 2.5 °C (different physics). Primary: thermofeel.
- [x] Wind: 10 m wind clamped to UTCI's valid 0.5–17 m/s; Liljegren's own stability-based 10 m → 2 m scaling used for WBGT.

### Indices (§6.3–6.6)
- [x] `indices.py`: 0–100 mapping; daily aggregation = mean of the 3 hottest hours; partial days (<20 h) dropped.
- [x] P_night from daily Tmin, P_persist from consecutive days with base ≥ 41 (first hot day earns 0).
- [x] **P_indoor** from `roof_sheet_share`, gated on base ≥ 41, ×1.5 on hot nights, capped at 10; missing roof data → 0 and flagged.
- [x] `vulnerability.py`: PVI with min-max normalization; missing or near-constant indicators (CV < 1%) held at 0.5 and flagged.
- [x] `risk.py`: MRI, HRI with H_m and C_h (clamped, default 1.0 when missing); IMD-colour alert levels.

### Explainability (§6.7)
- [x] `explain.py`: exact additive decomposition (heat part / vulnerability part / factor part), rescaled when capped; contributions sum to the score to 1e-9.
- [x] Summary string, e.g. *"Orange (72/100, model estimate) — driven by whole-body heat stress (UTCI) (+18 pts), outdoor work heat stress (WBGT) (+10 pts)."*

### Quality
- [x] 42 tests: solar geometry, MRT sign day/night, library cross-checks, extreme wind and saturated air, persistence resets, indoor gating and caps, PVI neutralization, alert band edges, exact explanation sums, golden day.
- [x] `scripts/score_ward.py` — one command prints the full explained score for any ward (live forecast or historical replay). Used instead of a notebook.

## Deliverables
- `heatrisk/`: `weather`, `thermal`, `indices`, `vulnerability`, `risk`, `explain`, `pipeline`
- `tests/` (42 passing), `scripts/score_ward.py`
- Output schema: `pipeline.score_ward()` returns `daily` (one row per date: indicators, normalized values, `pts_*`, `htsi`, `htsi_category`, `pvi`, `mri`, `hri`, `alert_mri`, `alert_hri`), `hourly`, `pvi`, `pvi_status`, and `explanations[date]["mri"|"hri"]`.

## Findings handed to Phase 3 (calibration)
Running May 2024 through the library exposed two problems — exactly what the backtest phase is for:

1. **HTSI saturates.** An ordinary Ahmedabad May day (41 °C) already scores 84 ("extreme"), and every day from 17–28 May hits the 100 cap. Sunlit UTCI above 46 °C is routine in Ahmedabad afternoons, so the fixed global thresholds cannot tell a normal hot day from a record one.
2. **No ward can reach Red.** Maximum MRI = 100 × (0.4 + 0.6 × PVI/100). With PVI currently 38.5–55.3 (half the weight held at midpoint for missing data), the ceiling is 63–73, below the Red threshold of 80.

See the Phase 3 file for the proposed fixes.
