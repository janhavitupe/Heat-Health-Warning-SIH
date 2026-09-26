"""Compute cooling access, cooling deserts, new-site recommendations and walking access to health care.

Inputs:  data/processed/walk_graph.graphml   (scripts/build_walk_network.py)
         data/processed/pop_grid.parquet     (gee/export_pop_grid.py)
         data/processed/cooling_points.geojson, wards.parquet
Outputs: data/processed/ward_access.csv      per ward: cooling_gap, cooling_gap_with_community,
                                             cooling_desert, health_walk_km (merged by build_wards.py)
         data/processed/cooling_sites.geojson recommended new cooling-centre sites (ranked)
         data/processed/ward_cooling_points.json up to 3 named AMC cooling places per ward (for advisories)
Usage:   python scripts/build_access.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from heatrisk import cooling, load_config, vulnerability  # noqa: E402

PROC = ROOT / "data" / "processed"


def main() -> None:
    cfg = load_config()
    cc = cfg["cooling"]
    reach_m = cc["walk_minutes"] * cc["walk_speed_kmh"] * 1000 / 60
    t = time.time()
    graph, nodes, nodes_xy = cooling.load_network(PROC / "walk_graph.graphml")
    print(f"network: {graph.number_of_nodes():,} nodes ({time.time() - t:.0f}s); 15-min reach = {reach_m:.0f} m")

    wards = pd.read_parquet(PROC / "wards.parquet")
    cells = pd.read_parquet(PROC / "pop_grid.parquet")
    # WorldPop grid (unconstrained) gives the distribution within each ward; totals follow the ward table
    scale = wards.set_index("ward_id")["population"] / cells.groupby("ward_id")["pop"].sum()
    cells["pop"] = cells["pop"] * cells["ward_id"].map(scale)
    cxy = gpd.GeoSeries(gpd.points_from_xy(cells["lon"], cells["lat"]), crs=4326).to_crs(cooling.METRIC_CRS)
    cells["node"], cells["snap_m"] = cooling.snap(np.c_[cxy.x, cxy.y], nodes, nodes_xy)
    pvi, _ = vulnerability.compute_pvi(wards, cfg)
    cells["weight"] = cells["pop"] * cells["ward_id"].map(pvi.set_index("ward_id")["pvi"] / 100)

    pts = gpd.read_file(PROC / "cooling_points.geojson").to_crs(cooling.METRIC_CRS)
    pts["node"], pts["snap_m"] = cooling.snap(np.c_[pts.geometry.x, pts.geometry.y], nodes, nodes_xy)

    def dist_to(layers, cutoff):
        src = set(pts.loc[pts["layer"].isin(layers), "node"])
        d = cooling.network_distance(graph, src, cutoff)
        return cooling.cell_distance(cells["node"].to_numpy(), cells["snap_m"].to_numpy(), d, missing_m=cutoff or 1e6)

    d_cool = dist_to(cc["existing_layers"], 5000)
    d_comm = dist_to(cc["existing_layers"] + cc["community_layers"], 5000)
    d_health = dist_to(cc["health_layers"], 20000)
    beyond = d_cool > reach_m

    out = pd.DataFrame({
        "cooling_gap": cooling.ward_gap(cells, beyond),
        "cooling_gap_with_community": cooling.ward_gap(cells, d_comm > reach_m),
        "health_walk_km": (cells.assign(d=d_health * cells["pop"]).groupby("ward_id")["d"].sum()
                           / cells.groupby("ward_id")["pop"].sum()) / 1000,
    }).round(3)
    out["cooling_desert"] = out["cooling_gap"] > cc["desert_gap"]
    out.index.name = "ward_id"
    out.to_csv(PROC / "ward_access.csv")

    # Named cooling places inside each ward, for advisories: health centres and public buildings first
    order = {"uhc": 0, "library": 1, "ward_office": 2, "public_hospital": 3, "park": 4, "brts_station": 5, "drinking_water": 6}
    named = pts[pts["layer"].isin(cc["existing_layers"]) & pts["name"].notna()].copy()
    named = gpd.sjoin(named, gpd.read_file(PROC / "wards.geojson").to_crs(cooling.METRIC_CRS)[["ward_id", "geometry"]],
                      predicate="within")
    named["o"] = named["layer"].map(order)
    per_ward = {wid: [{"name": str(r["name"]).strip(), "layer": r["layer"]} for _, r in g.sort_values("o").head(3).iterrows()]
                for wid, g in named.groupby("ward_id")}
    (PROC / "ward_cooling_points.json").write_text(json.dumps(per_ward, indent=1, ensure_ascii=False), encoding="utf-8")

    cand = pts[pts["layer"].isin(cc["candidate_layers"])].copy()
    ll = cand.to_crs(4326)
    cand["lon"], cand["lat"] = ll.geometry.x.round(5), ll.geometry.y.round(5)
    wpoly = gpd.read_file(PROC / "wards.geojson").to_crs(cooling.METRIC_CRS)
    cand = gpd.sjoin(cand, wpoly[["ward_id", "geometry"]], predicate="within").drop(columns="index_right")
    cand["name"] = cand["name"].fillna(cand["layer"].str.replace("_", " ").str.title())
    t = time.time()
    picks = cooling.greedy_sites(graph, cells, ~beyond, cand.reset_index(drop=True), reach_m, cc["new_sites_k"])
    print(f"site selection over {len(cand)} candidates in {time.time() - t:.0f}s")
    names = wards.set_index("ward_id")["ward_name"]
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
         "properties": {**{k: v for k, v in p.items() if k not in ("lon", "lat")}, "ward_name": names[p["ward_id"]]}}
        for p in picks]}
    (PROC / "cooling_sites.geojson").write_text(json.dumps(fc, indent=1), encoding="utf-8")

    total, uncovered = cells["pop"].sum(), cells.loc[beyond, "pop"].sum()
    print(f"city: {uncovered / total:.1%} of people beyond a {cc['walk_minutes']}-min walk of an AMC cooling option "
          f"({cells.loc[d_comm > reach_m, 'pop'].sum() / total:.1%} if temples/mosques/malls count)")
    print(f"cooling deserts: {int(out['cooling_desert'].sum())} wards")
    print(out.join(names).sort_values("cooling_gap", ascending=False).head(8).to_string())
    for p in picks:
        print(f"  site {p['rank']}: {p['name']} ({p['layer']}, {names[p['ward_id']]}) +{p['people_newly_covered']:,} people")


if __name__ == "__main__":
    main()
