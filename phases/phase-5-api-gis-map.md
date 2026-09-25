# Phase 5 — API & GIS Map

**Effort:** L · **MVP:** ✅ · **Depends on:** Phases 3, 4 · **Unblocks:** Phase 7

## Goal
Serve the library's outputs through an API that refreshes automatically, and build the ward-level risk map that authorities will use every day.

## Tasks

### Backend (§8)
- [ ] Database: SQLite + SpatiaLite for the prototype (PostGIS as documented production path). Tables: wards, hourly_scores, daily_scores, ensemble_probs, events, alerts, audit_log.
- [ ] Scheduler (APScheduler): hourly current-conditions run; daily forecast + ensemble run; retries and a "last updated" timestamp.
- [ ] FastAPI endpoints:
  - `GET /wards` — GeoJSON with latest scores and alert levels
  - `GET /ward/{id}` — full detail: weather, indices, PVI breakdown, explanation, forecast, probabilities, diurnal curve
  - `GET /forecast?day=` — all wards for a forecast day
  - `GET /events` — active/forecast heatwave events
  - `GET /config` — current weights and thresholds (transparency)
- [ ] Replay mode: `?replay=<event>` serves backtest data through the same endpoints (used for the demo).

### Frontend
- [ ] React + MapLibre GL app scaffold; role switch (Municipal / Healthcare) setting the default layer (§4.4).
- [ ] Ward-coloured map with switchable layers: temperature, HTSI, PVI, indoor heat (*Innovation 1*), MRI, HRI.
- [ ] Day slider across the 5-day forecast; confidence shown as pattern/opacity or badge (*Innovation 2*).
- [ ] Ward detail panel: scores with inline source labels (Live / Census / Satellite-Derived / Estimate), explanation bars, 5-day trajectory chart, diurnal curve, probability bars.
- [ ] Legend with alert colours matching IMD; "model estimate" labeling on every score (§6.8).
- [ ] Mobile-responsive layout for field officers.

## Deliverables
- Running API with OpenAPI docs
- Web map with all layers, forecast slider, and ward drill-down
- `docker-compose.yml` bringing up API + frontend in one command

## Exit criteria
- All wards update hourly without manual intervention.
- Any ward can be clicked to see why it has its score.
- Replay mode shows the backtest event end-to-end on the map.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| Frontend falls behind | Start scaffolding as soon as Phase 1 fixes the output schema; use mock JSON until the API is ready. |
| Open-Meteo outage during demo | Replay mode and cached last-good forecast. |
