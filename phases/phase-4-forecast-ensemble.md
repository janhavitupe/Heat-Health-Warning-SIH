# Phase 4 — Forecast & Ensemble Probabilities

**Effort:** M · **MVP:** ✅ · **Depends on:** Phase 3 · **Unblocks:** Phases 5, 6 · **Status:** ✅ complete ([write-up](../docs/forecast_phase4.md))

## Goal
Add the time dimension: 3–5 day risk trajectories, peak identification, heatwave-event detection, and — *Innovation 2* — alert **probabilities** computed from ensemble forecasts.

## Tasks

### Deterministic forecast
- [x] Daily forecast run: 3–5 day hourly Open-Meteo forecast → full pipeline for every ward. *`scripts/run_forecast.py`; 3 s deterministic.*
- [x] Persistence (P_persist) carried correctly across observed and forecast days. *3 past days in every run (4 for the ensemble, whose first day is partial).*
- [x] Peak identification per ward: peak day, peak hour, peak MRI/HRI. *`forecast.ward_peaks`.*
- [x] Hourly diurnal curve per ward (for the ward detail panel). *`hourly.csv`.*
- [x] Heatwave-event detection: group consecutive days where ≥ N wards are Orange/Red into a named event with start, peak, and expected end. *≥ 2 consecutive days (IMD rule) with ≥ 25% of wards Orange+; May 2024 → one event, 17–30 May.*

### Ensemble probabilities (§6.9)
- [x] `weather.py`: Open-Meteo Ensemble API fetcher (ECMWF and GFS ensembles) → one `WeatherFrame` per member. *Plus ICON: 122 members.*
- [x] `ensemble.py`: run the pipeline per member (vectorized where possible) and compute P(alert ≥ Yellow / Orange / Red) per ward per day. *Each model equally weighted (tested).*
- [x] Derive "most likely level" and a confidence label (e.g., High ≥ 70%, Medium 40–70%, Low < 40%).
- [x] Probability-based trigger rules in config (e.g., Orange preparedness when P(Red) ≥ 40% at 3-day lead). *`ensemble.triggers`.*
- [x] Performance check: all members × all wards × 5 days completes within the refresh window. *122 × 48 × 8 days ≈ 4 min.*

### Reliability check (§9.4)
- [x] Using archived or reanalysis-driven hindcasts over the backtest period where available, compute Brier score and a reliability diagram. If archived ensemble forecasts are unavailable, document this and plan evaluation for the live season. *Archived ensembles unavailable; used archived deterministic forecasts (Previous Runs API) as a 9-member lagged multi-model ensemble: Brier skill 0.44–0.53 at 1–5 days. Model choice tested on a blind 2025 season. Live-ensemble reliability to be measured in the 2027 season.*

## Deliverables
- `heatrisk/ensemble.py` and forecast runner
- Output table extended with `p_yellow, p_orange, p_red, confidence, peak_day, peak_hour`
- Heatwave-event objects (JSON)
- Reliability note

## Exit criteria
- Every ward has a 5-day trajectory, peak, and alert probabilities, refreshed daily.
- Probabilities are monotonic (P(Yellow+) ≥ P(Orange+) ≥ P(Red+)) and sum-checks pass.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| Ensemble run too slow | Run ensemble at city-grid level and apply ward adjustments afterward (downscaling is additive). |
| No archived ensemble data for reliability test | Report as a limitation; show the method on live forecasts. |
