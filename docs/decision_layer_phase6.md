# Decision Layer (Phase 6)

Phase 6 turns risk scores into decisions: what each department should do, when outdoor work is safe, where cooling is out of reach and new cooling centres should go, how to share scarce resources, and what to tell the public. Each design choice below comes with its evidence.

Code: [heatrisk/work_windows.py](../heatrisk/work_windows.py), [cooling.py](../heatrisk/cooling.py), [actions.py](../heatrisk/actions.py), [allocation.py](../heatrisk/allocation.py), [advisories.py](../heatrisk/advisories.py); rules and templates in [resources/](../resources/); API in [api/decisions.py](../api/decisions.py).

---

## 1. Safe work windows (Innovation 4)

**Method:** each hour's outdoor WBGT is compared with the ACGIH heat-stress limits already in `config.yaml` (verified against the 2026 table reproduced by CCOHS). Each limit applies to the share of a work/rest cycle spent working, read per hour as is usual in practice:

| Work share | Advice |
|---|---|
| 75–100% | normal work |
| 50–75% | 15 min rest per hour |
| 25–50% | 30 min rest per hour |
| 0–25% | 45 min rest per hour |
| above every limit | not advised |

Schedules cover working hours 06:00–20:00 and merge consecutive hours, for example *"Heavy work: not advised 08:00–16:00; 45 min rest per hour 07:00–08:00…"*.

**Acclimatization:** the stricter Action Limit (for unacclimatized workers) is suggested for the **first 3 days of a detected heatwave event**. NIOSH and OSHA say workers need up to 14 days to adapt to heat and that new or returning workers should start at 20% of a normal day. A sudden heatwave pushes even local workers beyond what they're used to. Officials can switch the mode in the app.

**Example:** on 23 May 2024 (peak WBGT 32.4 °C), heavy work is not advised from 08:00 to 16:00 for acclimatized workers, and from 07:00 to 18:00 in the first days of a heatwave.

**Limitation:** WBGT is computed for full sun, so work in shade is less restricted.

## 2. Cooling access, cooling deserts and new sites (Innovation 5)

**What counts as a cooling option.** The Ahmedabad Heat Action Plan activates "cooling centers, such as temples, public buildings, malls", expands shaded areas, and hands out water at temples, mosques and BRTS stations. So there are two tiers:

| Tier | Places | Use |
|---|---|---|
| AMC-controlled (main measure) | libraries, ward offices, 70 Urban Health Centres (geocoded), 5 public hospitals, parks, drinking water, BRTS stations | cooling gap, deserts, PVI |
| Community (sensitivity only) | temples, mosques, malls | shows how much they would add |
| Candidates for new centres | schools, community centres | site selection |

**Walking access.** Distances are measured along the OpenStreetMap street and footpath network (60,000 nodes), from each of 47,622 populated 100 m WorldPop cells. The cell populations are rescaled to the ward totals. This replaces the OSRM server in the plan: same data, routed in Python, no Docker.
- **Walking speed:** 4.0 km/h (1.1 m/s), so a 15-minute walk is about 1 km. Adults in their 60s and 70s walk at about 1.1–1.3 m/s, and women more slowly (Bohannon & Andrews 2011, 23,111 people).

**Results:**
- **30.5% of residents** live more than a 15-minute walk from an AMC cooling place (26.2% if temples, mosques and malls count).
- **8 cooling deserts** (most residents beyond the walk): Sarkhej, Lambha, Maktampura, Nikol, Baherampura, Ramol-Hathijan, Vatva, Gota. Mostly edge wards, plus dense Baherampura.
- **Top 5 new sites** by greedy maximum coverage of vulnerability-weighted people, bringing about 68,000 people newly within a 15-minute walk: first in Baherampura (+20,000 people), then Amraiwadi, Ghatlodia, India Colony and Navrangpura. OpenStreetMap maps only 113 schools while AMC runs several hundred, so read each site as *where* to open a centre, with the named building as the nearest mapped option.

**PVI update.** The access component (weight 0.20) is now split equally, as the phase plan asked ("feed cooling access back into PVI"):
- **Health care (0.10):** population-weighted *walking* distance to the nearest hospital, clinic or UHC. This replaces the straight-line centre-point distance behind the Maktampura artefact noted in Phase 3.
- **Cooling (0.10):** the ward's cooling gap. Heat-vulnerability indices commonly include access to cooling for people without AC.

**Effect on vulnerability ranks:**
- Bodakdev (affluent, west) drops from 7th to 34th.
- Vatva rises from 23rd to 17th.
- Top five: Baherampura, Odhav, Indrapuri, Lambha, Asarwa.

## 3. Action recommendations

