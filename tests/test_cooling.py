import networkx as nx
import numpy as np
import pandas as pd

from heatrisk import cooling


def _line_graph(n=11, step=200.0):
    """Nodes 0..10 on a straight street, 200 m apart."""
    g = nx.Graph()
    for i in range(n - 1):
        g.add_edge(i, i + 1, length=step)
    return g


def test_network_distance_and_snap():
    g = _line_graph()
    d = cooling.network_distance(g, {0})
    assert d[5] == 1000.0
    nodes, snap = cooling.snap(np.array([[410.0, 30.0]]), np.arange(11), np.c_[np.arange(11) * 200.0, np.zeros(11)])
    assert nodes[0] == 2 and round(snap[0], 1) == 31.6


def test_ward_gap_is_population_share():
    cells = pd.DataFrame({"ward_id": ["A", "A", "B"], "pop": [100.0, 300.0, 50.0]})
    gap = cooling.ward_gap(cells, np.array([True, False, True]))
    assert gap["A"] == 0.25 and gap["B"] == 1.0


def test_greedy_picks_site_that_covers_most_weight():
    g = _line_graph()
    cells = pd.DataFrame({"node": np.arange(11), "snap_m": 0.0, "pop": [10.0] * 11,
                          "weight": [1.0] * 8 + [5.0] * 3, "ward_id": "A"})
    covered = np.array([True] * 3 + [False] * 8)              # nodes 0-2 already near a cooling point
    cand = pd.DataFrame({"node": [3, 9], "snap_m": 0.0, "name": ["near", "far end"], "layer": "school",
                         "ward_id": "A", "lon": 0.0, "lat": 0.0})
    picks = cooling.greedy_sites(g, cells, covered, cand, reach_m=400.0, k=2)
    assert picks[0]["name"] == "far end"                      # nodes 7-10 carry the heaviest weights
    assert picks[0]["people_newly_covered"] == 40
    assert picks[1]["name"] == "near" and picks[1]["people_newly_covered"] == 30   # reaches nodes 1-5; only 3-5 were uncovered
