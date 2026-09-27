# Decision: Ward Data for Children, Elderly and Outdoor Workers

**Date:** 28 September 2026 · **Code:** [scripts/estimate_under5.py](../scripts/estimate_under5.py) · **Ward mapping:** [data/manual/ward_census2011_groups.csv](../data/manual/ward_census2011_groups.csv)

Three vulnerability indicators were held at the city midpoint:

| Indicator | Weight in PVI | Why it was neutral |
|---|---|---|
| Elderly (60+) | 0.25 | WorldPop applies district age shares uniformly, so every ward had 9.3% |
| Outdoor workers | 0.20 | No ward-level occupation data |
| Children under 5 | 0.10 | Same as elderly: every ward had 7.9% |

After searching for more data:
- **Under-5 now uses census 2011 data** at assembly-constituency level.
- **Elderly and outdoor workers stay neutral.** No usable source exists below city level, and the proxies tested were too weak to use.

---

## 1. Children under 5: now from census 2011

### The missing link, found

Census 2011 publishes children aged 0–6 for Ahmedabad's **57 census wards**, but only by number ("WARD NO.-0001"). The link between those numbers and today's wards had been the blocker. It turns out that **census 2011 kept the 2001 municipal ward numbers:**

| Census 2011 wards | What they are | Evidence |
|---|---|---|
| 1–43 | The 43 AMC wards of 2001 | The Delimitation Order 2008 lists them by number within each assembly constituency (AC) |
| 44–47 | The 2001 outgrowths: Asarva, Naroda, Nikol, Odhav | Named with these numbers in the same order ("Naroda (OG) 45") |
| 48–57 | The municipalities and villages that joined AMC in 2006 | 10 large, fast-growing wards (73,000–295,000 people) |

**The data confirms this reading:**
- **SC-reserved constituencies contain the high-SC wards.** Danilimda's wards 30, 38 and 40 are 38%, 31% and 11% Scheduled Caste. Jamalpur-Khadiya's ward 39 (Behrampura area) is 36%.
- **Constituency sizes fit the delimitation.** Each constituency adds up to 240,000–370,000 people in 2011, as the 2008 delimitation intended. The old walled-city seats are the smallest, which fits the known population loss from the old city.
- **Affluent areas have the fewest children.** The Ellisbridge and Naranpura areas have the lowest child shares (8.7%, 9.4%); Danilimda and Nikol the highest (13.0%, 12.4%).

### From constituencies to today's wards

Each of today's 48 wards is placed in one group. The evidence for each ward is in the CSV.

| Confidence | Wards | How placed |
|---|---|---|
| High | 31 | The ward shares its name with a constituency (Naranpura, Maninagar…), is a 2001 outgrowth ward (Naroda, Nikol, Odhav), or was outside AMC in 2001 (Gota, Bodakdev, Vejalpur…: the 2006 areas, pooled) |
| Medium | 13 | Neighbourhood evidence, e.g. Shahibag ("Asarwa AC … up to Shahibaug", Delimitation Order) or Baherampura (a Scheduled Caste area in the SC-reserved Danilimda seat) |
| Low | 4 | Viratnagar, Gomtipur, Indrapuri, Isanpur: no documented constituency, so they get the **city value** |

Under-5 share = 0–6 share × 0.70. The 0.70 is the ratio of ages 0–4 to 0–6 in urban Ahmadabad district (Census 2011 C-13). Across Gujarat's 26 urban districts, 0–6 and 0–4 shares correlate at **r = 0.996**, so this conversion is safe.

**Result:** under-5 share now ranges from **6.1% to 9.1%** across wards (before: 7.8–7.9%).

### Checks, including the ones that didn't pass