**Rule table:** [resources/actions.yaml](../resources/actions.yaml). The wording and departments come from the Heat Action Plan's "departmental wise suggested activities during heatwave days" (Nodal Officer, Health, Labour, 108, Transport/AMTS/BRTS, Schools, Water, Parks, Solid Waste, Real Estate, Electricity, ICDS). There are three kinds of rule:
- **City-wide measures by level**, e.g. Red: bulk SMS, no power cuts, schools closed and used as shelters.
- **Ward measures by level**, e.g. Red: UHCs open till 7 pm, announcements in slums, parks kept open.
- **Driver-specific measures**, each shown with its reason:
  - WBGT ≥ 30.5 °C (heavy work unsafe even at 15 min per hour) → stop outdoor and construction work 12:00–16:00;
  - hot nights → night shelters open all day;
  - top quarter for slums → link-worker outreach;
  - cooling desert → extra or mobile cooling centres;
  - ≥ 3 heat-alert days → pre-position ambulances;
  - hospitalization risk Red → hospital surge protocol.

Stronger rules replace weaker ones at higher levels, so there are no duplicate "Orange" actions on Red days. Probability triggers (P(Red) ≥ 40% within 3 days) map to the plan's Orange preparedness actions.

**Example:** Baherampura on 23 May 2024 gets 12 actions from 9 departments. A Yellow day gets none.

**Priority ranking:** wards are ranked by MRI (municipal view) or HRI (healthcare view), with P(Red) breaking ties.

## 4. Resource allocation

- **Mobile cooling units:** placed one at a time where they bring the most risk-weighted people within a 15-minute walk. The reported number is *coverage*, not how many people a unit can serve in a day.
- **Ambulances:** shared by expected heat-illness demand (population × HRI) with the D'Hondt highest-averages method, so each extra ambulance in a ward is worth progressively less.

Both are tools for discussion, not optimisation against real fleet data.

## 5. Public advisories

- **Formats:** three audiences (public, outdoor workers, elderly and caregivers) × Yellow / Orange / Red × English, Hindi and Gujarati. Each comes as an SMS and a longer WhatsApp text, which also serves as the voice script for Phase 7.
- **Content:** follows the Heat Action Plan's community advice and NDMA heat-wave do's and don'ts. Messages are filled with the ward, day, hottest hour, heavy-work window and nearest named AMC cooling places.
- **SMS limits (tested with the longest ward name):**
  - English: 160 characters, and **GSM alphabet only**, since one non-GSM character (e.g. "…") silently turns an SMS into 70-character Unicode parts;
  - Hindi and Gujarati: 134 characters (two Unicode parts).
- **Translations:** the Hindi and Gujarati text are **drafts written for the prototype**. They're marked "needs native-speaker review" in the API and the app, and must be checked by a native speaker before real use, as the plan requires.

## 6. API and app

- **API endpoints:** `/ward/{id}/actions`, `/ward/{id}/work-windows`, `/ward/{id}/advisories`, `/priorities`, `/cooling`, `/allocation`.
- **App additions:**
  - "What to do", "Safe outdoor work hours" and "Public advisories" in the ward panel;
  - a **Cooling access gap** map layer, with existing places as dots and recommended sites as numbered circles;
  - a **Plan** tab with city-wide measures, the top-10 ward list and the allocation form;
  - URL links: `?layer=cooling`, `?tab=plan`.

## Limitations

- Places of worship in OpenStreetMap are far from complete (179 mapped), so the community-tier sensitivity understates their reach.
- 20 of the 70 geocoded health centres are placed only by ward name, which is approximate.
- Outdoor-worker share is still missing, so worker actions key off WBGT and alert level rather than where workers live.
- Allocation parameters (units, ambulances) are user inputs, not linked to real fleet data.

## Sources

- ACGIH TLV / Action Limit table via CCOHS: https://www.ccohs.ca/oshanswers/phys_agents/heat/heat_control.html
- OSHA, Protecting new workers (acclimatization): https://www.osha.gov/heat-exposure/protecting-new-workers; NIOSH acclimatization: https://www.cdc.gov/niosh/heat-stress/recommendations/acclimatization.html
- Ahmedabad Heat Action Plan 2019 (departmental actions, pp. 13–21): https://www.nrdc.org/sites/default/files/ahmedabad-heat-action-plan-2019-update.pdf
- Bohannon RW, Andrews AW (2011). Normal walking speed: a descriptive meta-analysis. *Physiotherapy* 97(3):182–189. https://pubmed.ncbi.nlm.nih.gov/21820535/
- NDMA heat wave guidance: https://ndma.gov.in/Natural-Hazards/Heat-Wave
