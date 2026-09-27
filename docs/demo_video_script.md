# Demo Video Script (about 11 minutes)

A detailed, recorded walkthrough of every feature. The short live pitch is in [demo_script.md](demo_script.md).

Each scene lists:
- **Do:** the exact clicks;
- **Check:** what should be on screen before you speak, so you can pause if it isn't;
- **Say:** the narration, which you can read word for word.

Timings are approximate.

---

## Before recording

### Setup (once)

1. **Start the demo server** (terminal 1):
   ```
   cd D:\heat
   $env:HEAT_DB="data/api/demo.db"
   .venv\Scripts\python -m uvicorn api.main:app --port 8000
   ```
2. **Reset the demo data** (terminal 2). This puts the 17 May Red alert back to Draft and reloads the synthetic reports:
   ```
   cd D:\heat
   .venv\Scripts\python scripts\demo_setup.py --no-pdf
   ```
3. **Set up Chrome:**
   - Open a new window and maximise it; don't use full-screen, so the address bar stays visible for the report-card scene. Zoom 100%, light mode.
   - Close other tabs and turn on Do Not Disturb, so no notifications appear in the video.
   - Tab 1: `http://127.0.0.1:8000/?replay=may2024`
   - Tab 2: `http://127.0.0.1:8000/report-card?replay=may2024`
4. **In tab 1,** open **Alerts** once and type your name in the officer box. It's remembered, so you won't have to type it while recording. Then click **Ward** to go back.
5. **Recorder:**
   - **OBS Studio** (free): Display Capture, 1920×1080, 30 fps, MP4. Record the microphone too.
   - **Or Xbox Game Bar:** press **Win+Alt+R** to start and stop. It records only the active window.
6. **Microphone:** use a headset mic, in a quiet room. Do one 10-second test recording and listen back.

### Tips

- **Pause after each click** until the screen settles (1–2 seconds), then speak.
- **Move the mouse slowly** and point at what you're talking about.
- **Mistakes:** pause, then repeat the whole sentence and cut the mistake later. Or record scene by scene and join the clips.
- **Timing:** if a scene runs long, keep going. Accuracy matters more than speed.
- **Reset between takes:** run the reset command (step 2) and reload the page with **Ctrl+F5**.

---

## Part 1 — Introduction

### Scene 1 · Title (0:00, about 20 s)
**Do:** Show tab 1 with the map on **15 May**. If you want a title slide, show it here instead.
**Say:**
> "This is the Heat-Health Early Warning Platform, for Smart India Hackathon 2026, problem statement 26083. In this video I'll walk through the working prototype, built for the 48 municipal wards of Ahmedabad."

### Scene 2 · The problem (0:20, about 35 s)
**Do:** Nothing; keep the map on screen. Slowly circle the city with the mouse.
**Say:**
> "Heatwaves kill quietly. In May 2024, Ahmedabad crossed 46 degrees and reported 69 heatstroke cases. City-wide temperature alerts treat every neighbourhood the same. But risk depends on who lives where: slum housing, metal roofs, and how far people are from health care and cooling. Our platform turns weather forecasts into ward-level risk, early warnings and concrete actions, with a human officer approving every alert."

---

## Part 2 — Reading the map

### Scene 3 · The command screen (0:55, about 35 s)
**Do:**
1. Point at the map, then the right-hand panel, then the status strip under the title.
2. Point at the **"May 2024 replay"** button, then at the day bar at the bottom.
3. Click **Wed 15** in the day bar.

**Check:** the status strip says **48 Green**.
**Say:**
> "This is the command screen. On the left, a map of the 48 wards. On the right, the detail panel. Across the top, the status strip shows how many wards are at each level, whether a heatwave is under way, cooling deserts, and alerts waiting for review. We're replaying the May 2024 heatwave exactly as the system would have seen it. On the fifteenth of May, every ward is green."

### Scene 4 · Innovation 2: probabilistic early warning (1:30, about 40 s)
**Do:**
1. Click **Thu 16** in the day bar.
2. Open **Map layer** and choose **Chance of Red**.
3. Point at the dark wards in the east: Baherampura, Indrapuri, Odhav.

