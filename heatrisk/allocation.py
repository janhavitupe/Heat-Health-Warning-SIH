"""Resource Allocation Engine (Phase 6).

Given limited resources for one day, produce a ranked, explained plan:

  Mobile cooling units: each unit is parked where it brings the most risk-weighted
  people within a 15-minute walk. A unit reaches the uncovered residents inside a
  circle of walking radius r; with the ward's uncovered people spread over the
  uncovered share of its area, that is
      reach = min(uncovered people, uncovered density × π r²)
  and the gain is reach × MRI/100. Units are placed one at a time (greedy), so a
  second unit in the same ward only counts people the first did not reach.
  `people_within_walk` is coverage (people who could walk to the unit in 15 min),
  not how many people one unit can serve in a day.

  Ambulances: shared in proportion to expected heat-illness demand
  (population × HRI/100) with the D'Hondt highest-averages method: each extra
  ambulance in a ward is worth demand / (units already there + 1).
"""

from __future__ import annotations

import math

import pandas as pd


def cooling_units(wards: pd.DataFrame, n_units: int, reach_km: float) -> pd.DataFrame:
    """`wards` needs ward_id, ward_name, population, area_km2, cooling_gap, mri. Returns one row per unit."""
    w = wards.set_index("ward_id").copy()
    w["uncovered"] = w["population"] * w["cooling_gap"]
    density = w["uncovered"] / (w["area_km2"] * w["cooling_gap"]).clip(lower=1e-6)     # people per km² where uncovered
    circle = math.pi * reach_km ** 2
    remaining = w["uncovered"].copy()
    rows = []
    for unit in range(1, n_units + 1):
        reach = pd.concat([remaining, density * circle], axis=1).min(axis=1)
        gain = reach * w["mri"] / 100
        best = gain.idxmax()
        if gain[best] <= 0:
            break
        remaining[best] -= reach[best]
        rows.append({"unit": unit, "ward_id": best, "ward_name": w.at[best, "ward_name"],
                     "people_within_walk": int(round(reach[best])), "mri": round(float(w.at[best, "mri"]), 1),
                     "reason": f"{w.at[best, 'cooling_gap']:.0%} of residents beyond a 15-min walk of cooling; "
                               f"MRI {w.at[best, 'mri']:.0f}"})
    return pd.DataFrame(rows)


def ambulances(wards: pd.DataFrame, n_units: int) -> pd.DataFrame:
    """`wards` needs ward_id, ward_name, population, hri. Returns wards with their ambulance count (D'Hondt)."""
    w = wards.set_index("ward_id").copy()
    w["demand"] = w["population"] * w["hri"] / 100
    w["ambulances"] = 0
    for _ in range(n_units):
        best = (w["demand"] / (w["ambulances"] + 1)).idxmax()
        w.at[best, "ambulances"] += 1
    out = w[w["ambulances"] > 0].sort_values(["ambulances", "demand"], ascending=False).reset_index()
    total = w["demand"].sum()
    out["share_of_demand"] = (out["demand"] / total).round(3)
    out["reason"] = [f"HRI {h:.0f} × {p / 1000:.0f}k residents = {s:.1%} of expected heat-illness demand"
                     for h, p, s in zip(out["hri"], out["population"], out["share_of_demand"])]
    return out[["ward_id", "ward_name", "ambulances", "hri", "population", "share_of_demand", "reason"]]
