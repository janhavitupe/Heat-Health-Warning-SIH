# API and Ward Map (Phase 5)

The scoring library is now served through an API that refreshes by itself, with a ward-level map on top. Code: [api/](../api/) (FastAPI, SQLite, scheduler) and [frontend/](../frontend/) (React, MapLibre, Recharts).

![Map during the May 2024 replay](img/map_replay_may2024.png)

*May 2024 replay, 26 May: nearly every ward at Red. Dashed wards have low forecast confidence. The panel explains Amraiwadi's score of 98 factor by factor.*

## Running it

```bash
pip install -e ".[api]"
python -m api.cli all                      # load wards, forecast, ensemble (~4 min), May 2024 replay
cd frontend && npm install && npm run build && cd ..
uvicorn api.main:app                       # map at http://127.0.0.1:8000, API docs at /docs
```

- **Automatic refresh:** start with `HEAT_SCHEDULER=1`. The forecast then refreshes every hour at :05 and the ensemble daily at 05:45 IST. An empty database is filled straight away (tested).
- **Frontend development:** `cd frontend && npm run dev` runs a live-reloading map that proxies API calls to port 8000.
- **Docker:** `docker compose up --build`. Written but **not tested**, because Docker isn't installed on the development machine.

## Backend

| Piece | What it does |
|---|---|
| **Database** ([api/db.py](../api/db.py)) | SQLite with tables wards, runs, daily_scores, hourly_scores, ensemble_probs, events, triggers, alerts, audit_log. Ward shapes are stored as GeoJSON text; SpatiaLite wasn't available and 48 wards need no spatial queries. PostGIS stays the production path. |
| **Runs** | Every refresh is a *run*, and the API serves the latest successful one. **A failed refresh never replaces good data**; failures are listed in `/status`. Hourly forecast runs are pruned to the last 48. Ensemble runs are all kept, for the 2027 reliability check. |
| **Jobs** ([api/jobs.py](../api/jobs.py)) | Hourly forecast (3 s), daily ensemble (122 runs, about 4 min), replay builder (about 40 s). Each job retries 3 times. `python -m api.cli …` runs any job by hand. |
| **Replay** | `?replay=may2024` serves the May 2024 heatwave through the same endpoints. Weather is reanalysis. Probabilities come from archived forecasts issued 3–5 days ahead by ECMWF, GFS and ICON: what the system would have shown three days before each day. |
| **Audit log** | Ward loads and every run are logged. Phase 7 adds alert approvals. |

### Endpoints (OpenAPI docs at `/docs`)

| Endpoint | Returns |
|---|---|
| `GET /status` | Last forecast and ensemble runs, recent failures, available replays |
| `GET /days` | Every day available, with city-wide alert counts and the highest P(Red) (feeds the day slider) |
| `GET /wards?day=` | GeoJSON of all 48 wards with scores, alert levels, probabilities and top factors for one day |
| `GET /ward/{id}` | One ward: attributes, vulnerability breakdown, every day's scores with the full explanation, probabilities, hourly curve, peak |
| `GET /forecast?day=` | All wards for one day, without shapes |
| `GET /events` | Heatwave events and probability triggers that fired |
| `GET /config` | Every weight and threshold, plus the source and label of each ward data column (transparency, §6.8) |

All endpoints accept `?replay=may2024`, and every response carries "Model estimate - not a clinical prediction."

## Map

- **Mode and role:** Live vs May 2024 replay, and Municipal vs Healthcare. Municipal opens on mortality risk (MRI), Healthcare on hospitalization risk (HRI).
- **Layers:** mortality risk, hospitalization risk, heat stress (HTSI), max temperature (bands at the Heat Action Plan thresholds 41 / 43 / 45 °C), vulnerability (PVI), indoor heat from sheet roofs (Innovation 1; grey "no data" until roof data exists), and chance of Red (Innovation 2).
- **Colours:**
  - Alert layers use the fixed status palette, matching IMD green / yellow / orange / red, always with text labels.
  - Continuous layers use one orange ramp, checked for contrast in light and dark mode.
  - Wards with **low forecast confidence** are drawn fainter with a dashed outline, which the legend explains.
- **Day slider:** one button per day, with a bar showing how many wards are at each level.
- **Ward panel:**
  - summary cards;
  - the one-line explanation;
  - **"Why this score"** bars, where every factor carries its source label (Live / Census / Satellite / Estimate) and a note when data is missing;
  - the risk trajectory with the 10–90% ensemble band;
  - daily probability bars;
  - the hourly curve of air temperature, feels-like (UTCI) and work heat stress (WBGT);
  - the vulnerability breakdown.
- **All wards tab:** a sortable table, the accessible alternative to the map.
- **Light and dark themes** follow the device setting. The layout stacks on phones: at 504 px, the smallest width the test browser allows, nothing overflows.
- **Basemap:** OpenFreeMap (OpenStreetMap data, no API key). CARTO's free tiles now require a key.

## Checks done

- 75 automated tests pass, including 5 API tests on a temporary database with synthetic weather (no network).
- Every endpoint was exercised against the real database, live and replay.
- Screenshots were checked in dark and light mode and at narrow width. The frontend builds and lints cleanly.
- The scheduler fills an empty database on startup.

## Known limitations

- **Docker setup is untested.**
- **Bundle size:** the frontend bundle is about 1.7 MB, 470 kB compressed, mostly the map library. Code-splitting can come later.
- **Narrow phones:** widths below 504 px weren't tested (the test browser's minimum).
- **Single-user prototype:** SQLite and one process. There's no login yet; the role switch only picks the default layer.
