"""Download the OpenStreetMap walking network for the city (Phase 6 cooling and health access).

Covers all wards plus a 1 km margin (people near the boundary may walk to facilities
just outside). Saved as data/processed/walk_graph.graphml (not committed; rebuild
with this script). This replaces the OSRM server planned in Phase 6: the same
street network, routed in Python with networkx (no Docker needed).

Usage:  python scripts/build_walk_network.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import osmnx as ox

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "walk_graph.graphml"


def main() -> None:
    wards = gpd.read_file(ROOT / "data" / "processed" / "wards.geojson")
    area = wards.to_crs(32643).union_all().buffer(1000)
    area = gpd.GeoSeries([area], crs=32643).to_crs(4326).iloc[0]
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(ROOT / "data" / "raw" / "osm" / "osmnx_cache")
    t = time.time()
    g = ox.graph_from_polygon(area, network_type="walk", simplify=True, retain_all=False)
    print(f"{g.number_of_nodes():,} nodes, {g.number_of_edges():,} edges in {time.time() - t:.0f}s")
    ox.save_graphml(g, OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    sys.exit(main())
