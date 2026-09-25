# Phase 3 — Multi-Ward Scoring & Historical Backtest

**Effort:** M · **MVP:** ✅ · **Depends on:** Phases 1, 2 · **Unblocks:** Phases 4, 5, 9 · **Status:** ✅ complete ([backtest write-up](../docs/backtest_may2024.md), [decisions](../docs/decisions_humidity_persistence_wards.md))

## Goal
Score every demo ward together, then replay a real past heatwave to check that the model behaves sensibly — and tune weights while changing them is still cheap.

## Why here (moved earlier than the original plan)
Testing against real history *before* building any UI means problems in the science are found when they cost hours, not weeks. The backtest also becomes the centrepiece of the final demo.

## Tasks

### Multi-ward pipeline
- [x] Batch function: run the full pipeline (downscale → thermal → HTSI → PVI → MRI/HRI → explain) for all wards for a given time range. *`pipeline.score_city`.*
- [x] Performance check: all wards × 5 days × hourly runs in seconds. *48 wards × 8 days ≈ 4 s.*
- [x] Output a tidy long-format table (`ward_id, date, htsi, mri, hri, alert, top_factors…`) — the same schema the API will serve. *`pipeline.CITY_COLUMNS`.*

### Backtest (§9.1)
- [x] ~~`weather.py`: add ERA5 fetcher (Copernicus CDS)~~ *Used the planned fallback: Open-Meteo archive (`fetch_archive`), which serves ERA5 as a standard `WeatherFrame`.*
- [x] Replay the chosen event (from Phase 0) plus ~2 weeks before and after. *1 May – 15 June 2024, `backtest/may2024.py`.*
- [x] Compare daily city-wide max alert level against IMD heatwave-declaration dates: hit rate, false alarms, lead time. *IMD red days at Orange+: 5/5; Red: 3/5 (22–24 May); lead time 3 days; Red outside window 4/41 days (25–28 May, defensible). Daily vs the Heat Action Plan rule on observed Tmax: same level 74%, all 11 plan Orange/Red days caught, higher on 11 of 46 days (after the persistence decision).*
- [ ] Where health data exists, compute rank correlation between modeled MRI and reported cases (ward or district level). *Not possible: only a city-level count (69) exists for May 2024. Revisit with GVK-EMRI 108 / AMC ward data, or replay May 2010 (daily city mortality).*
- [x] Visual check: plot ward MRI over time; do the wards the team expects to be worst actually rank highest? *Chart: `backtest/results/may2024_timeline.svg`. Top wards at the peak: Odhav, Amraiwadi, Maktampura, Viratnagar, Gomtipur (eastern mill/worker areas; Maktampura far from hospitals). Vatva ranks near the bottom, likely because its informal-housing and worker data are missing. *Checked against an independent PDEU ward index and AMC slum data; eastern ranking confirmed, Maktampura and Vatva are data artefacts. See [decisions](../docs/decisions_humidity_persistence_wards.md).*

### Calibration issues found in Phase 1 (fix first)
- [x] **HTSI saturation.** *Done: thresholds anchored to the Ahmedabad Heat Action Plan (41 °C → 40, 45 °C → 80) by climatological rarity; 0 of 46 replay days at the cap (was 35); a typical 41 °C May day scores 37. See [docs/htsi_calibration.md](../docs/htsi_calibration.md).* Replace or supplement fixed global thresholds with a local, climate-relative scale, the way IMD defines heatwaves by departure from normal. Options to test against the May 2024 replay:
  - normalize each indicator against the ward's own summer climatology (e.g., 0 at the April–June median, 100 at the 99th percentile of 1991–2020 ERA5), or
  - raise the `full` thresholds (UTCI 46 → ~54, Heat Index 54 → ~50 with a higher zero), or
  - use shade UTCI (MRT = air temperature) for the population index and keep sunlit UTCI for outdoor work.
  Success: a normal 41 °C May day lands in High, the 17–28 May 2024 event in Very High / Extreme without hitting the cap every day.
- [x] **Red unreachable.** *Done: multiplier re-centred to 1 + 0.4 × (PVI − 50)/50, so an average ward takes the heat level as is; all 48 wards reach Red on 22–24 May 2024.* Either lower the Red band, or map MRI through the risk multiplier differently (e.g., multiplier = floor + (1 − floor) × PVI percentile rank), so that the most vulnerable wards can reach Red during a severe event. Must be decided together with the saturation fix, since both change the score distribution.

### Tuning and sensitivity (§9.3)
- [x] Adjust weights/thresholds only with documented reasoning; record each change in a changelog.
- [x] Vary each weight ±20% and measure change in ward rankings (Spearman ρ vs. baseline). *All ρ ≥ 0.93 (`backtest/sensitivity.py`).*
- [x] Vary β (from Phase 2) across its plausible range. *β_night 0–0.6: ρ ≥ 0.96. β_day 0.3: ρ 0.66.*
- [x] Flag any factor whose small changes reshuffle rankings — candidate for local calibration. *Only β_day (already off on station evidence). Red ward-day counts are fragile (UTCI weight ±20% → 109–302 vs 244) because peak days sit near the Red line.*

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
