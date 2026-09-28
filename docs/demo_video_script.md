# Demo Video Script (about 12 minutes)

A recorded walkthrough of every feature, told as one story: **how the May 2024 heatwave would have played out in Baherampura** with this system running. The short live pitch is in [demo_script.md](demo_script.md).

Each scene lists:
- **Do:** the exact clicks;
- **Check:** what should be on screen before you speak, so you can pause if it isn't;
- **Say:** the narration, which you can read word for word.

All numbers were checked against the demo database on 28 September 2026. If you rebuild the data, re-check the **Check** lines.

**Story arc**

| Part | Story beat | Features shown | Time |
|---|---|---|---|
| 1 | The problem | — | 0:00 |
| 2 | Warning before the heatwave | Map, day bar, **Innovation 2** (chance of Red) | 0:50 |
| 3 | Why Baherampura? | Explained scores, **Innovation 1** (roofs), census vulnerability, work hours (**4**), advisories, charts | 2:10 |
| 4 | What the city should do | Healthcare view, ranking, day plan, **Innovation 5** (cooling deserts) | 5:30 |
| 5 | Warning the people | Alert review, human approval, CAP, WhatsApp | 7:10 |
| 6 | Listening to the ground | **Innovation 6** (health-worker reports) | 8:50 |
| 7 | Planning for next summer | **Innovation 3** (what-if) | 9:50 |
| 8 | Proof and honesty | Report card, Method tab, live mode | 10:40 |

---

## Before recording

### Setup (every take)

1. **Terminal 1, start the server:**
   ```
   cd D:\heat
   $env:HEAT_DB="data/api/demo.db"
   .venv\Scripts\python -m uvicorn api.main:app --port 8000
   ```
2. **Terminal 2, reset the demo data.** This puts the 17 May Red alert back to Draft and reloads the labelled synthetic reports:
   ```
   cd D:\heat
   .venv\Scripts\python scripts\demo_setup.py --no-pdf
   ```
