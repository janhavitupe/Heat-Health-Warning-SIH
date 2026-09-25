# Phase 6 — Decision Layer

**Effort:** L · **MVP:** ✅ · **Depends on:** Phase 4 (and Phase 0 cooling data) · **Unblocks:** Phase 7

## Goal
Turn risk into decisions: ward-specific recommended actions, priority rankings, hour-by-hour **safe work windows** (*Innovation 4*), **cooling-desert** analysis with new-site selection (*Innovation 5*), and multilingual public advisories.

## Tasks

### Action Recommendation Engine
- [ ] `actions.py`: rule table in config keyed by (top risk driver × alert level) → actions, owner department, and lead time. Examples:
  - outdoor workers × Orange → shift outdoor work hours; water/shade at worksites
  - elderly × Red → door-to-door welfare checks; cooling-centre transport
  - indoor heat × Orange → open night-time cooling shelters in affected wards
  - HRI × Red → hospital surge protocol; pre-position ambulances
- [ ] Align action wording with the pilot city's Heat Action Plan departments.
- [ ] Priority-ward ranking by MRI (municipal view) and HRI (healthcare view), with probability as tie-breaker.

### Safe work windows (§6.10)
- [ ] `work_windows.py`: hourly ward WBGT → status per workload (light / moderate / heavy): continuous, work/rest ratio, or not advised; thresholds from config (ACGIH TLV / ISO 7243).
- [ ] Acclimatized (default) and unacclimatized modes; auto-suggest unacclimatized for the first 2–3 days of a heatwave event.
- [ ] Output compact schedule per ward per day, and a plain-language line for advisories.

### Cooling access and deserts (§6.11)
- [ ] Run OSRM locally (Docker) on the city's OSM extract with the walking profile.
- [ ] `cooling.py`: walking-time zones (default 15 min) around cooling points; compute Cooling Gap per ward using PVI-weighted WorldPop cells.
- [ ] Flag cooling deserts; feed cooling access back into PVI's accessibility component.
- [ ] Greedy maximum-coverage site selection: choose best *k* candidate sites (schools, community halls) to minimize vulnerable population beyond reach.

### Resource Allocation Engine
- [ ] Given limited resources (e.g., N mobile cooling units, M ambulances), allocate across wards by priority and coverage gain; show the ranked plan with reasons.

### Public Advisory Generator
- [ ] Templates for three audiences (general public, outdoor workers, elderly/caregivers) × four alert levels, parameterized with ward name, peak time, safe work window, nearest cooling point.
- [ ] Human-verified translations in Hindi and Gujarati (or the pilot city's language); Bhashini only as fallback for non-core text.
- [ ] Short SMS versions (≤160 characters) and longer WhatsApp versions; scripts for voice (used in Phase 7).

## Deliverables
- `heatrisk/actions.py`, `work_windows.py`, `cooling.py`
- Rule table and advisory templates in config/resources
- Cooling-desert layer and recommended-sites layer (GeoJSON)
- API endpoints: `/ward/{id}/actions`, `/ward/{id}/work-windows`, `/cooling`, `/allocation`, `/advisories`

## Exit criteria
- Every alert level produces ward-specific actions, a work schedule, and advisories in three languages.
- Cooling-desert map and top-*k* new sites computed for the demo wards.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| OSRM setup trouble | Straight-line distance buffers (clearly labeled as approximation). |
| Translation quality | Keep core templates short and have a native speaker verify each one. |
