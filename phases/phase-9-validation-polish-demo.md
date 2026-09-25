# Phase 9 — Validation, Polish & Demo

**Effort:** M · **MVP:** ✅ · **Depends on:** Phases 3, 8

## Goal
Finalize the evaluation, produce the post-event report card, make every screen understandable to a non-technical officer, and rehearse a demo that shows all six innovations in one story.

## Tasks

### Final validation (§9)
- [ ] Re-run backtest with final weights; update metrics (hit rate, false alarms, lead time, rank correlation).
- [ ] Final sensitivity analysis and downscaling validation numbers.
- [ ] Forecast reliability results (or documented limitation).
- [ ] Write `docs/evaluation.md`: methods, results, limitations — plainly stated.

### Post-event report card (§9.5)
- [ ] Auto-generated one-page report (HTML/PDF) for any event: predicted vs. reported per ward, alert lead times, missed/false alerts, health-worker anomalies, actions taken (from audit log).
- [ ] Generate it for the backtest event.

### Transparency and UX polish (§6.8)
- [ ] Audit every screen: each score shows its source label and "model estimate" tag inline.
- [ ] Methodology page in the app: formulas, weights (live from `/config`), data sources, limitations.
- [ ] Usability pass with someone unfamiliar with the project; fix confusing labels.
- [ ] Performance, error states, empty states, offline/cached fallback.

### Demo
- [ ] Script (~5–7 minutes) using replay mode:
  1. Day −3: two wards turn Yellow; probabilities show rising Red risk (*#2*).
  2. Ward detail: indoor heat from sheet roofs is a top driver (*#1*).
  3. Safe work windows issued for outdoor workers (*#4*).
  4. Cooling-desert map; system proposes two new cooling-centre sites (*#5*).
  5. Day −1: Ward 14 goes Red; officer reviews and approves alert; SMS and voice call arrive live.
  6. Health-worker report triggers a flag in a ward the model rated lower (*#6*).
  7. What-if: add tree cover and cool roofs → Red ward-days drop (*#3*).
  8. Close with the post-event report card and backtest metrics.
- [ ] Backup: screen recording of the full demo in case of network failure.
- [ ] Prepare answers for expected judge questions (data gaps, validation, clinical claims, scalability, cost).

## Deliverables
- `docs/evaluation.md`, report card for the backtest event
- In-app methodology page
- Demo script, recording, and Q&A sheet
- Final proposal and slides updated with real results

## Exit criteria
- All six innovations demonstrated end-to-end in a timed rehearsal.
- Every limitation stated in the proposal is also visible in the product.