3. **Chrome:**
   - Open a new window and maximise it (don't use full-screen). Zoom 100%, light mode.
   - Turn on Do Not Disturb and close other tabs.
   - Tab 1: `http://127.0.0.1:8000/?replay=may2024`
   - Tab 2: `http://127.0.0.1:8000/report-card?replay=may2024`
4. **In tab 1,** open **Alerts** and type your name in the officer box. It's remembered. Then click **Ward**. Press **Ctrl+F5** before you start.
5. **Recorder:** OBS Studio (Display Capture, 1920×1080, 30 fps, MP4, mic on), or **Win+Alt+R**.

### Tips

- **Click, wait 1–2 seconds, then speak.** Point the mouse slowly at whatever you're describing.
- **Record part by part** (8 clips) and join them afterwards. A mistake then only costs one part.
- **Between takes:** rerun step 2 and press **Ctrl+F5**.

---

## Part 1 — The problem (0:00–0:50)

### Scene 1 · Title
**Do:** Show tab 1 on the peak day (the replay opens on **Sun 26**, all wards Red). Optionally show a title slide first.
**Say:**
> "This is the Heat-Health Early Warning Platform, our entry for Smart India Hackathon 2026, problem statement 26083. It's a working prototype for the 48 municipal wards of Ahmedabad."

### Scene 2 · Why wards matter
**Do:** Slowly circle the red city with the mouse.
**Say:**
> "In May 2024, Ahmedabad crossed 46 degrees and reported 69 heatstroke cases. Today's heat alerts are city-wide: one colour for five and a half million people. But heat doesn't hurt everyone equally. It depends on the roof over your head, who lives with you, and how far you are from a doctor or a cool place. We'll follow that heatwave day by day, through one neighbourhood: Baherampura."

---

## Part 2 — Warning before the heatwave (0:50–2:10)

### Scene 3 · The command screen
**Do:**
1. Point at the map, then the right panel, then the status strip.
2. Click **Wed 15** in the day bar.

**Check:** the strip shows **47 Green, 1 Yellow**.
**Say:**
> "This is the command screen: the ward map, a detail panel, and a status strip with ward counts, heatwave status, cooling deserts and alerts waiting for review. We're replaying May 2024 exactly as the system would have seen it. On the fifteenth, the city is calm: forty-seven wards green."

### Scene 4 · Innovation 2: chance of Red
**Do:**
1. Click **Thu 16**.
2. **Map layer → Chance of Red.**
3. Point at the darkest wards in the centre and east.

**Check:** the strip shows **33 Yellow, 15 Orange** and "Heatwave under way". The darkest wards are at 50–70% or more.
**Say:**
> "On the sixteenth, the picture changes. This layer shows the chance of each ward reaching red, from forecasts issued three to five days earlier by three global weather models: ECMWF, GFS and ICON. Baherampura, Danilimda, Asarwa and Shahpur already show a two-in-three chance. The IMD red alert came four days later, on the twentieth."

### Scene 5 · The first Red ward
**Do:**
1. Set **Map layer → Mortality risk (MRI)**.
2. Click **Fri 17**, then click **Baherampura** on the map (south-east of the old city).

**Check:** the strip shows **1 Red**. The panel shows **Baherampura · Friday, 17 May 2024**, risk **83 · Red**.
**Say:**
> "On the seventeenth, one ward turns red first: Baherampura, three days before the official red alert. The whole city had nearly the same temperature, forty-five degrees. So why this ward?"

---

## Part 3 — Why Baherampura? (2:10–5:30)

### Scene 6 · Every score explains itself
**Do:**
1. Point at the six score boxes: risk 83, heat stress 74, vulnerability 66, max 45°, chance of Red 56%.
2. Scroll to **Why this score** and move along the bars.

**Say:**
> "Every score explains itself. Mortality risk combines heat stress, which is how hot it feels to the body, with vulnerability, which is who lives here. Heat stress comes from three body-heat indices: UTCI, wet bulb globe temperature and the heat index. Each factor here shows its points and where its data comes from: live weather, census, or an estimate."

### Scene 7 · Innovation 1: sheet roofs, and hot nights
**Do:** Point at **Hot night** (+8.7), then **Heat-trapping sheet roofs** (+4.1) with its **Estimate** tag.
**Say:**
> "Two factors are about the night. The minimum here stays above thirty degrees, so bodies can't recover. And innovation one, indoor heat: metal and asbestos sheet roofs keep homes hot long after sunset. We estimate each ward's sheet-roof share from census 2011 housing data, and it's labelled as an estimate."

### Scene 8 · Who lives here
**Do:** Point at **Informal housing** (+3.1), **Young children (under 5)** (+2.9), **Far from cooling places** (+2.5) and **Walking distance to health care** (+2.1). Then point at **Elderly** and **Outdoor workers**, "held at city midpoint".
**Say:**
> "Then vulnerability. Baherampura has a large slum population and more young children, measured from census 2011 ward data. Many residents are more than a fifteen-minute walk from a cooling place. We measured that along the real street network, not as a straight line. Two indicators, elderly and outdoor workers, have no ward-level data anywhere, so they're held at the city average, and the screen says so. We'd rather show a gap than invent a number."

### Scene 9 · What to do, and Innovation 4: safe work hours
**Do:**
1. Scroll to **What to do** and point at the departments.
2. Scroll to **Safe outdoor work hours**.
3. Click **New to the heat**, then **Acclimatized**.

**Check:** the Moderate line reads **"not advised 09:00–15:00"**.
**Say:**
> "The ward gets actions from the Ahmedabad Heat Action Plan for each department. And innovation four: safe outdoor work hours, using the ACGIH occupational heat standard. Here, moderate work is not advised from nine to three, with rest breaks around it. Workers new to the heat get stricter limits, because it takes days to acclimatise."

### Scene 10 · Advisories in three languages
**Do:** Scroll to **Public advisories**. Click **English**, **हिंदी**, **ગુજરાતી**, then the audiences (public, workers, elderly).
**Say:**
> "Advisories are drafted automatically in English, Hindi and Gujarati, for the public, outdoor workers, and the elderly and their carers. Each includes the ward's hottest hour and its nearest cooling places. The Hindi and Gujarati texts are drafts that native speakers still need to review."

### Scene 11 · The days ahead
**Do:** Scroll slowly through **Risk over the event**, **Chance of each alert level** and **Through the day**.
**Say:**
> "Further down: risk across the whole event with a forecast uncertainty band, the chance of each alert level, and the hour-by-hour heat curve, so teams know *when* in the day to act, not just which day."

---

## Part 4 — What the city should do (5:30–7:10)

### Scene 12 · Healthcare view
**Do:** Click **Healthcare** at the top, then point at the layer description. Then click **Municipal**.
**Say:**
> "Hospitals see the same city through hospitalization risk. Hospital capacity is switched off for now, because private-hospital bed data is missing, and the screen says so."

### Scene 13 · Ranking and the day plan
**Do:**
1. Click **Thu 23** (peak of the early wave).
2. Click **All wards** and scroll the ranked list.
3. Click **Plan**. Point at **City-wide measures**, **Where to act first** and **Resource allocation**.

**Check:** the strip shows **46 Red, 2 Orange**. Baherampura is at the top of the list.
**Say:**
> "By the twenty-third, forty-six wards are red, so ranking matters. The Plan tab turns scores into a day plan: city-wide measures for the alert level, wards in priority order with their main causes, and where to send cooling units and ambulances to reach the most people at risk."

### Scene 14 · Innovation 5: cooling deserts
**Do:**
1. **Map layer → Cooling access gap.**
2. Point at Baherampura (dark), then the small dots (existing places) and the numbered markers (recommended sites).
3. Point at **"Cooling deserts: 8"** in the strip.

**Say:**
> "Innovation five: cooling deserts. Seventy percent of residents can walk to a cooling place, such as a health centre, library or park, within fifteen minutes. Eight wards are cooling deserts, Baherampura among them. The numbered markers are where the system recommends new cooling centres, chosen to reach the most uncovered people."

**Then:** set **Map layer → Mortality risk (MRI)**.

---

## Part 5 — Warning the people (7:10–8:50)

### Scene 15 · The alert queue
**Do:** Click **Alerts**. Point at "Nothing is sent until an officer approves…", then the list.
**Say:**
> "Whenever wards reach orange or red, alert drafts are created automatically. But nothing is sent until a named officer approves and dispatches it."

### Scene 16 · Review
**Do:**
1. Click the row **2024-05-17 · Red · 1 · Draft**.
2. Point at the ward chip (Baherampura), then audiences, languages and channels.
3. Click the **हिंदी** and **ગુજરાતી** message buttons.
4. Point at **CAP XML**, without clicking it.

**Say:**
> "Here's the first red alert, for Baherampura on the seventeenth. The officer can change wards, audiences, languages, channels and wording. Each message is checked for length in every language before approval is allowed. The alert is also exported in the international Common Alerting Protocol, so it can feed government warning systems."

### Scene 17 · Approve and dispatch
**Do:**
1. Check your name is in the officer box.
2. Click **Approve**, then **Dispatch (simulated)**, then **OK**.
3. Scroll to **Deliveries** and **Audit trail**.

**Check:** the status is **Dispatched**, the deliveries are marked **simulated**, and your name is in the audit trail.
**Say:**
> "Approve, then dispatch. In this demo delivery is simulated, so no real phones are messaged. Every message is recorded, and the audit trail logs who approved what, and when."

### Scene 18 · Residents ask on WhatsApp
**Do:**
1. Click **← All alerts**, then **Resident WhatsApp preview**.
2. Type `Baherampura` and click **Send**.
3. Type `Vatva gujarati` and click **Send**.

**Check:** the first reply starts **"RED heat alert for Baherampura on Fri 17 May"**, the alert just approved. The second is in Gujarati.
**Say:**
> "Residents can also ask. Someone sends their ward name on WhatsApp and gets the alert an officer approved, in their own language. This preview runs the same bot code. With a registered WhatsApp business number, it answers real phones. And it never shares anything an officer hasn't approved."

---

## Part 6 — Listening to the ground (8:50–9:50)

### Scene 19 · Innovation 6: health-worker reports
**Do:**
1. Click **Thu 23**, then the **Reports** tab.
2. Point at the form fields.
3. Point at **"Case reports above expected: Vatva (6 vs 0.2)"** in the strip.
4. Scroll to **Wards with more cases than expected**.

**Say:**
> "Innovation six closes the loop. ASHA workers and health-centre staff report suspected heat illness here. Only counts are stored: no names, no phone numbers. On the twenty-third, Vatva reports six cases where its expected share is point two. The model ranks Vatva only seventeenth that day, so this flag catches what the model misses. These demo reports are synthetic, and labelled so."

### Scene 20 · Learning after the season
**Do:** Scroll to **Post-season recalibration (proposal only)**.
**Say:**
> "After the season, the system proposes adjusting each ward's risk factor, only where the evidence is statistically significant. It never changes the model on its own; an officer decides."

---

## Part 7 — Planning for next summer (9:50–10:40)

### Scene 21 · Innovation 3: what-if simulator
**Do:**
1. Click **All wards**, then **Baherampura**.
2. Click **What-if**. Baherampura is pre-filled, with trees at +10.
3. Drag **Cool roofs** to **50%**.
4. Click **Run scenario**.
5. Point at the result boxes, the before/after chart and the assumptions.

**Check:** the result shows **3 Red ward-days avoided** and **Scenario estimate**.
**Say:**
> "Innovation three is for planning. What if Baherampura gets ten points more tree cover, and half its sheet roofs are painted white? The system re-runs the whole heatwave in about a second: three red days avoided. The assumptions are listed, and the result is labelled a scenario estimate, an upper bound for comparing options before funding them. A new cooling centre can be tested the same way, by clicking the map."

---

## Part 8 — Proof and honesty (10:40–12:00)

### Scene 22 · Post-event report card
**Do:** Switch to **tab 2** and press **F5**. Point at the four top boxes, the timeline, **Checks against observations**, and **Alerts and actions**. Scroll to **Limitations**.
**Say:**
> "After every heatwave the system writes a one-page report card. For May 2024: all forty-eight wards reached red. Four of the five IMD red-alert days had a red ward, with four days of warning before IMD's alert. Forecasts three to five days ahead flagged two hundred and thirty-eight of three hundred and forty-four red ward-days. And all eleven days the city's own Heat Action Plan rated orange or red were caught, with none missed. The limitations are printed on the card itself."

### Scene 23 · Method and limitations
**Do:** Back to **tab 1** and click **Method**. Scroll through the weights, **How well it worked**, **Data sources** and **Limitations**.
**Say:**
> "The Method tab shows every formula and weight, read live from the system's settings, plus every data source and its limits. These are model estimates, not clinical predictions. They are there to help officers decide where and when to act."

### Scene 24 · Live mode
**Do:** Click **Live** at the top. Point at "Live forecast · updated …" and the day bar.
**Say:**
> "In live mode, the forecast refreshes every day with a hundred and twenty-two ensemble runs. Today, at the end of September, every ward is green, which is correct outside the heat season."

### Scene 25 · Closing
**Do:** Click **May 2024 replay**, then **Sun 26** (all Red). Leave the map on screen.
**Say:**
> "Warning days ahead, risk that explains itself, down to the ward and the hour, and a human in control of every alert. Indoor heat, safe work hours, cooling deserts, a what-if simulator, and a feedback loop from health workers. Thank you."

---

## After recording

- **Trim and join** the clips in Clipchamp or DaVinci Resolve.
- **Optional:** title card and an end card with team names and the repository link; auto-captions (check the ward names by hand).
- **Export** MP4 at 1080p. Keep a copy on a USB drive as the live-demo backup.
- **Reset afterwards:** `.venv\Scripts\python scripts\demo_setup.py --no-pdf`

## If something doesn't match

| On screen | Fix |
|---|---|
| The 17 May alert already says "Dispatched" | Rerun the reset and press Ctrl+F5 |
| The WhatsApp reply shows 30 May, not 17 May | The 17 May alert isn't approved yet (scene 17) |
| The what-if says "2 wards affected" | Remove the extra ward chip (✕) and run again |
| The map background is blank | No internet. Wards and panels still work, so carry on |
| Numbers differ from the **Check** lines | The data was rebuilt. Re-check them in the app before recording |
| A page shows an error | Check terminal 1 is still running, then Ctrl+F5 |
