# Phase 0 — Foundation & Data Freeze

**Effort:** M · **MVP:** ✅ · **Depends on:** nothing · **Unblocks:** Phases 1, 2

## Goal
Lock the pilot city, the demo ward set, and every static dataset into a single frozen ward table, and write every formula weight and threshold into one config file. After this phase, only weather data is fetched live.

## Why first
Data collection is the slowest and most uncertain part of the project. If ward boundaries or roof-material data turn out to be unavailable, the team must find out — and switch city if necessary — before writing any scoring code.

## Tasks

### City and wards
- [x] Verify ward boundary availability for Ahmedabad (AMC GIS portal, DataMeet); fall back to Nagpur or Delhi if unavailable (§4.3).
- [x] ~~Select 15–25 demo wards~~ — decided to use all 48 AMC wards; the pipeline is cheap enough.
- [x] Clean boundaries into `data/processed/wards.geojson` (EPSG:4326, `ward_id` AMC-NN, ward name).
- [x] AMC zone for each ward (Wikipedia list, name-matched; Indrapuri's South-zone assignment confirmed by the AMC UHC list).

### Population and vulnerability (§6.4, §7.4)
- [ ] **Blocked on the 2011 ward map.** Census 2011 ward-level PCA is downloaded (`data/raw/census/pca_tv_ahmadabad_2011.xlsx`, 58 wards) but the wards are numbered with no names or boundaries. Obtain a 2011 AMC ward map or number-to-name list (AMC Estate/Election dept, Directorate of Census Operations Gujarat, or a scanned map), then build `data/manual/ward_crosswalk_2011_2015.csv`. Unblocks slum share, roof material, and worker data.
- [ ] Extract **roof material** from Census houselisting tables — share of households with metal/asbestos/sheet roofs → `roof_sheet_share` (*Innovation 1*). Document the geographic level actually available and any disaggregation.
- [x] Run `gee/export_ward_stats.py` (project `heat-health-sih`): WorldPop population plus LST day/night, NDVI, built-up, tree cover for all 48 wards.
- [ ] WorldPop age shares turned out uniform across wards. Get ward-level under-6 from the Census 2011 Primary Census Abstract, and search for any ward-level elderly data (see data/README.md).
- [ ] Estimate outdoor-worker share from PLFS/NSSO district figures, disaggregated by ward population; document the method.

### Facilities and cooling points (§7.6)
- [x] Hospitals and clinics from OpenStreetMap (`scripts/fetch_osm.py`).
- [x] Public hospital beds for the 5 largest public hospitals (`data/manual/hospital_beds.csv`, 7,785 beds). 
- [ ] Private hospital beds (Health Facility Registry / nursing-home registrations) and Shardaben coordinates.
- [x] OSM cooling points (drinking water, parks) and candidate sites (schools, community centres), plus AMC libraries and ward offices from DataMeet.
- [x] AMC Urban Health Centre list parsed (`data/manual/amc_uhc_list.csv`, 79 of ~110 centres; personal contact details removed). 
- [ ] Geocode UHCs and add the remaining ~30; add AMC water-kiosk locations if published.
- [x] Store all points in `data/processed/cooling_points.geojson`, each tagged with `layer`, `role` (health_facility / cooling_point / candidate_site), and `source`.

### Ground truth for later phases
- [x] Station list (`data/manual/stations.csv`): IMD airport 42647 with hourly data 1944–2026 downloaded; 2 CPCB and 8 SAFAR stations with approximate coordinates. 
- [ ] Download CPCB station temperature/RH (app.cpcbccr.com) and request SAFAR data from IITM.
- [x] Backtest event chosen: May 2024 (IMD red alert from 20 May; airport max 46.2 °C on 23 May; 69 heatstroke cases). See `data/manual/backtest_event.md`. 
- [ ] Find AMC Heat Action Plan alert dates for May 2024 and a primary source for the heatstroke count.

### Configuration and repo
- [x] Create `config.yaml` with every value from §6: indicator mapping thresholds, HTSI weights, P_night / P_persist / P_indoor rules, PVI weights, H_m and C_h bounds, alert bands, WBGT work thresholds, walking-time threshold.
- [x] Set up the repository structure (see [README](README.md)), Python environment, and test runner (pytest, 13 tests).
- [x] Build `data/processed/wards.parquet` (`scripts/build_wards.py`); provenance and `is_estimate` per column in `data/manual/column_sources.csv`; fill rates in `data/processed/completeness.csv`.
- [x] ACGIH work/rest WBGT thresholds verified against the 2026 table (reproduced by CCOHS); `thresholds_verified: true`.

## Deliverables
- `wards.geojson`, `wards.parquet`, `cooling_points.geojson`, `completeness.csv`
- `config.yaml` (reviewed by the whole team)
- `data/README.md` — data inventory: every column, its source, its year, and whether it is measured or estimated
- Backtest event dossier (dates, IMD declarations, reported outcomes)

## Exit criteria
- Every demo ward has a complete row in `wards.parquet` with no unexplained nulls.
- Every estimated column is flagged and its method documented.
- The config file contains no placeholder values.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| No usable ward boundaries | Switch pilot city now — this is the go/no-go check. |
| Roof data only at town level | Disaggregate using slum share and built-up density; flag as estimate. |
| Census ward IDs don't match GIS ward IDs (delimitation changes) | Spatially join WorldPop-derived values instead; document the mismatch. |