| Check | Result | Reading |
|---|---|---|
| Leave-one-out: do neighbouring wards predict a ward's value? | Error 0.74 points vs 0.76 for the city mean | ❌ No. That's why the 4 low-confidence wards get the city value, not a neighbour average |
| Higher in slum wards (independent AMC slum survey)? | All wards ρ = −0.21 (p = 0.15); confidently placed, excluding the 2006 areas, ρ = −0.13 (p = 0.5) | Inconclusive. A constituency average hides large differences inside it: New Wadaj (61% slum) and Naranpura (4%) share one value |
| Constituency 2011 population vs today's assigned wards (WorldPop 2020) | 0.48–1.09, and **Ellisbridge 1.8** | Ratios below 1 are expected, since not every ward of a constituency is assigned to it. Ellisbridge's 1.8 suggests one of Paldi, Vasna or Navrangpura belongs elsewhere, or that WorldPop overstates it |

**What this means:** the estimate captures real differences **between constituencies**, in socio-economic level and fertility. It does not capture differences **within** a constituency. It is labelled as an estimate everywhere.

### Effect

- **Vulnerability (PVI):** rank correlation with the previous PVI is 0.85. The largest changes:
  - Paldi, Vasna and Navrangpura: −4.8 points;
  - Odhav: −4.4;
  - Danilimda and Baherampura: +4.9;
  - Nikol: +4.6.
- **May 2024 backtest:** the city-level results are unchanged.
  - 11 of 11 dangerous days caught; 4 of 5 IMD red days with a Red ward; 4 days of warning.
  - **Baherampura** now reaches Red (MRI 82–83) on **17–19 May**, the three days before IMD's red alert began.
- **Sensitivity:** under-5 weight ±20% gives ρ ≥ 0.989.

---

## 2. Elderly (60+): stays neutral

**What was searched:**
- **Census 2011 age tables (C-13, C-14)** are published down to district level only. Within Ahmedabad there is no ward or constituency age data.
- **WorldPop, and the Meta/CIESIN demographic layers,** apply the same district age shares to every grid cell.
- **Electoral rolls** count voters by age band for each constituency, but no public constituency-level table was found; only per-person roll PDFs, which should not be scraped.
- **Proxy from child share:** across Gujarat's 26 urban districts, elderly share falls as child share rises, but weakly (**R² = 0.20**, r = −0.45). Surat, with many young migrants, is far off the line. That's too weak to predict elderly within a city, so it is **not used**.

**Would fix it:** a 60+ count by ward from AMC's health department (NCD screening or ward-level voter age data), or ward-level age data from Census 2027.

## 3. Outdoor workers: stays neutral

**What was searched:**
- **Census 2011 ward tables** only split workers into cultivators, agricultural labourers, household industry and "other". Outdoor occupations can't be told apart.
- **Marginal-worker share** (casual work) as a proxy: it barely varies across the 57 census wards (2.1–3.3% by constituency), so it would add noise, not information.
- **PLFS and the Economic Census** are published at district level at the finest.

**Would fix it:** AMC's registers of street vendors and construction workers, or the Gujarat Building and Other Construction Workers Welfare Board registrations by address.

## 4. Still worth finding

AMC once published **"Ward-wise Data of AMC Area Census 2011.xls"**. Its link is on the AMC demographics page, but it now returns an error page; the Internet Archive was offline when checked. If recovered, it probably gives **names for the 57 census wards**. That would replace the constituency averages with exact census ward values for children, and give the old-to-new ward match needed for workers and roofs.

## Sources

- Census of India 2011, Primary Census Abstract, Ahmadabad district, ward level (`data/raw/census/pca_tv_ahmadabad_2011.xlsx`).
- Census of India 2011, C-13 Single year age returns, Gujarat: https://censusindia.gov.in/nada/index.php/catalog/1448
- Delimitation Commission of India, Gujarat Order No. 33 (2006), Table A: assembly constituencies and their extent, as quoted on each constituency's Wikipedia page, e.g. https://en.wikipedia.org/wiki/Jamalpur-Khadiya_Assembly_constituency, https://en.wikipedia.org/wiki/Ellis_Bridge_Assembly_constituency, https://en.wikipedia.org/wiki/Asarwa_Assembly_constituency
- AMC Slum Free City Action Plan 2014 (2010-11 slum survey), used for the slum-share check.
