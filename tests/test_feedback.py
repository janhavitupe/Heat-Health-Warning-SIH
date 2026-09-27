import pandas as pd
import pytest

from heatrisk import feedback


@pytest.fixture
def scores():
    days = ["2024-05-22", "2024-05-23"]
    return pd.DataFrame([{"ward_id": w, "date": d, "population": 100_000, "mri": m}
                         for d in days for w, m in (("A", 90.0), ("B", 90.0), ("C", 45.0))])


def test_expected_follows_population_times_mri(scores):
    obs = pd.Series({"A": 4, "B": 4, "C": 2})
    exp = feedback.expected(obs, scores[scores["date"] == "2024-05-23"])
    assert exp.sum() == pytest.approx(10) and exp["A"] == pytest.approx(4) and exp["C"] == pytest.approx(2)


def test_flag_needs_ratio_minimum_and_significance(scores, cfg):
    counts = pd.DataFrame({"ward_id": ["A", "B", "C", "A", "C"], "date": ["2024-05-23"] * 3 + ["2024-05-22"] * 2,
                           "reports": [1, 1, 9, 2, 1]})
    f = feedback.flags(counts, scores, cfg)
    assert f[["ward_id", "date"]].values.tolist() == [["C", "2024-05-23"]]    # C has far more than its low-risk share


def test_recalibration_is_a_bounded_significant_only_proposal(scores, cfg):
    counts = pd.DataFrame({"ward_id": ["A", "B", "C"] * 2, "date": ["2024-05-22"] * 3 + ["2024-05-23"] * 3,
                           "reports": [4, 4, 20, 4, 4, 20]})
    r = feedback.recalibrate(counts, scores, pd.Series(dtype=float), cfg).set_index("ward_id")
    b = cfg["risk"]["historical_factor"]
    assert r.loc["C", "evidence"] == "significant" and r.loc["C", "proposed_h_m"] == b["max"]
    assert r["proposed_h_m"].between(b["min"], b["max"]).all()
    assert cfg["feedback"]["auto_apply_recalibration"] is False


def test_synthetic_reports_are_reproducible_and_inject_the_anomaly(scores):
    a = feedback.synthetic_reports(scores, total=30, seed=1, anomaly={"ward_id": "C", "dates": ["2024-05-23"], "extra": 5})
    b = feedback.synthetic_reports(scores, total=30, seed=1, anomaly={"ward_id": "C", "dates": ["2024-05-23"], "extra": 5})
    assert a.equals(b)
    assert a.set_index(["ward_id", "date"]).loc[("C", "2024-05-23"), "reports"] >= 5
