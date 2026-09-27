"""Estimate the share of children under 5 in each 2015 ward from Census 2011 ward data.

WorldPop gives every Ahmedabad ward the same age shares (district proportions), so under-5
share had no ward-to-ward information. Census 2011 publishes children aged 0-6 for each of its
57 wards, but only by number. This script links them to today's wards:

  1. Census 2011 kept the 2001 municipal ward numbers: wards 1-43 are the 2001 AMC wards,
     44-47 the 2001 outgrowths (Asarva, Naroda, Nikol, Odhav) and 48-57 the areas that joined
     AMC in 2006. The Delimitation Order 2008 lists which 2001 wards form each assembly
     constituency (AC), so each AC's census 2011 child share can be computed.
  2. Each 2015 ward is placed in an AC, an outgrowth ward, or the 2006 areas
     (data/manual/ward_census2011_groups.csv, with evidence per row). Wards with no
     documented AC get the city value: interpolating from neighbours predicted assigned
     wards no better than the city mean (leave-one-out check below).
  3. Under-5 share = 0-6 share x (under-5 / 0-6 ratio of urban Ahmadabad district,
     Census 2011 C-13); across Gujarat's urban districts the two correlate at r = 0.996.

Inputs:  data/raw/census/pca_tv_ahmadabad_2011.xlsx, data/manual/ward_census2011_groups.csv,
         data/processed/wards.parquet (centroids, population, slum share for checks)
Output:  data/manual/under5_estimate.csv (merged by build_wards.py) and
         data/manual/under5_estimate.json (constants and validation)
Usage:   python scripts/estimate_under5.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "manual"

# Delimitation Order 2008 (Gujarat Order No. 33, Table A): 2001 AMC wards in each AC
AC_WARDS = {
    "Ellisbridge": [7, 8, 9, 10], "Naranpura": [11, 12, 13, 14], "Nikol": [31, 34, 35],
    "Naroda": [23, 24, 27], "Thakkarbapa Nagar": [22, 25, 26], "Bapunagar": [21, 28, 29],
    "Amraiwadi": [32, 33, 41], "Dariapur": [2, 3, 4, 16], "Jamalpur-Khadiya": [1, 5, 6, 39],
    "Maninagar": [36, 37, 43], "Danilimda": [30, 38, 40], "Asarwa": [17, 18, 19, 20, 44],
    "Vatva": [42, 47], "added_2006": list(range(48, 58)),
    "ward_15": [15], "ward_45": [45], "ward_46": [46], "ward_47": [47],
}
UNDER5_PER_CHILD06 = 0.0786 / 0.1123   # urban Ahmadabad district, Census 2011 C-13 (ages 0-4 / 0-6)


def census_wards() -> pd.DataFrame:
    p = pd.read_excel(ROOT / "data" / "raw" / "census" / "pca_tv_ahmadabad_2011.xlsx")
    w = p[(p["Level"] == "WARD") & p["Name"].astype(str).str.contains(r"Ahmadabad \(M Corp", regex=True)
          & (p["TRU"] == "Urban")]
    return pd.DataFrame({"ward": w["Ward"].astype(int), "pop": w["TOT_P"], "p06": w["P_06"]})


def group_shares(cw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g, ws in AC_WARDS.items():
        s = cw[cw["ward"].isin(ws)][["pop", "p06"]].sum()
        rows.append({"group": g, "census_wards": " ".join(map(str, ws)), "pop_2011": int(s["pop"]),
                     "child06_2011": s["p06"] / s["pop"]})
    return pd.DataFrame(rows).set_index("group")


def idw(target: pd.DataFrame, known: pd.DataFrame, k: int = 3) -> pd.Series:
    out = {}
    for wid, r in target.iterrows():
        d = np.hypot((known["lat"] - r["lat"]) * 111, (known["lon"] - r["lon"]) * 102)
        near = d.nsmallest(k)
        wt = 1 / near.clip(lower=0.5) ** 2
        out[wid] = float((known.loc[near.index, "child06_2011"] * wt).sum() / wt.sum())
    return pd.Series(out)


def main() -> None:
    cw = census_wards()
    assert sorted(cw["ward"]) == list(range(1, 58)), "expected census wards 1-57"
    groups = group_shares(cw)
    xw = pd.read_csv(MANUAL / "ward_census2011_groups.csv")
    wards = pd.read_parquet(ROOT / "data" / "processed" / "wards.parquet").set_index("ward_id")
    xw = xw.join(wards[["centroid_lat", "centroid_lon", "population", "informal_housing_share"]], on="ward_id")
    xw = xw.rename(columns={"centroid_lat": "lat", "centroid_lon": "lon"}).set_index("ward_id")

    known = xw[xw["census_group"] != "interpolate"].copy()
    known["child06_2011"] = known["census_group"].map(groups["child06_2011"])
    assert known["child06_2011"].notna().all(), "unknown census_group in ward_census2011_groups.csv"
    todo = xw[xw["census_group"] == "interpolate"]
    city = float(cw["p06"].sum() / cw["pop"].sum())
    xw["child06_2011"] = known["child06_2011"]
    xw.loc[todo.index, "child06_2011"] = city
    xw["under5_share"] = (xw["child06_2011"] * UNDER5_PER_CHILD06).round(4)

    # --- checks
    # (a) leave-one-out: how well do neighbours predict an assigned ward (is interpolation informative?)
    loo = pd.Series({wid: idw(known.loc[[wid]], known.drop(index=wid)).iloc[0] for wid in known.index})
    loo_mae = float((loo - known["child06_2011"]).abs().mean())
    base_mae = float((known["child06_2011"] - known["child06_2011"].mean()).abs().mean())
    # (b) independent check: children are more common in slum wards (AMC slum survey, not census)
    rho, p = stats.spearmanr(xw["child06_2011"], xw["informal_housing_share"])
    # (c) constituency populations: 2011 census vs today's wards assigned to them (WorldPop 2020)
    pop = xw[xw["census_group"].isin([g for g in AC_WARDS if not g.startswith(("ward_", "added"))])]
    popcheck = (pop.groupby("census_group")["population"].sum().to_frame("worldpop_2020_assigned")
                .join(groups["pop_2011"]))
    popcheck["ratio"] = (popcheck["worldpop_2020_assigned"] / popcheck["pop_2011"]).round(2)

    out = xw.reset_index()[["ward_id", "ward_name_2015", "census_group", "confidence", "child06_2011", "under5_share"]]
    out["child06_2011"] = out["child06_2011"].round(4)
    out.to_csv(MANUAL / "under5_estimate.csv", index=False)
    summary = {
        "method": "census 2011 ward 0-6 share by 2008 assembly constituency; see scripts/estimate_under5.py",
        "under5_per_child06": round(UNDER5_PER_CHILD06, 4), "city_child06_2011": round(city, 4),
        "groups": groups.round(4).reset_index().to_dict("records"),
        "ward_under5_range": [float(out["under5_share"].min()), float(out["under5_share"].max())],
        "confidence_counts": out["confidence"].value_counts().to_dict(),
        "check_leave_one_out_mae": round(loo_mae, 4), "check_mean_only_mae": round(base_mae, 4),
        "check_spearman_vs_slum_share": [round(float(rho), 3), float(p)],
        "check_population_ratio_by_ac": popcheck["ratio"].to_dict(),
    }
    (MANUAL / "under5_estimate.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(groups.round(4).to_string())
    print(popcheck.to_string())
    print(json.dumps({k: v for k, v in summary.items() if k != "groups"}, indent=1))


if __name__ == "__main__":
    main()
