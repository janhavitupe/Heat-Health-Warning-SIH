# Demo Script (about 6 minutes)

A replay of the **May 2024 Ahmedabad heatwave**, shown as if the system had been running then. It covers all six innovations. Every number below is what the app actually shows on the demo database.

## Before the demo (10 minutes)

```
python scripts/demo_setup.py                               # demo.db: alerts drafted, 69 synthetic reports, scripted approvals; report card
set HEAT_DB=data/api/demo.db                               # PowerShell: $env:HEAT_DB="data/api/demo.db"
uvicorn api.main:app --port 8000
```

- **Browser:** open `http://127.0.0.1:8000/?replay=may2024`, full screen, light mode, zoom 100%.
- **Second tab:** have the report card open at `http://127.0.0.1:8000/report-card?replay=may2024`, or use the file `docs/report_card_may2024.pdf`.
- **Live approval in step 5:** `demo_setup.py` approves every event alert except the **first Red alert (17 May, Baherampura and Indrapuri)**, which it leaves as a draft for you to approve on stage. To rehearse again, re-run `python scripts/demo_setup.py --no-pdf`.
- **Offline:** the basemap needs the internet. If the network fails, play the backup recording (see the end of this page). The ward shapes, scores and all panels still work without the basemap.
- **Delivery:** stays **Simulated** (the grey badge top right). Never switch to Twilio on stage unless the authority's test phones are registered.

## Script

| Time | Screen and clicks | What to say |
|---|---|---|
| 0:00 | Map, day slider on **Wed 15 May**. All wards Green | "This is Ahmedabad's 48 wards on 15 May 2024. Everything is Green. We are replaying that year's heatwave as if the system had been live." |
| 0:30 | Click **Thu 16 May**. Map layer → **Chance of Red** | "**Innovation 2, probabilistic alerts.** On the 16th, forecasts issued three to five days earlier already give Baherampura, Indrapuri and Odhav a **67% chance of Red**. IMD's red alert came four days later, on the 20th. Wards turn Yellow and Orange." |
| 1:00 | Click **Fri 17 May** → click **Baherampura** → *Ward* | "On the 17th, two wards go Red. Every score explains itself: whole-body heat stress, hot nights, consecutive hot days, and vulnerability: slum share and distance to care." |
| 1:30 | Scroll *Why this score* to **Heat-trapping sheet roofs** (or open **New Wadaj** on 23 May: +5.7 points) | "**Innovation 1, indoor heat.** Metal and asbestos sheet roofs keep homes hot at night. We estimate their share per ward from the census. In New Wadaj it adds almost 6 points on hot nights. Estimates are labelled as estimates." |
| 2:00 | Ward detail → **Safe work hours** (23 May, Baherampura) | "**Innovation 4, safe work windows.** Using the ACGIH standard: moderate outdoor work is **not advised 09:00–15:00**, and heavy work needs long rest breaks. The system issues these to labour contractors and the municipal workforce." |
| 2:30 | Map layer → **Cooling access gap** (numbered markers = recommended new sites; status strip: *Cooling deserts: 8*) | "**Innovation 5, cooling deserts.** Using the real street network, 70% of residents live within a 15-minute walk of a cooling option. Eight wards are cooling deserts, including Vatva, Lambha and Baherampura. The system proposes new sites: the top site in Baherampura brings about **20,000 more people** within a 15-minute walk." |
| 3:15 | Tab **Alerts** → open the **Red draft for 17 May** | "Nothing goes out without a person. The system drafts the alert in English, Hindi and Gujarati for SMS, WhatsApp and a voice call, and checks message length. The officer edits, approves or rejects, and every action is logged with their name." Click **Approve**, then **Dispatch**: "Here delivery is simulated. With a Twilio or telecom account the same button sends SMS and places voice calls." Optionally play the voice preview. |
| 4:00 | Click **Thu 23 May** → tab **Reports**; point at the red flag on the status strip | "**Innovation 6, the feedback loop.** ASHAs and health centres report cases, as counts only, with no names or numbers. On 23 May, **Vatva** reports 6 cases where its share would be 0.2. Vatva is ranked 20th by the model, so this flag catches something the model under-rates. *These demo reports are synthetic and labelled so.*" |
| 4:45 | Click **Baherampura** on the map first (the selected ward is pre-filled), then tab **What-if** → trees +10, cool roofs 50% → **Run** | "**Innovation 3, the what-if simulator.** Plant trees and paint half the sheet roofs in Baherampura: over the same heatwave this avoids **2 Red days** in that ward. That is an upper bound, and every assumption is listed. A planner can compare options before funding them." |
| 5:30 | Second tab: **Report card** | "After every event, a one-page report card. It covered 4 of 5 IMD red-alert days, gave 4 days of warning, flagged 232 of 350 Red ward-days three to five days ahead, and missed none of the Heat Action Plan's Orange or Red days. Limitations are printed on the card itself." |
| 6:00 | Tab **Method** | "Every formula and weight is on screen, read live from the settings, with the data sources and what we don't yet know. Model estimates, not clinical predictions." **End.** |

## If something goes wrong

| Problem | Fix |
|---|---|
| Map tiles don't load | Carry on: ward shapes and all panels still work. Mention "basemap needs the internet". |
| Alerts tab empty | Run `python scripts/demo_setup.py --no-pdf` and reload. |
| "Replay not built" | Run `python -m api.cli replay` (about 1 minute) before the demo, then `demo_setup.py`. |
| Server stopped | Re-run `uvicorn api.main:app --port 8000` with `HEAT_DB` set. |

## Rehearsal

An automated run-through of every step (headless Chrome, 27 Sep 2026) found each screen and number as described, with no page errors. A live rehearsal with a timer, and ideally someone new to the project, is still needed.

## Backup recording

**Not yet recorded.** Record the full run once with a screen recorder (Windows: Win+Alt+R with Xbox Game Bar, or OBS) at 1920×1080, and keep the file on the laptop and a USB drive.
