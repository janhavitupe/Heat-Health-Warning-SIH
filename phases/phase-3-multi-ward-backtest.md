# Phase 3 — Multi-Ward Scoring & Historical Backtest

**Effort:** M · **MVP:** ✅ · **Depends on:** Phases 1, 2 · **Unblocks:** Phases 4, 5, 9

## Goal
Score every demo ward together, then replay a real past heatwave to check that the model behaves sensibly — and tune weights while changing them is still cheap.

## Why here (moved earlier than the original plan)
Testing against real history *before* building any UI means problems in the science are found when they cost hours, not weeks. The backtest also becomes the centrepiece of the final demo.

## Tasks

### Multi-ward pipeline
- [ ] Batch function: run the full pipeline (downscale → thermal → HTSI → PVI → MRI/HRI → explain) for all wards for a given time range.
- [ ] Performance check: all wards × 5 days × hourly runs in seconds.
- [ ] Output a tidy long-format table (`ward_id, date, htsi, mri, hri, alert, top_factors…`) — the same schema the API will serve.

### Backtest (§9.1)
- [ ] `weather.py`: add ERA5 fetcher (Copernicus CDS) returning the standard `WeatherFrame`.
- [ ] Replay the chosen event (from Phase 0) plus ~2 weeks before and after.
- [ ] Compare daily city-wide max alert level against IMD heatwave-declaration dates: hit rate, false alarms, lead time.
- [ ] Where health data exists, compute rank correlation between modeled MRI and reported cases (ward or district level).
- [ ] Visual check: plot ward MRI over time; do the wards the team expects to be worst actually rank highest?

### Calibration issues found in Phase 1 (fix first)
- [ ] **HTSI saturation.** Replace or supplement fixed global thresholds with a local, climate-relative scale, the way IMD defines heatwaves by departure from normal. Options to test against the May 2024 replay:
  - normalize each indicator against the ward's own summer climatology (e.g., 0 at the April–June median, 100 at the 99th percentile of 1991–2020 ERA5), or
  - raise the `full` thresholds (UTCI 46 → ~54, Heat Index 54 → ~50 with a higher zero), or
  - use shade UTCI (MRT = air temperature) for the population index and keep sunlit UTCI for outdoor work.
  Success: a normal 41 °C May day lands in High, the 17–28 May 2024 event in Very High / Extreme without hitting the cap every day.
- [ ] **Red unreachable.** Either lower the Red band, or map MRI through the risk multiplier differently (e.g., multiplier = floor + (1 − floor) × PVI percentile rank), so that the most vulnerable wards can reach Red during a severe event. Must be decided together with the saturation fix, since both change the score distribution.

### Tuning and sensitivity (§9.3)
- [ ] Adjust weights/thresholds only with documented reasoning; record each change in a changelog.
- [ ] Vary each weight ±20% and measure change in ward rankings (Spearman ρ vs. baseline).
- [ ] Vary β (from Phase 2) across its plausible range.
- [ ] Flag any factor whose small changes reshuffle rankings — candidate for local calibration.

## Deliverables
- `backtest/` scripts and notebook
- Backtest results: timeline chart vs. IMD declarations, metrics table, ward ranking
- Sensitivity analysis table
- Weight changelog

## Exit criteria
- The model reaches Orange/Red on or before IMD-declared heatwave days in the backtest event.
- Ward rankings remain broadly stable (ρ ≥ 0.8) under ±20% weight changes, or unstable factors are documented.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| No usable health-outcome data | Validate against IMD declarations only; state this clearly. |
| Model alerts far too often or too rarely | Adjust category thresholds (documented), not individual ward results. |
| ERA5 access slow | Use Open-Meteo Historical Weather API (also reanalysis-based). |
