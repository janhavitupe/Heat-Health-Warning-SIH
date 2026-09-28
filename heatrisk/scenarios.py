"""What-if intervention simulator — proposal §6.12 (Innovation 3).

A scenario is a list of changes to ward attributes. The affected wards are re-scored
over a replayed heatwave with the same pipeline as the live model, and compared with
the baseline. Every result is a **Scenario Estimate**.

Levers and how they enter the model:
  tree_cover      +X percentage points of tree cover in chosen wards
                  → NDVI (+0.727 per unit cover, cross-ward fit)
                  → night LST (−11.3 °C per unit NDVI, Phase 2 fit)
                  → night air temperature (× beta_night), and
                  → more tree shade on mean radiant temperature (daytime UTCI)
  cool_roofs      paint X% of sheet roofs → roof_sheet_share × (1 − X) → P_indoor
                  (roof share is a census-based estimate; no effect where it is missing)
  cooling_centre  a new cooling place at a map point → people within a 15-min walk
                  → ward cooling gap → PVI (scored against the baseline city)

Temperature changes are added as scenario offsets rather than by editing satellite
values, so one ward's change does not shift the city mean; PVI is scored against the
baseline distribution for the same reason. Changes to unaffected wards are therefore zero.
"""

from __future__ import annotations

import pickle
from functools import lru_cache

import networkx as nx
import numpy as np
import pandas as pd

from heatrisk import vulnerability
from heatrisk.config import ROOT
from heatrisk.pipeline import score_ward

ACCESS_CACHE = ROOT / "data" / "processed" / "access_cache.pkl"
LEVERS = ("tree_cover", "cool_roofs", "cooling_centre")


class ScenarioError(ValueError):
    pass


@lru_cache(maxsize=1)
def access_cache() -> dict:
    """Walking network, snapped population cells and baseline coverage (built by scripts/build_access.py)."""
    if not ACCESS_CACHE.exists():
        raise ScenarioError("cooling-centre scenarios need data/processed/access_cache.pkl: run scripts/build_access.py")
    with open(ACCESS_CACHE, "rb") as f:
        c = pickle.load(f)
    d = nx.multi_source_dijkstra_path_length(c["graph"], c["cooling_nodes"], cutoff=c["reach_m"], weight="length")
    net = np.array([d.get(n, np.inf) for n in c["cells"]["node"]])
    c["covered"] = (c["cells"]["snap_m"].to_numpy() + net) <= c["reach_m"]
    return c


def _cooling_centre(scen: pd.DataFrame, lon: float, lat: float) -> tuple[list[str], dict]:
    import geopandas as gpd

    from heatrisk import cooling

    c = access_cache()
    xy = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(cooling.METRIC_CRS)
    node, snap = cooling.snap(np.c_[xy.x, xy.y], c["nodes"], c["nodes_xy"])
    if snap[0] > 500:
        raise ScenarioError("that point is more than 500 m from the walking network (outside the city?)")
    reach = c["reach_m"] - snap[0]
    near = nx.single_source_dijkstra_path_length(c["graph"], node[0], cutoff=reach, weight="length")
    cells = c["cells"]
    dist = cells["node"].map(near).to_numpy(dtype=float) + cells["snap_m"].to_numpy()
    new = (~c["covered"]) & np.isfinite(dist) & (dist <= reach)
    gained = cells.loc[new].groupby("ward_id")["pop"].sum()
    total = cells.groupby("ward_id")["pop"].sum()
    for wid, people in gained.items():
        i = scen.index[scen["ward_id"] == wid]
        scen.loc[i, "cooling_gap"] = (scen.loc[i, "cooling_gap"] - people / total[wid]).clip(lower=0)
    info = {"lever": "cooling_centre", "lon": lon, "lat": lat, "people_newly_within_walk": int(round(gained.sum())),
            "wards": {w: int(round(p)) for w, p in gained.items()}}
    return list(gained.index), info


