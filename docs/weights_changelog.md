# Weights & Thresholds Changelog

Every change to a value in `config.yaml` is recorded here with its reason (proposal §6.8, Phase 3 tuning).

| Date | Key | Old | New | Reason | By |
|---|---|---|---|---|---|
| 2026-09-24 | (all) | — | v0.1.0 | Initial literature-informed defaults from proposal §6 | Phase 0 |
| 2026-09-25 | downscaling.beta_default | 0.3 | split: beta_night 0.3, beta_day 0.0 | Day and night LST anomalies behave differently; daytime anomaly worsens airport-station MAE (1.56 → 1.69 °C) and does not track land cover. See docs/downscaling_validation.md | Phase 2 |
| 2026-09-25 | downscaling.day_transition_wm2 | — | 400 | Night offset fades to the day offset as the sun rises, so the dawn Tmin keeps its night adjustment | Phase 2 |
| 2026-09-25 | downscaling.lst_regression | nulls | night single-predictor fits (NDVI, built-up); day null | NDVI and built-up are collinear; daytime R² ≈ 0.01 | Phase 2 |
| 2026-09-25 | thermal_stress.normalization.utci | 26.0–46.0 | 41.9–51.9 | HTSI saturated (72% of 1991–2020 summer days Extreme). Anchored to Ahmedabad HAP 2019 Tmax thresholds by climatological rarity (41 °C → 40 pts, 45 °C → 80 pts). See docs/htsi_calibration.md | Phase 3 |
| 2026-09-25 | thermal_stress.normalization.wbgt | 25.0–33.0 | 28.6–38.3 | Same method | Phase 3 |
| 2026-09-25 | thermal_stress.normalization.heat_index | 27.0–54.0 | 36.0–50.6 | Same method | Phase 3 |
| 2026-09-25 | risk.vulnerability_floor → risk.vulnerability_spread | floor 0.4 | spread 0.4 | Old multiplier gave an average ward 0.7× the heat score, so Red was unreachable. New multiplier = 1 + spread × (PVI − 50)/50 (×1 for an average ward) | Phase 3 |
| 2026-09-25 | htsi.persistence.min_base_score | 41 | 60 | Count only heat-alert-level days (≈ Heat Action Plan Orange): IMD heatwaves need heatwave-level days, and duration adds far less risk than intensity (Anderson & Bell 2011). Backtest: plan agreement 57% → 74%, extra Orange days 13 → 4, all 11 plan Orange/Red days still caught. See docs/decisions_humidity_persistence_wards.md | Phase 3 |
| 2026-09-25 | pvi.normalization (new) | min-max (implicit) | percentile_rank | Skewed indicators (slum share: median 8%, max 61%) pushed the typical ward below the midpoint under min-max, so the average PVI fell to 41 and the risk multiplier (centred at PVI 50) lowered every ward. Percentile ranks, as in the CDC/ATSDR SVI, keep the median ward at 0.5. | Phase 3 follow-up |
| 2026-09-25 | risk.capacity (new) | — | E2SFCA, catchment 15 km, spread 0.0 (off) | Method for C_h built and tested, but kept off: only public beds are known and private hospitals handle 64.6% of urban Gujarat admissions (NSS 75th round), so a public-only factor would flag privately served wards (e.g. Thaltej, Bodakdev). public_beds_access is stored for display. | Phase 3 follow-up |
