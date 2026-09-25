"""Ward-level slum estimates from the AMC Slum Free City Action Plan (2014).

The plan's Annexure II lists every slum found by AMC's 2010-11 socio-economic
slum survey (691 settlements, 162,749 huts, 727,934 people) with its 2010 ward
name and number of huts. This script:

  1. extracts those rows from the PDF → data/manual/slums_amc_2010.csv
  2. maps 2010 ward names to 2015 wards with the hand-checked crosswalk
     data/manual/ward_crosswalk_slum_2010.csv (method and evidence per row)
  3. writes data/manual/slum_ward_stats.csv: ward_id, slum_settlements, slum_huts,
     slum_pop_est (huts × the survey's 4.47 people per hut)

scripts/build_wards.py turns slum_pop_est into informal_housing_share.
The survey predates the Sabarmati Riverfront relocations, which moved riverbed
slum households to peripheral resettlement sites (e.g. Vatva, Odhav), so those
wards are likely understated. See data/README.md.

Source PDF: data/raw/web/amc_slum_free_city_plan_2014.pdf
  (https://pas.org.in/Portal/document/PIP%20Application/Ahmedabad%20Slum%20Free%20City%20Action%20Plan%20RAY.pdf)
Requires:  pip install -e ".[pdf]"
Usage:     python scripts/extract_slums.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "raw" / "web" / "amc_slum_free_city_plan_2014.pdf"
MANUAL = ROOT / "data" / "manual"
FIRST_ANNEX_PAGE = 113                       # Annexure II starts here (1-based)
SURVEY = {"slums": 691, "huts": 162_749, "population": 727_934}   # plan Table 3-2
PEOPLE_PER_HUT = SURVEY["population"] / SURVEY["huts"]


def ward_key(name: str) -> str:
    """Normalize a 2010 ward name as written in the plan (spacing and line-break variants)."""
    k = re.sub(r"[^A-Z]", "", name.upper())
    return "GIRIDHARNAGAR" if k.startswith("GIRIDHARNAG") else k


def extract() -> pd.DataFrame:
    rows, cols = [], None
    with pdfplumber.open(PDF) as pdf:
        for pno in range(FIRST_ANNEX_PAGE - 1, len(pdf.pages)):
            for table in pdf.pages[pno].extract_tables():
                if not table or not table[0]:
                    continue
                header = [(h or "").replace("\n", " ").strip().lower() for h in table[0]]
                if any("huts" in h for h in header):
                    cols, body = header, table[1:]
                elif cols is None:
                    continue
                else:
                    body = table                 # table continued from the previous page
                try:
                    idx = {k: next(i for i, h in enumerate(cols) if k in h)
                           for k in ("code", "zone", "ward", "slum name", "huts")}
                except StopIteration:
                    continue
                for r in body:
                    cell = lambda k: (r[idx[k]] or "").replace("\n", " ").strip() if idx[k] < len(r) else ""  # noqa: E731
                    huts = cell("huts").replace(",", "")
                    if cell("code") and cell("ward") and huts.isdigit() and not cell("code").lower().startswith("total"):
                        rows.append({"slum_code": cell("code"), "zone_2010": cell("zone"), "ward_2010": cell("ward"),
                                     "slum_name": cell("slum name"), "huts": int(huts), "page": pno + 1})
    # Some slums appear in two strategy tables; keep one row per slum code
    return pd.DataFrame(rows).drop_duplicates("slum_code").reset_index(drop=True)


def main() -> None:
    slums = extract()
    print(f"Extracted {len(slums)} slums, {slums['huts'].sum():,} huts "
          f"(survey: {SURVEY['slums']} slums, {SURVEY['huts']:,} huts)")
    if abs(slums["huts"].sum() / SURVEY["huts"] - 1) > 0.03:
        raise SystemExit("Extracted hut total differs from the survey total by more than 3% - check the parser")
    slums["ward_key"] = slums["ward_2010"].map(ward_key)
    slums.to_csv(MANUAL / "slums_amc_2010.csv", index=False)

    cw = pd.read_csv(MANUAL / "ward_crosswalk_slum_2010.csv")
    unmapped = sorted(set(slums["ward_key"]) - set(cw["ward_key"]))
    if unmapped:
        raise SystemExit(f"2010 wards missing from ward_crosswalk_slum_2010.csv: {unmapped}")

    per_old = slums.groupby("ward_key").agg(slum_settlements=("slum_code", "size"), slum_huts=("huts", "sum"))
    j = cw.join(per_old, on="ward_key")
    j["slum_settlements"] *= j["share"]
    j["slum_huts"] *= j["share"]
    stats = j.groupby("ward_id")[["slum_settlements", "slum_huts"]].sum()
    stats["slum_pop_est"] = stats["slum_huts"] * PEOPLE_PER_HUT
    stats = stats.round({"slum_settlements": 1, "slum_huts": 0, "slum_pop_est": 0}).reset_index()
    stats.to_csv(MANUAL / "slum_ward_stats.csv", index=False)
    print(f"{len(stats)} wards with listed slums -> data/manual/slum_ward_stats.csv "
          f"({PEOPLE_PER_HUT:.2f} people per hut)")


if __name__ == "__main__":
    sys.exit(main())
