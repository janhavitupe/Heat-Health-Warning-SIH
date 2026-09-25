import numpy as np
import pandas as pd
import pytest

from heatrisk import access


def test_gaussian_decay_shape():
    g = access.gaussian_decay(np.array([0.0, 5.0, 10.0, 12.0]), d0_km=10)
    assert g[0] == pytest.approx(1.0) and g[2] == pytest.approx(0.0) and g[3] == 0.0
    assert 0 < g[1] < 1


def test_e2sfca_conserves_capacity_when_all_in_reach():
    """Σ population × access = total capacity when every facility serves every ward."""
    wards_xy = np.array([[0, 0], [2000, 0], [0, 3000]], dtype=float)
    pop = np.array([1000.0, 5000.0, 2000.0])
    fac_xy = np.array([[500, 500], [1500, 2500]], dtype=float)
    beds = np.array([100.0, 60.0])
    a = access.e2sfca(wards_xy, pop, fac_xy, beds, d0_km=50)
    assert (a * pop).sum() == pytest.approx(beds.sum())


def test_farther_ward_has_less_access():
    wards_xy = np.array([[0, 0], [8000, 0]], dtype=float)
    a = access.e2sfca(wards_xy, np.array([1000.0, 1000.0]), np.array([[0, 0]], dtype=float), np.array([50.0]), d0_km=15)
    assert a[0] > a[1] > 0


def test_capacity_factor_centred_and_bounded():
    acc = pd.Series([0.5, 1.0, 1.5, 2.0, 2.5])
    c = access.capacity_factor(acc, {"min": 0.8, "max": 1.3}, spread=0.15)
    assert c.tolist() == pytest.approx([1.15, 1.075, 1.0, 0.925, 0.85])   # least access → highest pressure