def apply(wards: pd.DataFrame, changes: list[dict], cfg: dict) -> tuple[pd.DataFrame, list[str], list[dict]]:
    """Scenario ward table, affected ward ids, and what each change did."""
    sc, reg = cfg["scenarios"], cfg["downscaling"]["lst_regression"]["night_ndvi"]
    scen = wards.copy()
    scen["scenario_dt_night"] = 0.0
    scen["scenario_dt_day"] = 0.0
    affected: list[str] = []
    notes: list[dict] = []
    known = set(wards["ward_id"])
    for ch in changes:
        lever = ch.get("lever")
        if lever not in LEVERS:
            raise ScenarioError(f"unknown lever {lever!r}; choose from {LEVERS}")
        if lever == "cooling_centre":
            try:
                lon, lat = float(ch["lon"]), float(ch["lat"])
            except (KeyError, TypeError, ValueError):
                raise ScenarioError("cooling_centre: give the location as lon and lat") from None
            ids, info = _cooling_centre(scen, lon, lat)
            affected += ids
            notes.append(info)
            continue
        ids = ch.get("wards") or []
        if not ids or not set(ids) <= known:
            raise ScenarioError(f"{lever}: give one or more valid ward ids")
        rows = scen["ward_id"].isin(ids)
        if lever == "tree_cover":
            pp = float(ch.get("pp", 0))
            if not 0 < pp <= sc["max_tree_pp"]:
                raise ScenarioError(f"tree_cover: pp must be between 0 and {sc['max_tree_pp']}")
            old = scen.loc[rows, "tree_cover"]
            new = (old + pp / 100).clip(upper=1.0)
            d_ndvi = sc["tree_ndvi_slope"] * (new - old)
            d_lst = reg["slope"] * d_ndvi
            scen.loc[rows, "tree_cover"] = new
            scen.loc[rows, "ndvi"] = scen.loc[rows, "ndvi"] + d_ndvi
            scen.loc[rows, "scenario_dt_night"] += cfg["downscaling"]["beta_night"] * d_lst
            notes.append({"lever": lever, "wards": ids, "pp": pp,
                          "night_lst_change_c": round(float(d_lst.mean()), 2),
                          "night_air_change_c": round(float((cfg["downscaling"]["beta_night"] * d_lst).mean()), 2)})
        elif lever == "cool_roofs":
            share = float(ch.get("share", 0))
            if not 0 < share <= 1:
                raise ScenarioError("cool_roofs: share must be between 0 and 1")
            before = scen.loc[rows, "roof_sheet_share"]
            missing = before.isna().all()
            scen.loc[rows, "roof_sheet_share"] = before * (1 - share)
            notes.append({"lever": lever, "wards": ids, "share": share,
                          "roof_share_before": None if missing else round(float(before.mean()), 3),
                          "roof_share_after": None if missing else round(float(before.mean() * (1 - share)), 3),
                          "note": "no effect: sheet-roof data is not yet available for these wards" if missing
                                  else "sheet-roof share is an estimate from census 2011 city and slum rates"})
        affected += ids
    return scen, list(dict.fromkeys(affected)), notes


def _summary(daily: pd.DataFrame) -> dict:
    return {"mean_mri": round(float(daily["mri"].mean()), 2), "max_mri": round(float(daily["mri"].max()), 1),
            "red_days": int((daily["alert_mri"] == "red").sum()),
            "orange_plus_days": int(daily["alert_mri"].isin(["orange", "red"]).sum()),
            "mean_tmin": round(float(daily["tmin"].mean()), 2), "mean_utci": round(float(daily["utci"].mean()), 2),
            "pvi": round(float(daily["pvi"].iloc[0]), 1)}


def run(wards: pd.DataFrame, wx: pd.DataFrame, changes: list[dict], cfg: dict) -> dict:
    """Apply the changes, re-score affected wards over `wx`, and compare with the baseline."""
    scen, affected, notes = apply(wards, changes, cfg)
    base_pvi = vulnerability.compute_pvi(wards, cfg)
    scen_pvi = vulnerability.compute_pvi(scen, cfg, reference=wards)
    rows, series = [], {}
    for wid in affected:
        b = score_ward(wid, wx, wards, cfg, pvi=base_pvi, explain_scores=False)["daily"]
        s = score_ward(wid, wx, scen, cfg, pvi=scen_pvi, explain_scores=False)["daily"]
        bs, ss = _summary(b), _summary(s)
        rows.append({"ward_id": wid, "baseline": bs, "scenario": ss,
                     "change": {k: round(ss[k] - bs[k], 2) for k in bs}})
        series[wid] = {"dates": [d.strftime("%Y-%m-%d") for d in b.index],
                       "baseline_mri": b["mri"].round(1).tolist(), "scenario_mri": s["mri"].round(1).tolist()}
    tot = lambda key: sum(r["change"][key] for r in rows)  # noqa: E731
    return {
        "label": "scenario_estimate",
        "wards": rows, "series": series, "changes": notes,
        "city": {"red_ward_days_avoided": -int(tot("red_days")),
                 "orange_plus_ward_days_avoided": -int(tot("orange_plus_days")),
                 "wards_affected": len(rows)},
        "assumptions": [
            "Tree cover → NDVI +0.727 per unit cover (Ahmedabad wards, r = 0.91); NDVI → night surface temperature "
            "−11.3 °C per unit (Phase 2); 30% of the surface change reaches night air temperature.",
            "Tree shade removes half of the direct sun on the shaded share of the ward (radiant temperature).",
            "Observed ward tree cover is 0–22%; studies find the strongest cooling above 40% canopy (Ziter et al. 2019), "
            "so large changes are outside what the data can support.",
            "A new cooling centre counts people within a 15-minute walk (1 km at 4 km/h) along the street network.",
            "Other wards are scored against the unchanged city, so they do not move.",
        ],
    }
