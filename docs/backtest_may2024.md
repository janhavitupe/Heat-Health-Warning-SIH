# Backtest: May 2024 Heatwave (Phase 3)

The full model (downscaling → thermal → HTSI → PVI → MRI) was replayed for all 48 wards from 1 May to 15 June 2024 and compared with what officially happened. Scripts: [backtest/may2024.py](../backtest/may2024.py), [backtest/sensitivity.py](../backtest/sensitivity.py), [backtest/plot_timeline.py](../backtest/plot_timeline.py). Raw outputs: [backtest/results/](../backtest/results/).

![Model vs official alerts, May–June 2024](../backtest/results/may2024_timeline.svg)

## Setup

- **Weather:** Open-Meteo historical archive (ERA5 reanalysis) at the city centre, downscaled to each ward. This is the "Open-Meteo instead of Copernicus CDS" fallback from the phase plan; both are ERA5.
- **Model settings:** calibrated config (see [htsi_calibration.md](htsi_calibration.md)), with consecutive-days points counting only heat-alert-level days, slum share from the AMC slum survey, and vulnerability indicators percentile-ranked (see [decisions_humidity_persistence_wards.md](decisions_humidity_persistence_wards.md)). The numbers below use these final settings.
- **Reference A:** IMD red alert for Ahmedabad, 20–24 May 2024 (All India Radio, 20 May 2024).
- **Reference B:** the Ahmedabad Heat Action Plan colour for each day (White ≤ 41 °C, Yellow 41.1–43, Orange 43.1–44.9, Red ≥ 45), applied to the observed daily maximum at the airport station (IMD 42647). Station maxima come from hourly readings, so they may be a few tenths of a degree below the official daily maximum.
- **Health outcomes:** city-level only (69 heatstroke cases in May; 66 in the last ten days, from a news report). No ward-level comparison is possible for this event.

> Numbers refreshed on 26 Sep 2026 after the Phase 6 vulnerability update (walking access to health care and cooling access in PVI). Changes were small.

## A. Did the model catch the IMD red alert?

| Metric | Result |
|---|---|
| IMD red days with any ward at Orange or above | **5 of 5** |
| IMD red days with any ward at Red | 3 of 5 (22–24 May; 20–21 May Orange) |
| IMD red days with the median ward at Red | 3 of 5 (22–24 May) |
| Lead time: days at Orange or above before 20 May | **3** (from 17 May) |
| Days outside the window with any ward at Red | 5 of 41 (25–29 May) |

The Red days after the window (25–29 May; 29 May only 7 wards) are hard to call false alarms. The airport reached 45.0 °C on 27 May, the Heat Action Plan's own Red threshold, and 66 of the 69 heatstroke cases fell in the last ten days of May.

## B. Day by day against the Heat Action Plan rule

The model's level for the median ward, compared with the plan's level from observed Tmax, over 46 days:

| Metric | Result |
|---|---|
| Same level | 31 days (67%) |
| Within one level | 45 days (98%) |
| Plan Orange/Red days where the model is Orange/Red | **11 of 11** |
| Model lower than the plan | 1 day |
| Model higher than the plan | 14 days |
| Plan Yellow/White days where the model is Orange/Red | 6 of 35 |

| Plan \ Model | Green | Yellow | Orange | Red |
|---|---|---|---|---|
| White (no alert) | 9 | 6 | 0 | 0 |
| Yellow | 1 | 13 | 5 | 1 |
| Orange | 0 | 0 | 5 | 2 |
| Red | 0 | 0 | 0 | 4 |

**The model never misses a dangerous day, and when it disagrees it usually rates higher.** Most of the 14 higher days are one step up (White → Yellow, or a muggy Yellow day → Orange), plus Red on 26 and 28 May after several heat-alert days in a row. That rests on warm nights and humid air, which the plan's temperature-only rule doesn't count.

Before the persistence decision, 19 days rated higher (13 plan Yellow/White days at Orange+). Consecutive-days points were adding up through the long humid spell. The change and its evidence are in [decisions_humidity_persistence_wards.md](decisions_humidity_persistence_wards.md).

## C. Sensitivity (§9.3)

Ward ranking is measured by mean MRI over 17–28 May. Each setting was changed on its own and the ranking compared with the baseline (Spearman ρ); the target is ρ ≥ 0.8. The full table is in [backtest/results/sensitivity.md](../backtest/results/sensitivity.md).

| Change | Lowest ρ | Largest rank move | Red ward-days (baseline 302) |
|---|---|---|---|
| Each HTSI weight ±20% | 0.996 | 4 | 195–350 (UTCI weight moves it most) |
| Each PVI weight ±20% (7 indicators) | 0.963 (slum share ×0.8) | 11 | 294–306 |
| Hot-night / persistence points ±20% | 0.999 | 1 | 254–313 |
| β_night 0 to 0.6 | 0.982 | 10 | 283–287 |
| Vulnerability spread 0.2 to 0.6 | 0.979 (0.2) | 8 | 273–320 |
| **β_day = 0.3** | **0.721 ⚠️** | 23 | 295 |

- **Rankings are stable** under every ±20% weight change (ρ ≥ 0.963). The phase target is met.
- **Slum share, hospital access and density drive the rankings** (the three vulnerability indicators with real ward data). Percentile ranking keeps any one of them from dominating. Re-run once worker and age data arrive.
- **Turning on daytime downscaling (β_day = 0.3) reshuffles the rankings** (ρ 0.72). That setting is off because the station evidence contradicts it ([downscaling_validation.md](downscaling_validation.md)). Turning it on would change which wards look worst, not just the numbers.
- **Alert counts are more fragile than rankings.** Red ward-days range from 195 to 350 when the UTCI weight moves ±20%, because many peak days sit just above the Red line (80). The Red *days* are the same; the number of wards over the line changes. Report ward counts on Red days with that uncertainty in mind.

## Performance

`pipeline.score_city` scores 48 wards × 8 days (hourly thermal model, downscaling, explanations) in about 4 seconds on a laptop.

## Decisions taken

Both open questions were decided from published research ([decisions_humidity_persistence_wards.md](decisions_humidity_persistence_wards.md)):

1. **Humid, long hot spells:** consecutive-days points now count only heat-alert-level days (base ≥ 60). Humidity and hot-night points are unchanged.
2. **Worst-ward list:** the eastern wards on top match an independent PDEU study. The two outliers were data gaps. Slum shares are now filled from the AMC slum survey and vulnerability indicators are percentile-ranked, so Maktampura moved from 5th to 30th and Vatva from 41st to 23rd. Top wards at the peak: Amraiwadi, Odhav, Jamalpur, Asarwa, Indrapuri.

## Limitations

- One event, city-level outcomes only. Ward rankings can't be checked against health data.
- The IMD window comes from a news report of the announcement; later extensions are not captured.
- Reference B is itself only a rule (the plan's Tmax thresholds), not an outcome.
- Secondary event (May 2010, with published daily mortality, Azhar et al. 2014) is not yet replayed.
