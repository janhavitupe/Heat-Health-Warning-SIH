# Backtest Event Dossier

Used in Phase 3 to replay a past heatwave through the model (proposal §9.1).

## Chosen event: May 2024 (primary)

| Item | Value | Source |
|---|---|---|
| Replay window | 1 May – 15 June 2024 (proposed; covers ~2 weeks before the peak and the tail-off) | — |
| IMD red alert for Ahmedabad | Announced 20 May 2024, "for five days" (≈ 20–24 May) | [All India Radio News, 20 May 2024](https://www.newsonair.gov.in/heatwave-to-prevail-for-next-three-days-in-gujarat-imd) |
| IMD severe-heatwave red alert, Gujarat region | Issued 20 May 2024 for the next four days | [All India Radio News, 20 May 2024](https://www.newsonair.gov.in/imd-issues-severe-heatwave-red-alert-for-northwest-india-north-mp-gujarat-for-next-4-days) |
| Observed maximum, Ahmedabad Airport (WMO 42647) | **46.2 °C on 23 May 2024** (hourly data) | Meteostat bulk data, `data/raw/web/meteostat_42647.csv.gz` |
| Reported maximum (news) | 45 °C in the 24 h before 20 May | All India Radio News, 20 May 2024 |
| Heatstroke cases | Gujarat 187 in May 2024, of which Ahmedabad 69; 66 of Ahmedabad's in the last ten days of May | [Gulf News, 10 Apr 2025](https://gulfnews.com/world/asia/india/gujarat-can-witness-one-of-the-hottest-years-in-2025-1.500089484) — no primary source cited; confirm with GVK-EMRI 108 or AMC health department |
| AMC Heat Action Plan alert dates | **To find** — AMC press notes / local news (Divya Bhaskar, Ahmedabad Mirror, DeshGujarat) | — |
| IMD district warning archive | **To collect** — IMD Ahmedabad Meteorological Centre daily district warnings for May 2024 | https://mausam.imd.gov.in/ahmedabad/ |

### What the backtest will check
- Does the model reach Orange/Red on or before 20 May and hold it through the IMD red-alert window?
- Does the city-wide daily maximum MRI track the Meteostat hourly temperature peak on 23 May?
- Health data is city-level only (69 cases). That rules out a ward-level rank correlation for this event; report this plainly.

## Secondary event: May 2010

The heatwave that led to the Ahmedabad Heat Action Plan. Daily all-cause mortality is analysed in Azhar et al. (2014), *PLoS ONE* 9(3): e91831. It's city-level, but a real health outcome to compare model output against. Meteostat 42647 hourly data covers 2010.

## Sources consulted
- All India Radio News (newsonair.gov.in), 20 May 2024 — two articles linked above
- Gulf News, 10 April 2025 — heatstroke counts
- Meteostat bulk hourly data, station 42647
