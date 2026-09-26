import pandas as pd

from heatrisk import actions


def _day(level, wbgt=32.0, hot_days=1, hri=None):
    return {"alert_mri": level, "alert_hri": hri or level, "wbgt": wbgt, "hot_run_days": hot_days}


def test_red_replaces_orange_versions_and_adds_red_actions():
    ids = {a["id"] for a in actions.ward_actions(_day("red"), None, {}, {})}
    assert {"health_red", "announce_red", "workers_red"} <= ids
    assert "health_orange" not in ids                       # superseded by health_red


def test_driver_conditions():
    ex = {"contributions": [{"key": "night", "points": 6.0}]}
    ids = {a["id"] for a in actions.ward_actions(_day("orange", wbgt=29.0), ex, {"cooling_desert": True},
                                                 {"informal_housing_share": 0.9})}
    assert {"nights_orange", "cooling_desert", "slums_orange"} <= ids
    assert "workers_orange" not in ids                      # WBGT below the 30.5 °C trigger


def test_nothing_on_green_and_hri_rules_need_hri_red():
    assert actions.ward_actions(_day("green"), None, {}, {}) == []
    ids = {a["id"] for a in actions.ward_actions(_day("red", hri="orange"), None, {}, {})}
    assert "hospital_red" not in ids


def test_city_actions_by_level_and_triggers():
    assert [a["id"] for a in actions.city_actions("green")] == []
    assert "schools_red" in {a["id"] for a in actions.city_actions("red")}
    assert "nodal_yellow" not in {a["id"] for a in actions.city_actions("red")}
    assert len(actions.trigger_actions("orange_preparedness")) == 3


def test_priority_ranking_uses_probability_as_tie_breaker():
    df = pd.DataFrame({"ward_id": ["A", "B", "C"], "mri": [80.0, 80.0, 90.0], "hri": [1, 2, 3], "p_red": [0.2, 0.6, 0.1]})
    assert actions.priority_ranking(df)["ward_id"].tolist() == ["C", "B", "A"]
    assert actions.priority_ranking(df, "healthcare")["ward_id"].tolist() == ["C", "B", "A"]
