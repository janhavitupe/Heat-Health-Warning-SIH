# Expected Questions and Answers

Short, honest answers for the jury. Details are in [evaluation.md](evaluation.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Validation

**How do you know it works?**
- **What we did:** we replayed the May 2024 heatwave through the full system.
- **Agreement with the city's rule:** it rated as Orange/Red all 11 days that the city's own Heat Action Plan rule (on measured temperature) called Orange/Red, and missed none.
- **Lead time:** it gave 4 days of warning before IMD's red alert.
- **Probabilistic warning:** forecasts 3–5 days ahead flagged 66% of Red ward-days.
- **What that does and doesn't prove:** agreement with official warnings and consistent early warning. It does not prove the model predicts deaths better than current practice.

**Why no correlation with deaths or hospital admissions per ward?**
- **Data:** 2024 heat illness data are published only for the whole city (69 heatstroke cases in May).
- **What would fix it:** anonymous ward-level counts from AMC's health department would let us test ward rankings directly.
- **Already built:** the health-worker feedback loop collects exactly those counts from the first season.

**Isn't one heatwave too little?**
- **Yes, for false-alarm rates.** Replays of the 2016, 2019 and 2022 heatwaves are the next step: the replay tool works for any past date range.

**Your model warns more than the Heat Action Plan. Is that bad?**
- **How often:** it rates one level higher on 7 of 35 quieter days, mostly humid ones.
- **Why it's deliberate:** the plan looks only at temperature. Humidity, hot nights and consecutive hot days are well-established risk factors, and the proposal adds them on purpose.
- **The counterweight:** officers still approve every alert.

## Data gaps

**Which data are missing?**
- **Neutral indicators:** ward-level elderly and outdoor-worker shares. No public source gives age or occupation below city level, and the proxies tested were too weak ([decision](decision_age_worker_data.md)). They are held at the city midpoint, and every explanation says so.
- **Coarse:** children under 5 come from census 2011, averaged by assembly constituency (6.1–9.1% across wards).
- **Hospital capacity:** private hospital beds are missing, so capacity is switched off.
- **Estimates:** sheet-roof shares come from census 2011 rates.

**What would you need from AMC?**
1. The 2011 ward map or number-to-name list, which unlocks census ward data for age, workers and roofs.
2. Anonymous daily heat-illness counts per ward.
3. Private hospital bed counts.
4. Official cooling-centre and water-point locations.

**Why not show a bigger temperature difference between wards?**
- **The evidence:** the airport station shows that the daytime satellite signal makes estimates worse.
- **What we use:** only the night-time adjustment (about 1 °C across wards). Ward differences come mainly from people and housing.
- **What we won't do:** show differences the data doesn't support.

## Clinical and ethical

**Does it predict who will die?**
- **No.** Scores are *model estimates, not clinical predictions*, shown on every screen. They rank wards and time actions.

**Can it send wrong alerts to the public?**
- **Human approval:** nothing is sent without a named officer approving it, and every action is logged.
- **Safe defaults:** delivery is simulated by default. Real sending needs explicit configuration and a registered recipient list.

**Privacy?**
- **Reports are stored only as counts:** ward, day, age band, severity, outcome and role.
- **What's never collected:** names, phones, addresses or free text.
- **Framework:** designed to the principles of India's Digital Personal Data Protection Act, 2023: data minimisation, purpose limitation and audit logs.

**Are the Hindi and Gujarati messages correct?**
- **Status:** they are drafts, flagged for native-speaker review before public use.

## Scale and cost

**Can another city use it?**
- **What changes per city:** the ward boundaries, a Heat Action Plan's thresholds (or IMD's), and census/OSM/satellite data. All of it is public for Indian cities.
- **What stays the same:** the code; city settings live in `config.yaml`. Earth Engine exports and OSM downloads are scripted.
- **Effort:** a few days of data work per city.

**What does it cost to run?**
- **Weather data:** Open-Meteo is free for non-commercial use; government production use needs its paid API plan.
- **Hosting:** one small server (FastAPI + SQLite) handles a city.
- **The main running cost is messaging:** SMS and voice through Twilio or an Indian telecom gateway, priced per message. Get current bulk tariffs before quoting a figure.

**How fast is it?**
- **Daily forecast:** about 4 minutes for 48 wards, including 122 ensemble runs.
- **What-if scenario:** under 1 second.
- **Map views:** load instantly from the database.

## Technical

**Why these weights?**
- **HTSI:** anchored to the Ahmedabad Heat Action Plan thresholds by how rare they are in 30 years of climate data.
- **PVI:** follows the proposal and the CDC Social Vulnerability Index method (percentile ranks).
- **Stability:** rankings barely change if any weight moves ±20% (ρ ≥ 0.978). Every change is logged in `docs/weights_changelog.md`.

**Why three forecast models?**
- **Evidence:** equal-weight ECMWF + GFS + ICON beat any single model or pair in 2024 and in a blind 2025 test.
- **Why each model's errors differ:** GFS runs too windy (understates heat stress) and ICON too calm.
