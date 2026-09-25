# Forecasts and Probabilistic Alerts (Phase 4)

How the platform turns weather forecasts into a 5-day, ward-by-ward outlook with alert probabilities (Innovation 2), and how well that works. Code: [heatrisk/forecast.py](../heatrisk/forecast.py), [heatrisk/ensemble.py](../heatrisk/ensemble.py), [scripts/run_forecast.py](../scripts/run_forecast.py). Evaluation: [backtest/forecast_skill.py](../backtest/forecast_skill.py).

## What the daily run produces

`python scripts/run_forecast.py` writes to `data/forecast/<date>/`:

| File | Contents |
|---|---|
| `wards_daily.csv` | One row per ward and day (3 past days + 5 forecast days): scores, alert level, top 3 factors, **P(Yellow+), P(Orange+), P(Red)**, most likely level, confidence, the 10th–90th percentile range of MRI across the ensemble, and the ward's **peak day and peak hour** |
| `hourly.csv` | Per ward and hour: air temperature, radiant temperature, UTCI, WBGT, Heat Index (for the ward detail panel) |
| `events.json` | Heatwave events: start, peak, end, wards affected, whether the event continues beyond the forecast |
| `triggers.csv` | Probability rules that fired, e.g. Orange preparedness where P(Red) ≥ 40% within 3 days |
| `summary.md` | A short readable summary |

Run time: deterministic forecast 3 seconds; full ensemble (122 runs × 48 wards) about 4 minutes, well within a daily refresh.

## How it works

- **Weather:** Open-Meteo forecast at the city grid point, with 3 past days so the consecutive-hot-days count carries over. Each ward then gets its own downscaling (§6.1), as in the backtest.
- **Ensemble:** ECMWF IFS (51 members), GFS (31) and ICON (40), 122 runs in total. The full pipeline runs on every member for every ward.
- **Probability:** P(alert ≥ level) is the weighted share of runs reaching that level. **Each model gets equal weight** (a third each), the combination tested below.
- **Most likely level and confidence:** the level with the largest share, labelled High (≥ 70%), Medium (40–70%) or Low (< 40%).
- **Peak hour:** the hour of highest UTCI on the peak day, reported as a range ("14:00–15:00") because forecast timestamps mark the end of the hour.
- **Heatwave events:** at least **2 consecutive days** (the IMD heatwave rule) with at least **a quarter of wards** at Orange or above. On the May 2024 replay this finds exactly one event, 17–30 May, which matches the real heatwave.

## How good are the forecasts? (May 2024)

Archived *ensemble* forecasts for 2024 aren't available: Open-Meteo keeps them for about three months. Instead, archived *deterministic* forecasts from the Previous Runs API show what each model predicted 1–5 days ahead. Each forecast was scored for all 48 wards and compared with the model run on actual (reanalysis) weather. That isolates the error coming from the weather forecast.

### Single models: Orange-or-above ward-days

| Model | Hit rate, 1–5 days ahead | False alarm ratio | Why |
|---|---|---|---|
| **ECMWF IFS** | 79–88% | 18–29% | Balanced |
| **GFS** | 19–44% | 0–30% | Afternoon wind 44% too strong and air too dry, so heat stress is understated (WBGT about −1.8 °C) |
| **ICON** | 84–90% | 30–35% | Wind too calm and air too humid, so heat stress is overstated |

Afternoon wind, May 2024: airport station 3.5 m/s, reanalysis 3.7, ECMWF 3.6, GFS 5.4, ICON 2.3. Air temperature itself is well forecast by all three (Tmax bias within ±0.6 °C).

### Probabilities: combined ensemble

A **time-lagged multi-model ensemble** was built from the three models' forecasts issued L, L+1 and L+2 days ahead, 9 members with each model equally weighted.

| Days ahead | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Brier skill vs climatology | 0.53 | 0.51 | 0.47 | 0.53 | 0.44 |

Every lead beats simply using the season's average frequency (40% of ward-days at Orange+). The reliability table ([backtest/results/forecast_skill.md](../backtest/results/forecast_skill.md)) is close to ideal at 1 day ahead: forecasts of 56% came true 49% of the time, and 89% came true 93%. At 5 days ahead the forecasts are somewhat under-confident, so events happen more often than predicted.

### Which models to combine: train on 2024, blind test on 2025

| Option (3-day lead) | Brier skill 2024 | Brier skill 2025 (blind) |
|---|---|---|
| **All three models, raw** | **0.47** | **0.39** |
| All three, GFS/ICON wind corrected (factors from 2024) | 0.46 | 0.39 |
| ECMWF + ICON | 0.41 | 0.34 |
| ECMWF only | 0.40 | 0.30 |

**Decision:** use all three models with no bias correction. The wind correction didn't help in the blind season; it even made GFS worse alone, because GFS is also too dry. Each model gets equal weight. This matches the multi-model ensemble literature: combining models beats the best single model, not only because errors cancel but because the combination is more consistent and reliable (Hagedorn, Doblas-Reyes & Palmer, 2005).

## Limitations

- The reliability test uses a *lagged deterministic* ensemble (9 members), not the live 122-member ensemble. It shows the multi-model approach works; the live ensemble's own reliability should be measured on the 2027 heat season by archiving each daily run (the outputs are saved per day for this).
- One season of training, one of testing, at one grid point. Ward-days within a day are strongly correlated, so the effective sample is closer to 40 days than 2,000 ward-days.
- "Truth" is the model driven by reanalysis weather, not observed health outcomes.
- The probability trigger (P(Red) ≥ 40% within 3 days → Orange preparedness) comes from the proposal and has not been tuned.

## Sources

- Open-Meteo Ensemble API and Previous Runs API: https://open-meteo.com/en/docs/ensemble-api, https://open-meteo.com/en/docs/previous-runs-api
- Hagedorn R, Doblas-Reyes FJ, Palmer TN (2005). The rationale behind the success of multi-model ensembles in seasonal forecasting – I. Basic concept. *Tellus A* 57:219–233. https://onlinelibrary.wiley.com/doi/full/10.1111/j.1600-0870.2005.00103.x
- Doblas-Reyes FJ, Hagedorn R, Palmer TN (2005). … II. Calibration and combination. *Tellus A* 57:234–252. https://onlinelibrary.wiley.com/doi/10.1111/j.1600-0870.2005.00104.x
- India Meteorological Department, heat wave criteria (2 consecutive days): https://internal.imd.gov.in/section/nhac/dynamic/FAQ_heat_wave.pdf
