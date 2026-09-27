"""Estimate the share of households under metal/asbestos sheet roofs in each 2015 ward (Innovation 1).

Census 2011 publishes roof material per ward (HH-14), but only for the old, numbered
2011 wards, which cannot yet be matched to the 2015 wards (see data/README.md). Sheet
roofs are concentrated in slums, and slum share is known for every 2015 ward
(scripts/extract_slums.py), so each ward is estimated as a mix:

  share_ward = s_slum × slum_share + s_nonslum × (1 − slum_share)

  S_city     sheet-roof share of all Ahmedabad (M Corp.) households, household-weighted
             over the 2011 wards  (HH-14 Ahmadabad + PCA ward households)
  s_slum     sheet-roof share of slum households, Gujarat (SLUM HL-02 A; state-level proxy)
  f          share of households living in slums (AMC 2010-11 slum survey huts / 2011 households)
  s_nonslum  = (S_city − f × s_slum) / (1 − f)

The estimate understates real differences between wards: 2011 census wards ranged from
8% to 48% (10th-90th percentile), because sheet roofs also occur outside slums (e.g. old
mill chawls). It will be replaced by census ward values once the 2011 ward list is found.

Inputs:  data/raw/census/hl14_ahmadabad_2011.xlsx, pca_tv_ahmadabad_2011.xlsx,
         data/raw/census/slum_hl02a_2011.pdf (Gujarat row), data/manual/slum_ward_stats.csv
Output:  data/manual/roof_estimate.json (constants + per-ward estimate), merged by build_wards.py
Usage:   python scripts/estimate_roof_share.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pypdf

ROOT = Path(__file__).resolve().parent.parent
RAW, MANUAL = ROOT / "data" / "raw" / "census", ROOT / "data" / "manual"
GUJARAT_SLUM_HOUSEHOLDS = 360_291       # SLUM HL-02 A total for Gujarat, used to find its row


def city_share() -> tuple[float, dict]:
    hl = pd.read_excel(RAW / "hl14_ahmadabad_2011.xlsx", header=None)
    hl = hl[hl[8].astype(str).str.contains(r"Ahmadabad \(M Corp", regex=True, na=False) & (hl[7].astype(str) != "0000")]
    hl = pd.DataFrame({"ward": hl[7].astype(int), "sheet": hl[28].astype(float)})      # col 28: G.I./Metal/Asbestos sheets, %
    p = pd.read_excel(RAW / "pca_tv_ahmadabad_2011.xlsx", header=0)
    p = p[(p["Level"] == "WARD") & p["Name"].astype(str).str.contains(r"Ahmadabad \(M Corp", regex=True)]
    p = p[p["TRU"] == ("Total" if (p["TRU"] == "Total").any() else "Urban")]
    m = hl.merge(pd.DataFrame({"ward": p["Ward"].astype(int), "households": p["No_HH"]}), on="ward")
    share = float((m["sheet"] * m["households"]).sum() / m["households"].sum()) / 100
    spread = dict(zip(["p10", "median", "p90", "max"], np.round(np.percentile(hl["sheet"], [10, 50, 90, 100]) / 100, 3)))
    return share, {"wards_2011": int(len(hl)), "wards_with_households": int(len(m)),
                   "households": int(m["households"].sum()), "ward_spread_2011": {k: float(v) for k, v in spread.items()}}


def gujarat_slum_share() -> float:
    text = "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(RAW / "slum_hl02a_2011.pdf").pages)
    for line in text.split("\n"):
        nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", line)]
        if nums and nums[0] == GUJARAT_SLUM_HOUSEHOLDS:
            # columns: total, grass, plastic, hand tiles, machine tiles, burnt brick, stone, G.I./metal/asbestos, concrete, other
            return nums[7] / nums[0]
    raise SystemExit("Gujarat row not found in SLUM HL-02 A")


def main() -> None:
    S, info = city_share()
    s_slum = gujarat_slum_share()
    slums = pd.read_csv(MANUAL / "slum_ward_stats.csv")
    f = slums["slum_huts"].sum() / info["households"]
    s_non = (S - f * s_slum) / (1 - f)
    out = {"method": "slum-share mix; see scripts/estimate_roof_share.py",
           "city_sheet_share_2011": round(S, 4), "slum_sheet_share_gujarat_2011": round(s_slum, 4),
           "slum_household_share": round(f, 4), "nonslum_sheet_share": round(s_non, 4), **info}
    (MANUAL / "roof_estimate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
