# Decisions: Humid Heat, Hot-Spell Persistence, and Ward Ranking

Two questions came out of the May 2024 backtest ([backtest_may2024.md](backtest_may2024.md)). Both were decided from published research and checked against the backtest. Date: 25 September 2026.

---

## Decision 1 — How should humid, long hot spells count?

### The question

On 19 of 46 days the model rated one level above the Ahmedabad Heat Action Plan, mostly humid days in late May and June (plan Yellow, model Orange). Three things push these days up, and the plan's temperature-only rule counts none of them: humidity (through WBGT and Heat Index), consecutive hot days (persistence points) and warm nights.

### What the research says

| Factor | Evidence | Implication |
|---|---|---|
| **Humidity** | A 445-city, 24-country study found that adding humidity to temperature barely changed predicted daily deaths. If anything, higher humidity went with slightly *lower* mortality: +23% RH gave −1.1% (Armstrong et al., 2019, *EHP*). A cross-disciplinary review explains the gap: physiology shows humidity raises heat strain, but population studies of mostly sedentary, older people who die of heart and kidney strain rarely detect it. Workers facing exertional heat stroke are a separate case (Baldwin et al., 2023, *EHP*). IMD itself began issuing an experimental temperature + humidity heat index in March 2024, though it is not yet validated for India. | Humidity matters most for **people doing physical work**. For death risk in the general population, temperature carries most of the signal. **Keep** WBGT and Heat Index in the model (they drive the outdoor-worker safe-work windows in Phase 6), but don't let humidity alone push the mortality alert up. |
| **Duration of a hot spell** | In 43 US cities, each extra day of a heatwave raised mortality by 0.38%, while each extra 1 °F of intensity raised it by 2.49%, about 6.5 times more (Anderson & Bell, 2011, *EHP*). IMD declares a heatwave only when heatwave-level temperatures last **at least two consecutive days**. | Persistence matters, but only for days that are **themselves** dangerous, and far less than intensity. |
| **Hot nights** | Multi-country studies find hot nights raise mortality independently of daytime heat, by about 10% in one estimate, because the body can't recover overnight. | **Keep** the hot-night points unchanged. |

### Decision

