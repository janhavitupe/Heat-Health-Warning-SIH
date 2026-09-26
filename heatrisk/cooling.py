"""Cooling access, cooling deserts and new cooling-centre sites — proposal §6.11 (Innovation 5).

Walking times are measured along the OpenStreetMap footpath/street network
(scripts/build_walk_network.py) from every populated 100 m WorldPop cell
(gee/export_pop_grid.py) to the nearest cooling option:

  walk time = (straight line from cell centre to its nearest network node
               + network distance from that node to the nearest option) / walking speed

  Cooling Gap (ward)  = share of the ward's population beyond `walk_minutes`
  cooling desert      = Cooling Gap > `desert_gap`
  new sites           = greedy maximum coverage: repeatedly pick the candidate site
                        (school, community centre) that brings the most PVI-weighted
                        people newly within reach

Proposal §6.11 weights the gap by PVI. PVI is a ward-level score, so within a ward
the weighted and unweighted shares are identical; PVI weights matter when people
are summed across wards, i.e. in site selection.

The same machinery gives the population-weighted walking distance to the nearest
health facility, which replaces the straight-line centroid distance in PVI.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

METRIC_CRS = "EPSG:32643"


def load_network(path) -> tuple[nx.Graph, np.ndarray, np.ndarray]:
    """Walking network as an undirected graph with edge `length` (m), plus node ids and UTM coordinates."""
    import osmnx as ox

    g = ox.project_graph(ox.load_graphml(path), to_crs=METRIC_CRS)
    und = nx.Graph()
    for u, v, d in g.edges(data=True):
        w = float(d["length"])
        if not und.has_edge(u, v) or und[u][v]["length"] > w:
            und.add_edge(u, v, length=w)
    nodes = np.array(list(und.nodes))
    xy = np.array([[g.nodes[n]["x"], g.nodes[n]["y"]] for n in nodes])
    return und, nodes, xy


def snap(points_xy: np.ndarray, nodes: np.ndarray, nodes_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nearest network node for each point, and the straight-line distance to it (m)."""
    d, i = cKDTree(nodes_xy).query(points_xy)
    return nodes[i], d


def network_distance(graph: nx.Graph, sources: set, cutoff_m: float | None = None) -> dict:
    """Distance (m) from every reachable node to the nearest source node."""
    return nx.multi_source_dijkstra_path_length(graph, sources, cutoff=cutoff_m, weight="length")


def cell_distance(cell_nodes: np.ndarray, cell_snap_m: np.ndarray, dist: dict, missing_m: float) -> np.ndarray:
    """Distance from each cell to the nearest source: snap distance + network distance."""
    net = np.array([dist.get(n, missing_m) for n in cell_nodes], dtype=float)
    return cell_snap_m + net


def ward_gap(cells: pd.DataFrame, beyond: np.ndarray) -> pd.Series:
    """Population share per ward with `beyond` True."""
    return (cells["pop"] * beyond).groupby(cells["ward_id"]).sum() / cells.groupby("ward_id")["pop"].sum()


def greedy_sites(graph: nx.Graph, cells: pd.DataFrame, covered: np.ndarray, candidates: pd.DataFrame,
                 reach_m: float, k: int) -> list[dict]:
    """Greedy maximum coverage over candidate sites.

    `cells` needs node, snap_m, weight (PVI-weighted people) and pop; `covered` marks
    cells already within reach of an existing option. Each pick adds the candidate
    that newly covers the most weight.
    """
    node_cells = cells.reset_index(drop=True).groupby("node").indices
    reach = []
    for c in candidates.itertuples():
        near = nx.single_source_dijkstra_path_length(graph, c.node, cutoff=reach_m + c.snap_m, weight="length")
        idx = [i for n, d in near.items() for i in node_cells.get(n, ())
               if d + c.snap_m + cells["snap_m"].iat[i] <= reach_m]
        reach.append(np.array(idx, dtype=int))
    covered = covered.copy()
    w, pop = cells["weight"].to_numpy(), cells["pop"].to_numpy()
    picks = []
    for _ in range(k):
        gains = [w[r[~covered[r]]].sum() if len(r) else 0.0 for r in reach]
        best = int(np.argmax(gains))
        if gains[best] <= 0:
            break
        new = reach[best][~covered[reach[best]]]
        covered[new] = True
        c = candidates.iloc[best]
        picks.append({"rank": len(picks) + 1, "name": c["name"], "layer": c["layer"], "ward_id": c["ward_id"],
                      "lon": c["lon"], "lat": c["lat"], "people_newly_covered": int(round(pop[new].sum())),
                      "vulnerability_weighted_gain": round(float(w[new].sum()), 1)})
    return picks
