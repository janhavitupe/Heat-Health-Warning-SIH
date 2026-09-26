# Data Inventory — Phase 0

Pilot city: **Ahmedabad** (AMC), **48 wards** (2015 delimitation), 441 km². All 48 wards are used rather than a 15–25 ward subset, because the pipeline is cheap enough to run the whole city.

Every column in `processed/wards.parquet` is listed with its source, year, and whether it is an estimate in [`manual/column_sources.csv`](manual/column_sources.csv). `processed/completeness.csv` reports how much of each column is filled and is regenerated on every build.

## How to rebuild

```bash
python scripts/fetch_osm.py                                 # OSM facilities & cooling points (~2 min)
python gee/export_ward_stats.py --project <gcp-project>     # WorldPop + satellite (needs Earth Engine)
python scripts/extract_slums.py                             # slum huts per ward from the AMC Slum Free City Plan (needs .[pdf])
python scripts/geocode_uhcs.py                              # place AMC Urban Health Centres (Nominatim; cached in the CSV)
python gee/export_pop_grid.py --project <gcp-project>       # WorldPop 100 m cells (Earth Engine)
python scripts/build_walk_network.py                        # OSM walking network (~1 min, 63 MB, not committed)
python scripts/build_access.py                              # cooling gap, deserts, new sites, walking access to health care
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
| AMC socio-economic slum survey 2010-11, via the Slum Free City Action Plan 2014 (Annexure II) | informal_housing_share, slum_huts | ✅ 686 slums, 161,463 huts (99.2% of the survey total) extracted by `scripts/extract_slums.py`; 2010 ward names mapped to 2015 wards in [`manual/ward_crosswalk_slum_2010.csv`](manual/ward_crosswalk_slum_2010.csv) (name match, TP scheme or geocoded locality; evidence per row) |
| Census 2011 Houselisting roof material | roof_sheet_share (Innovation 1) | ⛔ Blocked on the 2011→2015 ward crosswalk |
| PLFS / NSSO / Census B-series | outdoor_worker_share | ⛔ Blocked on the crosswalk |
| Major public hospitals (Wikipedia, DeshGujarat) | hospital_beds, public_beds_access | ✅ 5 hospitals, 7,785 beds, in [`manual/hospital_beds.csv`](manual/hospital_beds.csv) (Shardaben placed at its ward centroid). Private beds pending. Private hospitals handle 64.6% of urban Gujarat admissions, so `capacity_factor` stays at default until they are added |
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
3. The roof, worker, and under-6 columns can then be reallocated automatically. (Slum share no longer depends on this; it comes from the AMC slum survey.)

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

### Slum share (informal_housing_share)
- **Source:** AMC's 2010-11 socio-economic slum survey, as listed slum by slum (ward name and huts) in Annexure II of the [Ahmedabad Slum Free City Action Plan (2014)](https://pas.org.in/Portal/document/PIP%20Application/Ahmedabad%20Slum%20Free%20City%20Action%20Plan%20RAY.pdf). Copy saved in `raw/web/amc_slum_free_city_plan_2014.pdf`.
- **Method:** huts × 4.47 people per hut (survey total 727,934 people / 162,749 huts) ÷ 2020 WorldPop ward population. Wards with no listed slum get 0 (Viratnagar, Maktampura).
- **Old → new wards:** 65 old ward names. Most match directly; the rest were placed by the slums' Town Planning scheme or by geocoding the old locality (see the crosswalk's `evidence` column). Mahavirnagar is split 50/50 between Amraiwadi and Bhaipura-Hatkeshwar by TP scheme.
- **Known bias:** the survey counts slums, not the formal resettlement (BSUP) flats where about 11,000 Sabarmati Riverfront families were moved in 2006–2014. **Vatva**, which holds about half of those flats, and Odhav are therefore understated. Chawls (old mill-worker tenements), common in eastern wards such as Viratnagar, are also not counted as slums.
- **Years differ:** 2010 slum counts over 2020 population. Only the ward's percentile rank enters PVI, so the share is used as a relative indicator.

### Cooling and health access (Phase 6)
- **Population grid:** `processed/pop_grid.parquet`, 47,622 populated WorldPop 2020 100 m cells (unconstrained product, 6.10 M people). Only the distribution within wards is used; totals are rescaled to the ward table.
- **Walking network:** OpenStreetMap footpaths and streets for the city plus 1 km (`scripts/build_walk_network.py`).
- **Cooling places:** AMC libraries and ward offices (public buildings), Urban Health Centres (70 of 79 geocoded; 20 only by ward name, see `coord_quality` in `manual/amc_uhc_list.csv`), the 5 public hospitals, OSM parks, drinking water and BRTS stations. Temples, mosques and malls (OSM) are a sensitivity tier; OSM maps only 179 places of worship, far below reality.
- **Outputs:** `processed/ward_access.csv` (cooling_gap, cooling_gap_with_community, cooling_desert, health_walk_km), `processed/cooling_sites.geojson` (5 recommended sites), `processed/ward_cooling_points.json` (named places used in advisories).