**Consecutive-days points now count only heat-alert-level days:** base score ≥ 60 (Very High, roughly the plan's Orange / Tmax ≈ 43 °C), instead of ≥ 41 (High). Humidity indicators and hot-night points are unchanged. Config: `htsi.persistence.min_base_score: 60`.

### Effect on the May 2024 backtest

| | Before | After |
|---|---|---|
| Same level as the Heat Action Plan | 26 of 46 days (57%) | **34 of 46 (74%)** |
| Within one level | 44 (96%) | 45 (98%) |
| Model higher than the plan | 19 | 11 |
| Plan Yellow/White days rated Orange/Red | 13 | **4** |
| Plan Orange/Red days caught (Orange or Red) | 11 of 11 | **11 of 11** |
| Lead time before IMD red alert (days at Orange+) | 3 | 3 |
| IMD red days (20–24 May) with any ward at Red | 4 of 5 | 3 of 5 (22–24 May) |

- **Gained:** far fewer extra alerts, and still no missed dangerous day. Red now falls on 22–24 and 26–28 May, close to the plan's own Red days (22–24 and 27 May).
- **Lost:** 21 May (airport 44.4 °C, a plan Orange day) no longer has any ward at Red. It is still Orange in all 48 wards.
- **Still higher than the plan:** 11 days, mostly Yellow → Orange on muggy days, plus 26 and 28 May (Red after several heat-alert days in a row).

---

## Decision 2 — Is the worst-ward list right?

### What the model said

At the May 2024 peak, the highest-risk wards were Odhav, Amraiwadi, **Maktampura**, Viratnagar and Gomtipur. **Vatva** ranked near the bottom.

### What independent evidence says

| Source | Finding | Agrees with the model? |
|---|---|---|
| PDEU ward-level Relative Heat Risk Index (Kela, Kandya & Patel, Pandit Deendayal Energy University, reported April 2026). Built from satellite surface temperature, green cover and population density. | 16 "critical" eastern wards. Highest: **Viratnagar**, Dariapur, **Amraiwadi**, Indrapuri, Maninagar. Lowest: Gota, **Maktampura**, Sarkhej. | ✅ Eastern wards on top (Viratnagar, Amraiwadi). ❌ **Maktampura**: their third-safest, our third-worst. |
| Ahmedabad Slum Free City Action Plan (AMC, 2014; 2010–11 slum survey) | 727,934 slum residents (13% of the city). The **South zone** (Vatva, Danilimda, Behrampura, Isanpur, Lambha) has the largest share: 26.6%. | ❌ Suggests Vatva should rank higher. |
| Kaushal & Nair (2024) on Ahmedabad's industrial areas | **Vatva** is a GIDC industrial estate and a major resettlement site for displaced slum dwellers, with many small garment and textile workshops. | ❌ Suggests Vatva should rank higher. |
| Heat Action Plan background (Knowlton et al., 2014) | The most vulnerable groups are migrant slum residents, the elderly and outdoor workers (construction, rickshaw drivers). | Explains why the missing slum and worker data matter. |

### Why the two outliers happen (checked in the data)

- **Maktampura (AMC-34)** is the 5th-largest ward (25.6 km²). Its centre falls in open land 3.3 km from the nearest hospital, the largest distance in the city. The "healthcare access" indicator is a straight line from the ward's centre, which is unfair to large wards. That one number gives Maktampura the city's highest vulnerability score. The PDEU index uses no hospital data, so it rates the ward low.
- **Vatva (AMC-47)** is close to hospitals (0.4 km, 18 in the ward) and has moderate density. Its slum share and outdoor-worker share, where it would score high, are **missing**, so the model can't see them.

### Decision

1. **Accept the eastern-ward ranking.** It matches an independent study.
2. **Do not edit ward scores by hand.** Adjusting individual ward results would break the rule that every score is explained by its inputs (and the Phase 3 rule: "adjust thresholds, not individual ward results"). Fix the causes instead.
3. **Fix Vatva's cause next: fill in slum data.** The Slum Free City Action Plan's annex lists every slum with its **ward name and number of huts**. Matching those ward names to today's wards gives an `informal_housing_share` estimate without waiting for the census 2011 crosswalk.
4. **Mark Maktampura's rank as provisional until the hospital-access measure is fixed.** Phase 6 replaces centre-point distance with population-weighted walking time. A quicker interim option is population-weighted distance from the WorldPop grid, which is already in Earth Engine.

The sensitivity analysis supports this. The hospital-access weight is the setting that moves ward rankings most (ρ 0.94 at ×0.8), because it's one of only two vulnerability indicators with real data.

---

## Sources

- Armstrong B, et al. (2019). The role of humidity in associations of high temperature with mortality: a multicountry, multicity study. *Environmental Health Perspectives* 127(9):097007. https://ehp.niehs.nih.gov/doi/full/10.1289/EHP5430
- Baldwin JW, Benmarhnia T, Ebi KL, Jay O, Lutsko NJ, Vanos JK (2023). Humidity's role in heat-related health outcomes: a heated debate. *Environmental Health Perspectives* 131(5). https://ehp.niehs.nih.gov/doi/10.1289/EHP11807
- Anderson GB, Bell ML (2011). Heat waves in the United States: mortality risk during heat waves and effect modification by heat wave characteristics in 43 U.S. communities. *Environmental Health Perspectives* 119:210–218. https://pubmed.ncbi.nlm.nih.gov/21084239/
- Hot nights and mortality, multi-country analysis in 178 locations (2025). *Environment International*. https://www.sciencedirect.com/science/article/pii/S0160412025004702
- No reprieve: extreme heat at night contributes to heat wave mortality (2023). *Environmental Health Perspectives* 131(7). https://ehp.niehs.nih.gov/doi/full/10.1289/EHP13206
- India Meteorological Department. Heat wave criteria (FAQ). https://internal.imd.gov.in/section/nhac/dynamic/FAQ_heat_wave.pdf
- IMD experimental heat index (March 2024), reported by Question of Cities. https://questionofcities.org/heat-index-or-the-temperature-it-feels-like-will-change-the-way-india-measures-heat/
- Ahmedabad Heat Action Plan, 2019 update (NRDC). https://www.nrdc.org/sites/default/files/ahmedabad-heat-action-plan-2019-update.pdf
- Knowlton K, et al. (2014). Development and implementation of South Asia's first heat-health action plan in Ahmedabad. *IJERPH*. https://pmc.ncbi.nlm.nih.gov/articles/PMC4024996/
- Azhar GS, et al. (2014). Heat-related mortality in India: excess all-cause mortality associated with the 2010 Ahmedabad heat wave. *PLOS ONE* 9(3):e91831. https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0091831
- "Study finds 44% of Ahmedabad population at severe heat risk, eastern wards worst hit" (PDEU study), Vibes of India, 29 April 2026. https://www.vibesofindia.com/study-finds-44-of-ahmedabad-population-at-severe-heat-risk-eastern-wards-worst-hit/
- Ahmedabad Municipal Corporation (2014). Ahmedabad Slum Free City Action Plan (RAY). https://pas.org.in/Portal/document/PIP%20Application/Ahmedabad%20Slum%20Free%20City%20Action%20Plan%20RAY.pdf
- Kaushal S, Nair T (2024). Industrial fragmentation, migration and live-in factories in Ahmedabad. https://journals.sagepub.com/doi/10.1177/09737030241238818

---

## Follow-up (same day): slum data added, vulnerability index re-scaled

Decision 2's next step is done.

**Slum share filled for all 48 wards** from the AMC slum survey (see [data/README.md](../data/README.md#slum-share-informal_housing_share)). The bias noted there is that Vatva's resettlement flats aren't counted as slums.

**Vulnerability indicators now use percentile ranks instead of min-max.** With real slum data in, min-max rescaling left most wards far below the midpoint: slum share is skewed, with one ward at 61%. The average ward's PVI dropped to 41, which would have silently lowered every ward's risk, because the risk formula treats PVI 50 as average. Percentile ranking, the method of the CDC/ATSDR Social Vulnerability Index (Flanagan et al., 2011), keeps the median ward at 0.5 and stops one extreme value from dominating.

**Effect on the ward ranking**

| Ward | Before (min-max, no slum data) | After |
|---|---|---|
| Amraiwadi | 9th (PVI) | **1st** |
| Odhav | high | **2nd** |
| Maktampura | 5th, the hospital-distance artefact | **30th** |
| Vatva | 41st | **23rd** (still understated, see bias above) |
| Sarkhej | low | 40th (PDEU study: third-safest) |

Highest mean risk at the May 2024 peak: Amraiwadi, Odhav, Jamalpur, Asarwa, Indrapuri, Baherampura, India Colony, Bodakdev. Lowest: Isanpur, Sarkhej, Paldi, Nikol, Jodhpur. Bodakdev, an affluent western ward, ranks high because the 2010 survey lists five slums there (4,054 huts). That is real data but worth checking locally.

**Effect on the backtest** (final numbers in [backtest_may2024.md](backtest_may2024.md)): every dangerous day is still caught (11 of 11), lead time before IMD's alert is 4 days, and exact agreement with the Heat Action Plan is 67%. The earlier 74% was helped by the off-centre PVI quietly lowering all wards. Ward rankings are now very stable (ρ ≥ 0.976 under every ±20% weight change). *(After the Phase 6 access update: lead time 3 days, ρ ≥ 0.963; see backtest_may2024.md.)*

Additional sources:
- Flanagan BE, et al. (2011). A social vulnerability index for disaster management. *Journal of Homeland Security and Emergency Management* 8(1). https://atsdr.cdc.gov/place-health/media/pdfs/2024/07/Flanagan_2011_SVIforDisasterManagement-508.pdf
- CDC/ATSDR SVI 2022 documentation (percentile ranks 0–1 for each variable). https://svi.cdc.gov/map/data/docs/SVI2022Documentation_5.17.2024.pdf
- Sabarmati Riverfront displacement (about 11,000 families; Vatva the largest resettlement site): Down To Earth, https://www.downtoearth.org.in/environment/concerns-over-sabarmati-riverfront-development-project-5786; Mapping Evictions and Resettlement in Ahmedabad 2000–2017, https://www.researchgate.net/publication/328448824_Mapping_Evictions_and_Resettlement_in_Ahmedabad_2000-2017

---

## Decision 3 — Hospital capacity factor (C_h): method built, kept switched off

**Question:** C_h (hospital capacity pressure, used only in the hospitalization score HRI) was empty everywhere. Can it be filled from the bed data?

**Method built:** the enhanced two-step floating catchment area method (E2SFCA; Luo & Qi, 2009), the standard way to measure how many beds each area can reach relative to the population competing for them. It uses a 15 km Gaussian catchment from each ward's centre. The code is in [heatrisk/access.py](../heatrisk/access.py) with tests; Phase 6 will reuse it for cooling-point access.

**What it showed:** with the 5 public hospitals (7,785 beds), the city averages 1.39 public beds per 1,000 residents. The walled-city wards next to Civil, VS/SVP and LG hospitals have the most access (1.8), and the edge wards the least (Maktampura 0.6, Sarkhej, Thaltej, Gota). As a C_h, this would have pushed **Thaltej and Bodakdev**, affluent western wards served by many private hospitals, into the top six for hospitalization risk.

**Evidence:** private hospitals handle **64.6% of in-patient cases in urban Gujarat**, and government facilities 32.2% (NSS 75th round, 2017–18). A city-wide private bed total isn't published; the only figures are COVID-era designated beds (62 hospitals, over 3,150 beds). OpenStreetMap lists 763 hospitals but none has a bed count.

**Decision:** keep C_h at its flagged default (1.0, "no data") and don't feed a public-only measure into HRI. The public-bed access figure is stored as `public_beds_access` (beds per 1,000 residents) for maps and for Phase 6, labelled as *public safety-net* access. To switch C_h on, add private hospital beds to `data/manual/hospital_beds.csv`, for example from India's Health Facility Registry (ABDM), and set `risk.capacity.spread` to about 0.15.

Sources:
- Luo W, Qi Y (2009). An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians. *Health & Place* 15(4):1100–1107. https://pubmed.ncbi.nlm.nih.gov/19576837/
- NSS 75th round, Health in India (2017–18), via "High privatisation in Gujarat's healthcare…" (Counterview, April 2026). https://www.counterview.net/2026/04/high-privatisation-in-gujarats_01448575537.html; MoSPI summary: https://mospi.gov.in/sites/default/files/announcements/Summary%20Analysis_Report_586_Health.pdf
- COVID-era designated private beds in Ahmedabad (Business Standard, 2020). https://www.business-standard.com/article/current-affairs/ahmedabad-over-80-beds-in-designated-private-hospitals-occupied-120092801065_1.html