**Check:** the strip shows **32 Yellow, 16 Orange**. The legend is "Chance of Red", with the darkest wards at 50–70% or more.
**Say:**
> "Move to the sixteenth. Wards turn yellow and orange. Now I switch the map to Chance of Red. These probabilities come from forecasts issued three to five days earlier by three global weather models: ECMWF, GFS and ICON. Baherampura, Indrapuri and Odhav already show a sixty-seven percent chance of reaching red. The official IMD red alert came four days later, on the twentieth."

### Scene 5 · How a risk score is built (2:10, about 45 s)
**Do:**
1. Click **Fri 17** in the day bar.
2. Change **Map layer** to **Heat stress (HTSI)** and pause 3 seconds.
3. Change it to **Vulnerability (PVI)** and pause 3 seconds.
4. Change it back to **Mortality risk (MRI)**.

**Check:** the strip shows **2 Red**.
**Say:**
> "Each ward's mortality risk combines three parts. First, heat stress, from three body-heat indices: UTCI, wet bulb globe temperature and the heat index. Points are added for hot nights, consecutive hot days and heat-trapping roofs. Second, vulnerability, from slum share, walking distance to health care, access to cooling, and population density. Third, a local history factor. The colours follow the IMD scheme of green, yellow, orange and red."

---

## Part 3 — One ward in detail

### Scene 6 · Every score explains itself (2:55, about 35 s)
**Do:**
1. Click the **All wards** tab, then click the **Baherampura** row. The panel switches to its detail.
2. Point at the four score boxes, then scroll to **Why this score** and point along the bars.

**Check:** the panel header is **Baherampura · Friday, 17 May 2024**, and the risk box is Red.
**Say:**
> "Clicking a ward opens its detail. Baherampura turns red on the seventeenth. Every score explains itself. This chart shows how many points each factor adds, and each factor is labelled as live data, census data, or an estimate. So an officer can see *why* a ward is red, not just that it is red."

### Scene 7 · Innovation 1: indoor heat from sheet roofs (3:30, about 30 s)
**Do:**
1. Click **Thu 23** in the day bar.
2. Click **All wards**, then **New Wadaj**.
3. In **Why this score**, point at **Heat-trapping sheet roofs (indoor heat)** and its "Estimate" tag.

**Check:** that row shows about **+5.7**.
**Say:**
> "Innovation one is indoor heat. Metal and asbestos sheet roofs keep homes hot through the night. We estimate each ward's sheet-roof share from census 2011 data, and it's clearly labelled as an estimate. In New Wadaj on the twenty-third, sheet roofs add almost six points on a hot night."

### Scene 8 · Actions and Innovation 4: safe work hours (4:00, about 40 s)
**Do:**
1. Scroll down to **What to do** and point at the department names.
2. Scroll to **Safe outdoor work hours**.
3. Click **New to the heat**, then **Acclimatized** again.

**Check:** the Moderate line says **"not advised 09:00–15:00"**.
**Say:**
> "Below the explanation, the system lists actions from the Ahmedabad Heat Action Plan, for each department. Then innovation four: safe outdoor work hours. Using the ACGIH occupational heat standard, moderate outdoor work is not advised from nine in the morning to three in the afternoon, with rest breaks on either side. Stricter limits apply to workers who are new to the heat."

### Scene 9 · Advisories in three languages (4:40, about 25 s)
**Do:** Scroll to **Public advisories**. Click the language buttons: English, then Hindi, then Gujarati.
**Say:**
> "Public advisories are drafted automatically in English, Hindi and Gujarati, for SMS, WhatsApp and voice calls. They're filled in with the ward's hottest hour and its nearest cooling places. The Hindi and Gujarati texts are drafts that still need review by native speakers."

### Scene 10 · Charts (5:05, about 20 s)
**Do:** Scroll slowly through **Risk over the event**, **Chance of each alert level**, **Through the day**, and **Vulnerability breakdown**.
**Say:**
> "Further down: the risk over the whole event with a forecast uncertainty band, the chance of each alert level, the hour-by-hour heat curve, and a breakdown of vulnerability."

### Scene 11 · Healthcare view (5:25, about 25 s)
**Do:**
1. At the top, click **Healthcare**. The map switches to hospitalization risk.
2. Point at the layer description.
3. Click **Municipal** to switch back.

