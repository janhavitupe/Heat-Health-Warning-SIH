# Phase 8 — What-If Simulator & Health-Worker Feedback Loop

**Effort:** M · **MVP:** ⚠️ Simulator required; feedback loop minimum = form + flags · **Depends on:** Phases 2, 7 · **Unblocks:** Phase 9 · **Status:** ✅ complete ([write-up](../docs/whatif_feedback_phase8.md)); feedback shown on synthetic data

## Goal
Close the loop in two directions: let planners test interventions before funding them (*Innovation 3*), and let health workers feed real cases back into the system so it learns (*Innovation 6*).

## Part A — What-If Intervention Simulator (§6.12)

### Tasks
- [x] `scenarios.py`: take a scenario (list of changes) → modified copy of ward attributes → re-run full pipeline over a chosen period (default: replayed backtest heatwave). *0.2–1 s.*
- [x] Levers:
  - [x] Tree cover +X% → NDVI change → LST anomaly change via Phase 2 regression → ward temperature and MRT *(capped at +20 points: observed range 0–22%)*
  - [x] Cool roofs on X% of sheet-roofed homes → reduced effective `roof_sheet_share` → P_indoor *(roof share estimated from census 2011; upper-bound effect)*
  - [x] New cooling centre at a map-clicked location → recompute Cooling Gap → PVI
  - [ ] Additional beds / ambulances → C_h → HRI *(not built: C_h is off until private-bed data exists, so it would change nothing)*
- [x] UI: scenario builder panel, before/after map side-by-side or toggle, per-ward delta table, "Red-alert ward-days avoided" summary. *Before/after chart instead of a second map.*
- [x] Label all outputs **Scenario Estimate**; show assumptions used.
- [x] Save/load named scenarios for comparison.

## Part B — Health-Worker Feedback Loop (§6.13)

### Tasks
- [x] Mobile-friendly report form (and optional WhatsApp flow): ward, date, age band, severity, outcome. No names, phone numbers, or identifiers stored with reports. *Web form; WhatsApp flow not built.*
- [x] Role-based access; store only per-ward, per-day aggregates for analysis. *Stored only as counts; writes need the API token when set.*
- [x] Anomaly flag: compare daily reports against expected count from MRI (simple Poisson exceedance or ratio threshold in config); raise dashboard flag *"Ward 11: reports 3× expected."* *Ratio ≥ 2, ≥ 3 reports and Poisson p < 0.01.*
- [x] Post-season recalibration script: re-estimate H_m per ward from accumulated reports; produce a *proposed* config change for authority review (never auto-applied). *Shrunk, bounded, significant-only.*
- [x] Demo data: seed the form with plausible synthetic reports during the replay, clearly labeled as synthetic.

## Deliverables
- `heatrisk/scenarios.py` and scenario UI
- Report form, anomaly flags on dashboard, recalibration script
- Short privacy note (data collected, retention, access)

## Exit criteria
- A judge can add tree cover or a cooling centre and see ward risk change within seconds.
- A submitted report appears in ward aggregates and can trigger a dashboard flag.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| Scenario re-runs too slow | Restrict to affected wards; cache baseline. |
| Recalibration untestable without real data | Demonstrate on synthetic data; present as the season-two plan. |
