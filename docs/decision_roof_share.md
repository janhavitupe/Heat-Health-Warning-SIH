# Decision: Estimating Sheet-Roof Share per Ward (Innovation 1)

**Date:** 2026-09-27 · **Code:** [scripts/estimate_roof_share.py](../scripts/estimate_roof_share.py) → `data/manual/roof_estimate.json` → [scripts/build_wards.py](../scripts/build_wards.py)

## Problem

The indoor-heat points (P_indoor) and the what-if **cool roofs** lever both depend on the share of households under **metal or asbestos sheet roofs**. That column was empty, so both showed "no data".

Census 2011 does publish roof material **per ward** (Houselisting table HH-14). However, the table only covers the old, numbered 2011 wards (1–63). The platform uses the 48 named wards created in 2015.
- **No reliable number-to-name list:** different sources number the old wards differently. For example, Khadia is ward 28 in one list and ward 45 in another.
- **No boundaries to overlay:** there are no 2011 ward boundaries to intersect with the 2015 ones.

Matching them now would mean guessing.

## Decision

Estimate each 2015 ward's share as a mix of the **slum** and **non-slum** sheet-roof rates. The mix is weighted by the ward's slum share, which is already known for every 2015 ward from the AMC slum survey (Phase 3):

```
roof_sheet_share = s_slum × slum_share + s_nonslum × (1 − slum_share)
```

| Quantity | Value | Source |
|---|---|---|
| City sheet-roof share, S | **21.9%** of households | Census 2011 HH-14, Ahmadabad (M Corp.): 63 wards, weighted by PCA households (1,179,823 households in the 57 wards that match) |
| Slum sheet-roof share, s_slum | **51.1%** | Census 2011 SLUM HL-02 A, Gujarat urban slum households (G.I./metal/asbestos) |
| Slum household share, f | **13.7%** | AMC 2010-11 slum survey huts ÷ 2011 households |
| Non-slum share, s_nonslum | **17.3%** | Solved from S = f·s_slum + (1 − f)·s_nonslum |

**Result for the 48 wards:** 17.2% to 37.9%, with a median of 20.1%. The highest are New Wadaj (38%), Shahpur (34%), Indrapuri (31%), Danilimda (30%) and Vasna (29%).

**Why this is reasonable:**
- The estimate reproduces the census city total exactly.
- It uses only official census rates plus the same slum data the vulnerability index already uses.
- Research ties sheet roofs in Ahmedabad to informal settlements: tin, asbestos-cement and tarpaulin roofs are the main heat trap in slum housing (Vellingiri et al. 2020).

## Limitations

- **Too smooth.** The real 2011 wards ranged from 7.8% to 47.8% (10th–90th percentile) and up to 62.7%. The estimate spans only 17%–38%, because sheet roofs also occur outside mapped slums (e.g. old mill chawls in the east). Wards with many chawls but few mapped slums are underestimated.
- **State slum rate.** s_slum is Gujarat's, not Ahmedabad's. SLUM HL-02 A is not published for Ahmedabad separately.
- **2011 data.** Roofs have changed since 2011. Slum redevelopment and MHT's cool-roof programme (painted or insulated roofs) both reduce the true heat-trapping share. The estimate therefore probably overstates today's level somewhat.
- **Labelled as an estimate** everywhere: in column_sources.csv, in the explanation note ("roof share estimated from census 2011 city and slum rates") and in the map's layer help.
- **Replacement plan:** once a 2011→2015 ward crosswalk is found, the census HH-14 ward values replace this estimate (data/README.md). A value entered by hand in `ward_attributes.csv` already takes priority.

## Effect on scores

**Indoor points:** 10 × share on days with base heat score ≥ 41, × 1.5 on hot nights. That gives about 1.7–3.8 points on hot days and up to 5.7 on hot nights.

**May 2024 backtest:**

| Metric | Before (no roof data) | After |
|---|---|---|
| IMD red days with any ward at Red | 3 of 5 | **4 of 5** |
| Lead time: consecutive Orange+ days before 20 May | 3 | **4** |
| Plan Orange/Red days caught | 11 of 11 | 11 of 11 |
| Days outside IMD window with a Red ward | 5 of 41 | 6 of 41 (adds 17 May, the day before the heatwave; two wards at MRI 80.2–80.7, ward Tmax 45 °C) |
| Median ward same level as the plan | 67% | 65% |
| Red ward-days, 10–31 May | 302 | 350 |

The ward ranking barely moves: sensitivity ρ stays ≥ 0.97 for every change except beta_day. Alert counts move more, as expected, because many wards sit near the Red line during the peak.

## Cool-roofs lever (what-if)

The lever multiplies a ward's sheet-roof share by (1 − X) for X% of sheet roofs treated.

**Example:** Baherampura, 50% of sheet roofs → share 27.5% → 13.8%. Over May 2024:
- Mean MRI −1.6
- 2 Red days avoided
- 7 fewer Orange+ days

**Upper bound:** the lever treats a treated sheet roof as no longer heat-trapping at all.
- **Evidence:** reflective paint on sheet roofs lowers indoor temperature by about 2–5 °C (NRDC/IIPH 2018). MHT's modular roofs showed 7–8 °C.
- **Remaining gap:** unpainted tin roofs can still reach indoor peaks above 49 °C. A painted sheet roof may therefore not fully match a concrete roof.
- **How to read results:** read them as the most a cool-roof programme could achieve under this model.

## Sources

- Census of India 2011, Houselisting & Housing Census, Table HH-14 (Ahmadabad district, ward level), "Households by material of roof": https://censusindia.gov.in/nada/index.php/catalog/ (HLPCA-24474-2011_H14)
- Census of India 2011, SLUM HL-02 A, "Slum households by material of roof", state level: https://censusindia.gov.in/nada/index.php/catalog/ (SHH0402A)
- Vellingiri S, Dutta P, Singh S, et al. (2020). Combating climate change-induced heat stress: assessing cool roofs and its impact on the indoor ambient temperature of the households in the urban slums of Ahmedabad. *Indian J Occup Environ Med* 24(1):25–29. https://pubmed.ncbi.nlm.nih.gov/32435111/
- NRDC, IIPH Gandhinagar, ASCI (2018). *Cool Roofs: Protecting Local Communities from Extreme Heat.* https://iiphg.edu.in/images/pdfs/NRDC/cool-roofs-2018.pdf
