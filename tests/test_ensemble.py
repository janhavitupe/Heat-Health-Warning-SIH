import numpy as np
import pandas as pd
import pytest

from heatrisk import ensemble, weather
from synth import synthetic_weather


@pytest.fixture
def members():
    """Six members: cool, mild and extreme runs from two models."""
    return {
        "ecmwf_ifs025_m00": synthetic_weather(tmax=36, tmin=24),
        "ecmwf_ifs025_m01": synthetic_weather(tmax=44, tmin=30),
        "ecmwf_ifs025_m02": synthetic_weather(tmax=47.5, tmin=32),
        "ecmwf_ifs025_m03": synthetic_weather(tmax=47.5, tmin=32),
        "gfs025_m00": synthetic_weather(tmax=36, tmin=24),
        "gfs025_m01": synthetic_weather(tmax=47.5, tmin=32),
    }


@pytest.fixture
def scores(members, wards, cfg):
    return ensemble.score_members(members, wards, cfg)


def test_probabilities_are_monotonic_and_bounded(scores, cfg):
    p = ensemble.probabilities(scores, cfg)
    assert ((p["p_yellow"] >= p["p_orange"]) & (p["p_orange"] >= p["p_red"])).all()
    assert p[["p_yellow", "p_orange", "p_red"]].stack().between(0, 1).all()
    assert (p["n_members"] == 6).all()
    assert (p["mri_p10"] <= p["mri_median"]).all() and (p["mri_median"] <= p["mri_p90"]).all()


def test_probability_is_member_share(scores, cfg):
    c = {**cfg, "ensemble": {**cfg["ensemble"], "weighting": "member"}}
    p = ensemble.probabilities(scores, c).set_index(["ward_id", "date"])
    lvl = scores.assign(red=scores["level"] == "red").groupby(["ward_id", "date"])["red"].mean()
    assert p["p_red"].to_numpy() == pytest.approx(lvl.to_numpy())


def test_model_weighting_gives_each_model_equal_weight(scores, cfg):
    p = ensemble.probabilities(scores, cfg)                                   # default: per model
    m = ensemble.probabilities(scores, {**cfg, "ensemble": {**cfg["ensemble"], "weighting": "member"}})
    # ECMWF has 4 members and GFS 2; per-model weights differ from per-member weights
    assert not np.allclose(p["p_red"], m["p_red"])
    w = ensemble.member_weights(scores, "model")
    assert scores.assign(w=w).groupby(["ward_id", "date"])["w"].sum().to_numpy() == pytest.approx(1.0)


def test_confidence_labels(cfg):
    scores = pd.DataFrame({"member": [f"x_m{i:02d}" for i in range(10)], "model": "x", "ward_id": "W1",
                           "date": pd.Timestamp("2024-05-22"), "htsi": 90.0, "mri": [85.0] * 8 + [70.0] * 2})
    scores["level"] = ["red"] * 8 + ["orange"] * 2
    p = ensemble.probabilities(scores, cfg).iloc[0]
    assert p["most_likely"] == "red" and p["p_red"] == pytest.approx(0.8) and p["confidence"] == "high"


def test_trigger_fires_within_lead_window(cfg):
    probs = pd.DataFrame({"ward_id": "W1", "date": pd.date_range("2024-05-20", periods=5),
                          "p_yellow": 1.0, "p_orange": 0.9, "p_red": [0.9, 0.5, 0.3, 0.6, 0.8]})
    t = ensemble.triggers(probs, cfg, issue_date="2024-05-20")
    # day 0 (issue day) and lead 4 are outside 1..3; lead 2 (0.3) is below 0.40
    assert t["lead_days"].tolist() == [1, 3]
    assert (t["action"] == "orange_preparedness").all()


def test_split_members_trims_run_start_and_drops_gappy_members():
    times = [f"2026-09-22T{h:02d}:00" for h in range(8)]
    base = {"temperature_2m": [None, None, 30, 31, 32, 33, 34, 35]}
    hourly = {"time": times}
    for old in weather._OPEN_METEO_VARS:
        vals = [None, None] + [10.0] * 6
        hourly[old] = vals
        hourly[old + "_member01"] = vals
        hourly[old + "_member02"] = vals[:4] + [None] + vals[5:]      # gap mid-run → dropped
    hourly["temperature_2m"] = base["temperature_2m"]
    out = weather.split_members({"hourly": hourly}, "ecmwf_ifs025", "Asia/Kolkata")
    assert sorted(out) == ["ecmwf_ifs025_m00", "ecmwf_ifs025_m01"]
    assert len(out["ecmwf_ifs025_m00"]) == 6
