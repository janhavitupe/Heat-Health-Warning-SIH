import pandas as pd
import pytest

from heatrisk import allocation


@pytest.fixture
def wards():
    return pd.DataFrame({
        "ward_id": ["A", "B", "C"], "ward_name": ["A", "B", "C"],
        "population": [100_000, 100_000, 50_000], "area_km2": [10.0, 10.0, 5.0],
        "cooling_gap": [0.6, 0.1, 0.0], "mri": [90.0, 90.0, 95.0], "hri": [90.0, 45.0, 90.0],
    })


def test_cooling_units_go_where_uncovered_high_risk_people_are(wards):
    plan = allocation.cooling_units(wards, n_units=3, reach_km=1.0)
    assert plan["ward_id"].iloc[0] == "A"
    assert "C" not in set(plan["ward_id"])                         # everyone in C already has cooling
    a = plan[plan["ward_id"] == "A"]["people_within_walk"].sum()
    assert a <= 60_000                                              # never more than the uncovered people


def test_ambulances_follow_demand_dhondt(wards):
    plan = allocation.ambulances(wards, n_units=4).set_index("ward_id")
    # demand A 90k, B 45k, C 45k -> D'Hondt with 4 seats gives A 2, B 1, C 1
    assert plan["ambulances"].to_dict() == {"A": 2, "B": 1, "C": 1}
    assert plan["share_of_demand"].sum() == pytest.approx(1.0)
