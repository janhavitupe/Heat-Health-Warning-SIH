# Weights & Thresholds Changelog

Every change to a value in `config.yaml` is recorded here with its reason (proposal §6.8, Phase 3 tuning).

| Date | Key | Old | New | Reason | By |
|---|---|---|---|---|---|
| 2026-09-24 | (all) | — | v0.1.0 | Initial literature-informed defaults from proposal §6 | Phase 0 |
| 2026-09-25 | downscaling.beta_default | 0.3 | split: beta_night 0.3, beta_day 0.0 | Day and night LST anomalies behave differently; daytime anomaly worsens airport-station MAE (1.56 → 1.69 °C) and does not track land cover. See docs/downscaling_validation.md | Phase 2 |
| 2026-09-25 | downscaling.day_transition_wm2 | — | 400 | Night offset fades to the day offset as the sun rises, so the dawn Tmin keeps its night adjustment | Phase 2 |
| 2026-09-25 | downscaling.lst_regression | nulls | night single-predictor fits (NDVI, built-up); day null | NDVI and built-up are collinear; daytime R² ≈ 0.01 | Phase 2 |