**Say:**
> "The healthcare view switches the map to hospitalization risk, for hospitals and health centres planning beds and staff. Hospital capacity is switched off for now, because private hospital beds are missing from the data, and the screen says so. Back to the municipal view."

---

## Part 4 — Planning for the city

### Scene 12 · All wards, ranked (5:50, about 15 s)
**Do:** Click **All wards** and scroll the list slowly.
**Say:**
> "The all-wards list ranks every ward by risk, with heat stress, vulnerability, temperature and chance of red side by side, so officers can see where to act first."

### Scene 13 · Plan for the day (6:05, about 25 s)
**Do:** Click **Plan**. Point at **City-wide measures**, then **Where to act first**, then scroll to **Resource allocation**.
**Say:**
> "The Plan tab turns scores into a plan for the day: city-wide measures for the current alert level; wards in priority order, with their main drivers and actions; and a resource allocation that places cooling units and ambulances where they reach the most people at risk."

### Scene 14 · Innovation 5: cooling deserts (6:30, about 30 s)
**Do:**
1. Change **Map layer** to **Cooling access gap**.
2. Point at the darkest wards, then at the small dots (existing cooling places) and the numbered markers (recommended sites).
3. Point at **"Cooling deserts: 8"** in the status strip.

**Say:**
> "Innovation five is cooling deserts. Using the real street network, we measured who can walk to a cooling place, such as a health centre, library or park, within fifteen minutes. Seventy percent of residents can. Eight wards are cooling deserts, and the numbered markers show the recommended sites for new cooling centres."

**Then:** set **Map layer** back to **Mortality risk (MRI)**.

---

## Part 5 — Alerts with a human in control

### Scene 15 · The alert queue (7:00, about 15 s)
**Do:** Click **Alerts**. Point at the sentence "Nothing is sent until an officer approves…", then at the list.
**Say:**
> "Now, alerts. Drafts are created automatically whenever wards reach orange or red. Nothing is sent until a named officer approves and dispatches it."

### Scene 16 · Reviewing an alert (7:15, about 30 s)
**Do:**
1. Click the row **2024-05-17 · Red · 2 · Draft**.
2. Point at the ward chips, then Audiences, Languages and Channels.
3. Click the **Hindi** and **Gujarati** message buttons to show the text.
4. Point at the **CAP XML** link. Don't click it.

**Say:**
> "Opening the red alert for the seventeenth. The officer sees the wards, audiences, languages and channels, and can edit the message. Placeholders are filled in for each ward, and message length is checked in every language before approval is allowed. Each alert is also exported in the international Common Alerting Protocol format."

### Scene 17 · Approve and dispatch (7:45, about 25 s)
**Do:**
1. Check your name is in the officer box.
2. Click **Approve**.
3. Click **Dispatch (simulated)**, then **OK** in the confirmation.
4. Scroll to **Deliveries** and **Audit trail**.

**Check:** the status says **Dispatched**, the deliveries are marked **simulated**, and the audit trail shows your name.
**Say:**
> "The officer approves, then dispatches. In this demo delivery is simulated, so nothing reaches real phones. Every message is recorded with its status, and the audit trail logs who did what, and when."

### Scene 18 · Residents can ask on WhatsApp (8:10, about 35 s)
**Do:**
1. Click **← All alerts**.
2. Click **Resident WhatsApp preview**.
3. Type `Baherampura` and click **Send**.
4. Type `Vatva gujarati` and click **Send**.

**Check:** the first reply starts with **"RED heat alert for Baherampura on Fri 17 May"**, the alert you just approved. The second is in Gujarati.
**Say:**
> "Residents can also ask. A resident sends their ward name on WhatsApp and gets the alert an officer has approved, in their own language. This preview runs the same bot code; with a registered WhatsApp business sender, it answers real phones. The bot never shares anything an officer hasn't approved."

---

## Part 6 — Learning from the ground

### Scene 19 · Innovation 6: health-worker feedback (8:45, about 40 s)
**Do:**
1. Click **Thu 23** in the day bar, if it isn't already selected.
2. Click the **Reports** tab.
3. Point at the form fields, then at **"Case reports above expected: Vatva (6 vs 0.2)"** in the status strip.
4. Scroll to **Wards with more cases than expected**.

