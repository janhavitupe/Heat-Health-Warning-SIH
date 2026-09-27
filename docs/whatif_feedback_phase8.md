# What-If Simulator and Health-Worker Feedback (Phase 8)

Phase 8 closes the loop in two directions. Planners can test interventions before funding them (Innovation 3), and health workers can feed real cases back so the system can learn (Innovation 6). Code: [heatrisk/scenarios.py](../heatrisk/scenarios.py), [heatrisk/feedback.py](../heatrisk/feedback.py), [api/loop.py](../api/loop.py); app tabs **What-if** and **Reports**.

---

## A. What-if simulator

Interventions are applied to ward attributes, and the affected wards are re-scored over the May 2024 heatwave with the same pipeline as the live model. Every result is labelled **Scenario Estimate** and lists its assumptions.

| Lever | How it enters the model | Evidence |
|---|---|---|
| **Tree cover +X points** (max 20) | Tree cover → NDVI (+0.727 per unit, r = 0.91 across Ahmedabad's wards) → night surface temperature (−11.3 °C per unit NDVI, Phase 2 fit) → night air temperature (× 0.3). More tree shade also lowers daytime radiant temperature | Ward data; Ziter et al. (2019, PNAS): the strongest cooling comes above 40% canopy, while Ahmedabad's wards have 0–22%, so the lever is capped at +20 points |
| **Cool roofs on X% of sheet roofs** | Sheet-roof share × (1 − X) → indoor-heat points | **No effect yet:** roof data is missing, and the result says so |
| **New cooling centre** (map click or recommended site) | People newly within a 15-minute walk along the street network → ward cooling gap → vulnerability (PVI) | Phase 6 access model |

**Two design choices keep unaffected wards unchanged:**
- **Temperature:** changes are added as scenario offsets rather than edits to satellite values. Editing one ward's surface temperature would shift the city mean and every other ward's adjustment.
- **Vulnerability:** changed wards are scored against the *baseline* city, since percentile ranks would otherwise move every ward. Unchanged wards reproduce their baseline scores exactly (tested).

**Examples (May 2024 replay):**

| Scenario | Effect |
|---|---|
| +10 points of trees in Baherampura and Odhav | Night minimum −0.25 °C; average risk −1.2 in each; **1 Red day avoided in each** |
| +15 points of trees in Baherampura | Average risk −1.7; 1 Red day avoided |
| Cooling centre at recommended site 1 (Baherampura) | 20,206 more people within a 15-minute walk; vulnerability −1.5; average risk −0.7 |
| Cool roofs 50% in Baherampura | No effect (no roof data), and the result says so |

**Speed:** 0.2–0.4 s for tree scenarios. About 1 s for a cooling centre, using a cached walking network (`scripts/build_access.py` writes it; loading takes 1.4 s instead of about 20 s).

**Honest reading:** the effects are modest because Ahmedabad's measured relationships are modest in the observed range of tree cover. The simulator is for comparing options, not promising outcomes.

Scenarios can be saved by name and compared (`POST /scenarios`, `GET /scenarios`).

## B. Health-worker feedback loop

**Report form** (app → Reports, or `POST /reports`): ward, date, age band, severity (mild / moderate / severe), outcome (treated / referred / died) and reporter role (ASHA, ANM, PHC doctor, UHC staff, hospital). Nothing else is asked for or accepted.

**Expected cases:** each day's city-wide reports are shared across wards in proportion to **population × modelled mortality risk**. This needs no historical calibration, so it works from the first season.

**Anomaly flag:** a ward-day is flagged when it has at least 3 reports, at least 2× its expected share, **and** Poisson p < 0.01. That is, it has far more cases than its modelled share, even if its risk score is lower, which is exactly the proposal's intent. Flags appear in the Reports tab and on the command status strip.

**Post-season recalibration:** `GET /reports/recalibration` returns a proposed H_m per ward, computed as (reported + 10) / (expected + 10). The pseudo-cases shrink small counts toward 1, and the result is clamped to 0.8–1.2.
- **Evidence threshold:** a change is proposed **only where the season's count differs significantly from expected** (two-sided Poisson p < 0.05), so noise alone never moves a factor.
- **Never applied automatically** (`auto_apply_recalibration: false`). The authority reviews it, and if accepted records it in `data/manual/ward_attributes.csv` with a changelog entry.

**Demo data:** "Add synthetic demo reports" seeds **69 synthetic cases**, the number of heatstroke cases reported in Ahmedabad in May 2024. They're spread over days by city risk and over wards by population × risk, plus a **planted cluster in Vatva on 23–24 May**. Everywhere it appears, the data is labelled synthetic.

**Result on the synthetic data:** the flag catches exactly the planted cluster (6 reports vs 0.2 expected on 23 May; 7 vs 0.3 on 24 May), with no false flags. Recalibration proposes a change only for Vatva (13 reported vs 1.2 expected → H_m 1.2).

An earlier version of my synthetic generator shared cases between wards with a different rule than the flag uses. That produced false "over-reporting" in Lambha and Odhav. The generator now uses the same rule, and the significance threshold was added to recalibration.

## Privacy note

Written against the principles of India's **Digital Personal Data Protection Act, 2023**: purpose limitation, data minimisation, storage limitation, security safeguards and accountability.

| Question | Answer |
|---|---|
| What is collected? | Ward, date, age band (5 bands), severity (3 levels), outcome (3), reporter role (5). **No name, phone number, address, patient ID, exact age or free text.** |
| How is it stored? | **Only as counts** per ward × day × age band × severity × outcome × role (`report_counts`). A submission increments a count; there is no per-case record to retrieve, correct or leak. |
| What is shown? | Ward-day totals, expected shares and flags. Breakdowns by age, severity and outcome aren't exposed by the API. Small cells (e.g. "one death aged 60+ in a ward on one day") could still identify someone locally, so they must stay internal. |
| Purpose | Early warning during heat events and seasonal recalibration of the risk model. Nothing else. |
| Retention | Season counts are kept for recalibration. Access and processing logs (the audit log) are kept for at least one year, as the DPDP Rules 2025 require of logs. A deployment should set a period after which counts older than N seasons are deleted. |
| Access | Submitting reports and seeding data are write actions: set `HEAT_API_TOKEN` so only authorised staff can submit. A real deployment needs per-user accounts. |
| Synthetic data | Stored with `synthetic = 1` and labelled in every view. |

## Not done / limitations

- **No real reports yet.** Flags and recalibration are shown on synthetic data. The method is ready for the 2027 season.
- **No WhatsApp report flow.** The optional WhatsApp route in the plan isn't built; health workers use the web form, which works on phones.
- **Hospital beds / ambulances lever not included.** The hospital capacity factor is switched off until private-bed data exists (Phase 6), so a beds lever would change nothing.
- **Cool roofs and outdoor workers still lack data**, so those levers and indicators stay neutral.
- **No side-by-side before/after map.** The simulator shows a per-ward change table and a before/after risk chart instead.

## Sources

- Ziter CD, Pedersen EJ, Kucharik CJ, Turner MG (2019). Scale-dependent interactions between tree canopy cover and impervious surfaces reduce daytime urban heat during summer. *PNAS* 116(15):7575–7580. https://www.pnas.org/doi/10.1073/pnas.1817561116
- Digital Personal Data Protection Act, 2023 (PRS summary): https://prsindia.org/billtrack/digital-personal-data-protection-bill-2023; DPDP Rules 2025 (PIB): https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf
- Heatstroke cases in Ahmedabad, May 2024 (69): see `data/manual/backtest_event.md` (news source; primary source still to be confirmed).
