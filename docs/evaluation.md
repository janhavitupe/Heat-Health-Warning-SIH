# Evaluation (Phase 9, proposal §9)

This page brings together how the Heat-Health Early Warning Platform was tested, what the results were, and what the tests cannot show. All numbers are from the final settings as of 27 Sep 2026: the weights in `config.yaml`, 48 wards, and sheet-roof estimates included.

**In one paragraph:**
- **The event:** we replayed the May 2024 Ahmedabad heatwave through the full system.
- **Days that mattered:** the model rated as Orange or Red every day that the city's own Heat Action Plan rule (observed temperature) called Orange or Red: 11 of 11.
- **Lead time:** it gave 4 days of Orange-or-worse warning before IMD's red alert.
- **Probabilistic warning:** forecasts issued 3–5 days ahead flagged about two-thirds of Red ward-days (238 of 344) with at least a 40% chance of Red.
- **Stability:** ward rankings barely change when any weight moves by ±20%.
- **What we cannot show:** the model predicts fewer deaths or admissions in the wards it ranks higher. Health outcomes for 2024 exist only for the city as a whole.

---

## 1. What was tested and how

| Test | Method | Script | Details |
|---|---|---|---|
| Backtest against a real heatwave | Replay 1 May–15 Jun 2024 with reanalysis weather (ERA5). Compare with IMD's red-alert window (20–24 May) and with the Heat Action Plan colour computed from observed airport Tmax | `backtest/may2024.py` | [backtest_may2024.md](backtest_may2024.md) |
| Sensitivity | Change each weight and setting on its own (±20%) and compare ward rankings (Spearman ρ) and Red ward-days | `backtest/sensitivity.py` | [backtest/results/sensitivity.md](../backtest/results/sensitivity.md) |
| Ward temperature adjustment | Airport station (IMD 42647) vs grid, 8,736 hourly pairs, Apr–Jun 2022–2025 | Phase 2 | [downscaling_validation.md](downscaling_validation.md) |
| Forecast skill | Archived forecasts (ECMWF, GFS, ICON) issued 1–5 days ahead, scored for all 48 wards, compared with the model on actual weather | `backtest/forecast_skill.py` | [forecast_phase4.md](forecast_phase4.md) |
| Model combination | Choose weights on 2024, then test blind on 2025 | Phase 4 | [forecast_phase4.md](forecast_phase4.md) |
| Heat-stress scale | Anchor the index scales to the Heat Action Plan thresholds by climatological rarity (1991–2020) | `scripts/calibrate_htsi.py` | [htsi_calibration.md](htsi_calibration.md) |
| Feedback loop | Synthetic reports with a planted cluster; check that flags find it | `heatrisk/feedback.py` | [whatif_feedback_phase8.md](whatif_feedback_phase8.md) |
| Software | 156 automated tests (formulas, API, alert workflow, CAP validity against the OASIS schema, privacy of reports) | `pytest` | [PROJECT_STATUS.md §6](PROJECT_STATUS.md) |

**What counts as "right":** we have no ward-level health data for 2024, so the references are official warnings (IMD) and the city's own alert rule applied to measured temperature. The model is judged on the **median ward** for day-by-day comparisons, and on "any ward at Red" for the IMD window.

## 2. Results

### 2.1 Backtest: May 2024

| Against the IMD red alert (20–24 May) | Result |
|---|---|
| IMD red days with any ward at Orange or above | **5 of 5** |
| IMD red days with any ward at Red | **4 of 5** (21–24 May; 20 May Orange) |
| Days of Orange-or-worse warning before 20 May | **4** (from 16 May) |
| Days outside the window with any ward at Red | 6 of 41: 17 May (day before onset) and 25–29 May (airport reached 45.0 °C on 27 May) |

| Day by day against the Heat Action Plan rule (46 days, median ward) | Result |
|---|---|
| Plan Orange/Red days the model also rated Orange/Red (hit rate) | **11 of 11** |
| Missed (plan Orange/Red, model lower) | **0** |
| Over-warning (model Orange/Red, plan Yellow or none) | 7 of 35 |
| Same level / within one level | 65% / 98% |

The over-warning days are mostly one step up on humid days. The Heat Action Plan looks only at temperature, while the model also counts humidity, hot nights and consecutive hot days, as the proposal intends. The Red days after IMD's window are hard to call false alarms: 66 of the 69 heatstroke cases in May fell in the last ten days of the month.

### 2.2 Ranking stability (sensitivity)

- **Rankings:** stable under every ±20% weight change (lowest ρ = 0.978; target ≥ 0.8).
- **The one setting that matters:** turning on daytime temperature adjustment (β_day = 0.3) reshuffles rankings (ρ = 0.73). It is off because the station data contradicts it.
- **Alert counts are more sensitive than rankings:** Red ward-days, 10–31 May, range from 283 to 429 around a baseline of 350 when the UTCI weight moves ±20%. That is because many wards sit just above the Red line at the peak. The *days* that are Red do not change, only how many wards cross the line.

