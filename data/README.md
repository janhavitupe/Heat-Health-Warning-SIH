# Data Inventory — Phase 0

Pilot city: **Ahmedabad** (AMC), **48 wards** (2015 delimitation), 441 km². All 48 wards are used rather than a 15–25 ward subset, because the pipeline is cheap enough to run the whole city.

Every column in `processed/wards.parquet` is listed with its source, year, and whether it is an estimate in [`manual/column_sources.csv`](manual/column_sources.csv). `processed/completeness.csv` reports how much of each column is filled and is regenerated on every build.

## How to rebuild

```bash
python scripts/fetch_osm.py                                 # OSM facilities & cooling points (~2 min)
python gee/export_ward_stats.py --project <gcp-project>     # WorldPop + satellite (needs Earth Engine)
python scripts/build_wards.py                               # assemble wards.parquet + completeness report
pytest                                                      # data checks
```

## Folders

| Folder | Contents | Committed? |
|---|---|---|
| `raw/` | Downloaded source files, unmodified | Small files yes; rasters and OSM dumps no |
| `manual/` | Hand-entered and exported tables, provenance table | Yes |
| `processed/` | Generated outputs — never edit by hand | Yes |

## Sources and status

| Dataset | Used for | Status |
|---|---|---|
| DataMeet `Municipal_Spatial_Data/Ahmedabad` — Wards, AMC Facilities (CC BY-SA 2.5 IN) | Ward boundaries; libraries and ward offices as candidate cooling sites | ✅ Downloaded |
| OpenStreetMap via Overpass | Hospitals, clinics, drinking water, parks, schools, community centres | ✅ Downloaded (1,372 points) |
| WorldPop 2020 constrained age-sex structures | population, 60+, under-5 | ✅ Via Earth Engine (total 5.71 M). ⚠️ Age shares do not vary by ward — see limitations |
| Landsat 8/9, MODIS, Sentinel-2, ESA WorldCover | LST day/night, NDVI, built-up, tree cover | ✅ Via Earth Engine (2021–2025, Apr–Jun) |
| Census 2011 ward-level PCA (58 wards) | population, 0–6, workers by category | ✅ Downloaded to `raw/census/`. ⛔ Not usable until 2011 wards are matched to 2015 wards — see below |
| Census 2011 slum tables / Houselisting roof material | informal_housing_share, roof_sheet_share (Innovation 1) | ⛔ Blocked on the 2011→2015 ward crosswalk |
| PLFS / NSSO / Census B-series | outdoor_worker_share | ⛔ Blocked on the crosswalk |
| Major public hospitals (Wikipedia, DeshGujarat) | hospital_beds | ✅ 5 hospitals, 7,785 beds, in [`manual/hospital_beds.csv`](manual/hospital_beds.csv); private beds pending |
| AMC Urban Health Centre list (2024) | Cooling / first-aid points | ✅ 79 of ~110 parsed into [`manual/amc_uhc_list.csv`](manual/amc_uhc_list.csv); not yet geocoded |
| Wikipedia AMC zone list | zone | ✅ All 48 wards |
| NCDC NPCCHH, AMC health dept | historical_factor | ✅ Default 1.0 everywhere (no ward-level data found) |
| Meteostat (IMD 42647 airport), CPCB, SAFAR | Downscaling validation (Phase 2) | ✅ Airport hourly 1944–2026 downloaded; others listed in [`manual/stations.csv`](manual/stations.csv) with approximate coordinates |
| Backtest event | Phase 3 | ✅ May 2024 in [`manual/backtest_event.md`](manual/backtest_event.md) |
| ACGIH work/rest thresholds | Safe work windows | ✅ Verified against the 2026 table (via CCOHS) |

### The 2011 → 2015 ward crosswalk (the one remaining blocker)
The Census 2011 ward table has 58 wards identified only by number ("WARD NO.-0001"); no public source found gives their names or boundaries. The AMC census download link is dead, and the District Census Handbook has no ward map. To unblock:
1. Ask the AMC Estate / Election department or the Directorate of Census Operations, Gujarat, for the 2011 ward map or number-to-name list. A scanned map is enough.
2. Build `manual/ward_crosswalk_2011_2015.csv` (`ward_2011, ward_id_2015, share`).
3. The slum, roof, worker, and under-6 columns can then be reallocated automatically.

Until then these columns stay empty, and the scoring treats them as neutral (midpoint) and says so in each explanation.

## Known limitations

- **WorldPop age shares are effectively constant across wards** (elderly 9.3–9.4%, under-5 7.8–7.9%). WorldPop applies district-level age proportions uniformly, so these columns carry no ward-level signal. WorldPop *totals and density* do vary and are usable. For ward-level age data:
  - under-6 population is in the Census 2011 Primary Census Abstract at ward level; use it as a proxy for `under5_share`.
  - elderly (60+) is generally published only at city level; look for AMC or health-survey ward data. Otherwise PVI must treat elderly share as uniform — Phase 1 excludes near-constant indicators from min-max normalization so noise is not stretched into false differences.
- **Daytime LST is highest in the peri-urban fringe** (Odhav 49.1°C, Ramol-Hathijan 48.6°C), where bare dry soil heats faster than the built-up core; daytime LST barely correlates with built-up share (r = −0.11). **Night-time LST tracks the urban heat island strongly** (r = +0.90 with built-up share, −0.74 with NDVI). Phase 2 should use night LST for Tmin and the P_night / P_indoor terms, and treat daytime LST with care.
- **WorldPop total (5.71 M) is likely an undercount** for AMC in 2020; ward *proportions* matter more than the absolute total for relative risk.

- **Census 2011 used 2011 ward boundaries, which do not match the 2015 48-ward map.** Census-based shares must be reallocated to the new wards — by area overlap or by WorldPop population — and are flagged `is_estimate = True`.
- **OSM coverage is uneven.** Only 7 drinking-water points and 113 schools are mapped for the whole city, which is far below reality. Add AMC's cooling-centre and water-kiosk lists from its Heat Action Plan to `raw/` when obtained.
- **`nearest_hospital_km` is provisional.** It measures straight-line distance from the ward centroid, which is misleading for large wards (e.g., Thaltej). Phase 6 replaces it with population-weighted OSRM walking time.
- **OSM `amenity=hospital` includes small nursing homes.** Treat `n_hospitals` as facility density, not capacity; use `hospital_beds` for capacity.