**Say:**
> "Innovation six is the feedback loop. ASHA workers and health-centre staff report suspected heat illness through this form. Reports are stored only as counts, with no names or phone numbers. On the twenty-third, Vatva reports six cases where its expected share is only point two. Vatva ranks twentieth in the model, so this flag catches something the model under-rates. These demo reports are synthetic, and labelled as such."

### Scene 20 · Learning after the season (9:25, about 15 s)
**Do:** Scroll to **Post-season recalibration (proposal only)**.
**Say:**
> "After the season, the system proposes adjustments to each ward's local risk factor, only where the evidence is statistically significant. It never applies them automatically."

---

## Part 7 — Planning ahead

### Scene 21 · Innovation 3: what-if simulator (9:40, about 40 s)
**Do:**
1. Click **All wards**, then **Baherampura**, so it's the selected ward.
2. Click **What-if**. Baherampura is pre-filled, and tree cover is set to +10.
3. Drag **Cool roofs** to **50%**.
4. Click **Run scenario** and wait about 1 second.
5. Point at the result boxes, the before/after chart, and the assumptions.

**Check:** the result says **Red ward-days avoided** and is labelled **Scenario estimate**.
**Say:**
> "Innovation three is the what-if simulator. A planner picks Baherampura, adds ten points of tree cover, paints half of the sheet roofs, and re-runs the whole heatwave in about a second. Red days are avoided. The assumptions are listed, and results are labelled as scenario estimates, an upper bound for comparing options before funding them. A new cooling centre can be tested the same way."

---

## Part 8 — Evidence and honesty

### Scene 22 · Post-event report card (10:20, about 40 s)
**Do:**
1. Switch to **tab 2** (the report card) and press **F5**.
2. Point at the four top boxes, the timeline, **Checks against observations**, **Health-worker reports** and **Alerts and actions**.
3. Scroll to **Limitations**.

**Say:**
> "After every event, the system produces a one-page report card. For May 2024: all 48 wards reached red. Four of the five IMD red-alert days had a red ward. There were four days of warning before the IMD alert. Two hundred and thirty-two of three hundred and fifty red ward-days were flagged three to five days ahead. And all eleven days the Heat Action Plan rated orange or red were caught, with none missed. The limitations are printed on the card itself."

### Scene 23 · Method and limitations (11:00, about 20 s)
**Do:** Go back to **tab 1** and click **Method**. Scroll through the weights tables, **How well it worked**, **Data sources**, and **Limitations**.
**Say:**
> "The Method tab shows every formula and weight, read live from the system settings, along with data sources and limitations. These are model estimates, not clinical predictions."

### Scene 24 · Live mode (11:20, about 20 s)
**Do:** At the top, click **Live**. Point at "Live forecast · updated …" and the day bar.
**Say:**
> "In live mode, the system refreshes the forecast every day using a 122-member ensemble. Today, at the end of September, every ward is green, which is correct outside the heat season."

### Scene 25 · Closing (11:40, about 25 s)
**Do:** Click **May 2024 replay**, then **Sun 26** (the peak day, all Red). Leave the map on screen.
**Say:**
> "To sum up: ward-level risk that explains itself, probabilistic early warning, indoor heat, safe work hours, cooling deserts, a what-if simulator, and a feedback loop from health workers, with a human officer in control of every alert. Thank you."

---

## After recording

- **Trim** the start and end. The free Clipchamp editor in Windows or DaVinci Resolve work well.
- **Optional:** add a title card at the start and a card at the end with team names and the GitHub link.
- **Optional:** add captions. Clipchamp can generate them automatically; check the ward names by hand.
- **Export** as MP4, 1080p. Keep a copy on a USB drive as the backup for the live demo.
- **Reset the demo afterwards** so the 17 May alert is a draft again: `.venv\Scripts\python scripts\demo_setup.py --no-pdf`

## If something doesn't match

| On screen | Fix |
|---|---|
| The 17 May alert already says "Dispatched" | Run the reset command and press Ctrl+F5 |
| The WhatsApp reply shows 30 May, not 17 May | You haven't approved 17 May yet (scene 17) |
| The map background is blank | Internet is down. Wards and panels still work, so carry on |
| The what-if says "2 wards affected" | Another ward was also selected. Click ✕ on the extra ward chip and run again |
| A page shows an error | Check the server terminal is still running, then Ctrl+F5 |
