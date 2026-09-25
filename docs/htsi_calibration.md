# HTSI and Risk Calibration (Phase 3)

This note covers the fix for the two problems found in Phase 1: HTSI hit the 100 cap on ordinary summer days, and no ward could ever reach Red. Scripts: [build_climatology.py](../scripts/build_climatology.py) and [calibrate_htsi.py](../scripts/calibrate_htsi.py). Values: `config.yaml` → `thermal_stress.normalization` and `risk.vulnerability_spread`.

## 1. Why HTSI saturated

The original thresholds were global. Checked against Ahmedabad's own climate (Open-Meteo/ERA5, city centre, April–June 1991–2020, 2,730 days, run through the same thermal code as the live pipeline):

| Indicator | Old "full" (100) | Where that falls in the local climate |
|---|---|---|
| UTCI | 46 °C | about the 80th percentile: one summer day in five maxed out |
| WBGT | 33 °C | about the 90th percentile |
| Heat Index | 54 °C | never reached (99.9th percentile is 48 °C) |

Under the old thresholds, 72% of all summer days from 1991 to 2020 rated "Extreme", and a typical 41 °C May day scored 96.

## 2. Local anchor: the Ahmedabad Heat Action Plan

The city already has health-based heat triggers. The Ahmedabad Heat Action Plan (2019 update, section "Color Signals for Heat Alert", [NRDC PDF](https://www.nrdc.org/sites/default/files/ahmedabad-heat-action-plan-2019-update.pdf)) sets:

| Alert | Name | Max temperature |
|---|---|---|
| White | No alert | ≤ 41 °C |
| Yellow | Hot Day Advisory | 41.1–43 °C |
| Orange | Heat Alert Day | 43.1–44.9 °C |
| Red | Extreme Heat Alert Day | ≥ 45 °C |

## 3. Method: match by rarity

HTSI uses UTCI, WBGT and Heat Index, not air temperature, so the plan's thresholds can't be applied directly. Instead each indicator is matched **by rarity**:

1. Find how rare each plan threshold is in the 1991–2020 climatology. Tmax 41 °C is the 80.5th percentile and 45 °C is the 99.85th.
2. Take each indicator's value at those same percentiles.
3. Scale linearly so the 41 °C-equivalent value scores **40** (the edge of High) and the 45 °C-equivalent scores **80** (the edge of Extreme).

| Indicator | 0 at | 100 at | 43 °C-equivalent scores (target 60) |
|---|---|---|---|
| UTCI | 41.9 °C | 51.9 °C | 60 |
| WBGT | 28.6 °C | 38.3 °C | 58 |
| Heat Index | 36.0 °C | 50.6 °C | 60 |

The 43 °C check lands on its target, so a straight line fits between the anchors.

**Resulting HTSI categories over 1991–2020 summers:** Low 42.8%, Moderate 39.5%, High 13.7%, Very High 3.6%, Extreme 0.4% (previously 72% Extreme).

The hot-night, persistence and sheet-roof points still add up to 30 on top of the base. That is intentional: the plan's thresholds look at daytime temperature only, and the extra points carry the risks it leaves out.

## 4. Why Red was unreachable, and the fix

Old: `risk = HTSI × (0.4 + 0.6 × PVI/100)`. A ward of average vulnerability (PVI 50) got only 0.7× the heat score, so the city's hazard was always discounted. With PVI at 38.5–55.3, no ward could exceed 73, below Red (80).

New: `risk = HTSI × (1 + 0.4 × (PVI − 50)/50) × factor`.

- A ward of average vulnerability takes the heat level unchanged, so an extreme heat day is Red for a typical ward.
- The multiplier runs from ×0.6 (PVI 0) to ×1.4 (PVI 100). With PVI in its usual range, vulnerability moves a ward up or down by up to about one alert level.
- **Explanations:** each PVI indicator now contributes points in proportion to its distance from the city midpoint. Neutral indicators (missing or flat data) contribute exactly 0 instead of an invented share. Below-average vulnerability shows as negative points. Contributions still add up to the score exactly.

`vulnerability_spread = 0.4` is a prototype choice, not a fitted value; the sensitivity analysis should vary it.

## 5. Result: May 2024 replay, all 48 wards

> Measured before the persistence decision (consecutive-days points now start at base ≥ 60). Final backtest numbers are in [backtest_may2024.md](backtest_may2024.md); the reasoning is in [decisions_humidity_persistence_wards.md](decisions_humidity_persistence_wards.md).

Grid weather at the city centre, downscaled per ward.

| Dates | What the model says | What happened |
|---|---|---|
| 7, 10–12 May | Orange in some to all wards | Airport max 42–43 °C |
| **17–20 May** | **Orange in all 48 wards** | Max 44.7–45.5 °C; IMD red alert announced 20 May |
| **21–28 May** | **Red**: 13 wards on the 21st, all 48 on 22–24 May, 8–45 wards on 25–28 May | Peak 46.2 °C on 23 May (station); 66 of 69 heatstroke cases in the last ten days of May |
| 29 May – 10 June | Mostly Orange | Tmax 41–43 °C but humid pre-monsoon air (high WBGT and Heat Index) |
| 13–15 June | Green | Cooling |

- The model reaches Orange **3 days before** IMD's red alert, and Red one day after it was announced. It stays at Red or Orange through the whole IMD window.
- **Open question:** early-June humid days rate Orange, while the plan's Tmax rule would give Yellow or no alert. This may be real humid-heat risk that a temperature-only rule misses, or over-alerting. The formal backtest (hit rate, false alarms, lead time) should decide.
- On any given day, MRI varies by about 5–12 points across wards, driven by PVI (only hospital distance and density have real data so far) and night-time downscaling.

| | Before | After |
|---|---|---|
| Replay days with HTSI at the cap (city centre) | 35 of 46 | 0 |
| Wards ever Red | 0 | 48 |
| Typical 41 °C May day (1991–2020) | HTSI 96, Extreme | HTSI 37, Moderate |

## 6. Limitations

- The anchors are daytime maximum temperatures. How rare WBGT and Heat Index are does not line up perfectly with how rare Tmax is, which is why humid days score higher than the plan's rule would.
- The climatology is one grid point (city centre) with no downscaling, which is fine while β_day = 0.
- ERA5 Tmax at the airport matches the station on average (bias −0.04 °C over 360 summer days, 2022–2025). A different weather source would need its own climatology.
- The plan's thresholds come from a mortality study of the city (Azhar et al., 2014). The risk multiplier has not been checked against ward-level health outcomes, because none are available.