### 2.3 Ward temperature adjustment

| Hourly error at the airport station | All hours | Day | Night |
|---|---|---|---|
| Raw grid | 1.53 °C | 1.56 °C | 1.49 °C |
| **With night adjustment (β_night = 0.3), used** | **1.50 °C** | 1.56 °C | **1.41 °C** |
| With day adjustment added (β_day = 0.3) | 1.57 °C | 1.69 °C | 1.41 °C |

- **Night:** the adjustment helps (night surface temperature follows built-up share, R² = 0.81).
- **Day:** the daytime satellite signal makes errors worse, so it is off.
- **Consequence:** ward differences in heat are about 1 °C at night and none by day. Differences between wards come mainly from vulnerability, sheet roofs and hot nights.
- **Exit criterion not met:** the Phase 2 target of a ≥ 2 °C afternoon spread between wards is not met, and is not supported by the evidence.

### 2.4 Forecast skill (May 2024, archived forecasts)

| | 1 day ahead | 3 days | 5 days |
|---|---|---|---|
| ECMWF: hit rate for Orange-or-worse ward-days | 85% | 84% | 82% |
| ECMWF: false alarm ratio | 21% | 28% | 32% |
| Combined probability: Brier skill vs climatology | 0.47 | 0.41 | 0.40 |

- **Every lead beats climatology:** each lead is better than always forecasting the season's average frequency (48%).
- **Combining models is best:** an equal-weight combination of the three models beats any single model or pair, in 2024 and in a blind 2025 test (Brier skill 0.47 → 0.39 at 3 days).
- **Calibration at 1 day ahead:** high probabilities are well calibrated (89% forecasts came true 88% of the time). Mid-range forecasts are over-confident (56% came true 38%).
- **Individual models:** GFS understates Ahmedabad heat stress (winds too strong) and ICON overstates it (winds too calm).

### 2.5 Early warning of Red wards (report card)

Of the 344 Red ward-days in the May 2024 event, **238 (69%)** had a chance of Red ≥ 40% in the forecasts issued 3–5 days before. The first such day was 16 May, one day before the first Red ward and four days before IMD's red alert. See the [report card](report_card_may2024.html) ([PDF](report_card_may2024.pdf)).

### 2.6 Feedback loop (synthetic)

With 69 synthetic reports (the number of heatstroke cases reported in May 2024) and a planted cluster in Vatva on 23–24 May:
- **Planted cluster:** the flag caught it on both days (6 vs 0.19 expected; 7 vs 0.26).
- **One chance flag:** Maktampura, 24 May, with 3 random reports against 0.25 expected (p = 0.002). With hundreds of ward-days tested at p < 0.01, about one chance flag is expected. This is why a flag prompts verification by the health department rather than an automatic action.
- **Recalibration:** proposed only for Vatva, and it is only a proposal.

## 3. What these tests cannot show (limitations)

1. **No ward-level health validation.** Illness and death data for 2024 are city-wide, so no Spearman correlation between ward risk and ward outcomes was possible. Ward-level case data from AMC's health department (even anonymous counts) would allow this. The feedback loop is designed to collect it.
2. **One event.** One heatwave cannot measure false-alarm rates across seasons. Replays of 2016, 2019 and 2022 (IMD-declared heatwaves) are the next step.
3. **The model is compared with rules, not outcomes.** Agreement with the Heat Action Plan shows the model is consistent with current practice. It does not prove that it is more accurate than that practice.
4. **Data gaps held at neutral:** elderly and outdoor-worker shares (no ward-level source), and hospital capacity (private beds missing). Children under 5 are census 2011 constituency averages ([decision](decision_age_worker_data.md)).
5. **Estimates:** sheet-roof shares (census 2011 rates mixed by slum share) and slum shares (2010-11 survey).
6. **Early-warning skill in the replay** uses 9 archived deterministic forecasts, not the live 122-member ensemble. The live ensemble's reliability can only be measured in the 2027 season. Daily outputs are stored for that.
7. **The ward temperature adjustment** rests on one station. The CPCB stations at Maninagar and Vatva would allow a proper fit.
8. **Advisories in Hindi and Gujarati** are drafts pending native-speaker review. Alert delivery was tested in simulated mode. A real SMS/voice test needs the authority's Twilio (or telecom) account.

Every limitation above also appears in the product: in the **Method** tab, in each ward's explanation (neutral indicators and estimates are labelled), and on the report card.

## 4. Reproduce

```
python backtest/may2024.py          # backtest tables → backtest/results/
python backtest/sensitivity.py      # sensitivity table
python backtest/forecast_skill.py   # forecast skill (needs internet for archived forecasts)
python -m api.cli replay            # replay into the API database
python scripts/demo_setup.py        # demo database + report card (HTML and PDF)
pytest                              # 156 tests
```
