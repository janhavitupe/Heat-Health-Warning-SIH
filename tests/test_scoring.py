import numpy as np
import pandas as pd
import pytest

from heatrisk import indices, pipeline, risk, vulnerability
from synth import synthetic_weather


# ---------- indices ----------

def test_normalize_clamps():
    assert indices.normalize(20, 26, 46) == 0
    assert indices.normalize(36, 26, 46) == 50
    assert indices.normalize(60, 26, 46) == 100


def test_category_bands(cfg):
    bands = cfg["htsi"]["categories"]
    assert indices.category(20, bands) == "low"
    assert indices.category(20.01, bands) == "moderate"
    assert indices.category(100, bands) == "extreme"


def _daily(cfg, **kw):
    from heatrisk import thermal
    wx = synthetic_weather(**kw)
    return indices.daily_indicators(thermal.compute(wx, 23.02, 72.57, cfg), cfg)


def test_persistence_counts_consecutive_hot_days(cfg):
    d = indices.htsi(_daily(cfg, days=4), cfg, roof_sheet_share=0.0)
    assert d["hot_run_days"].tolist() == [1, 2, 3, 4]
    assert d["pts_persist"].tolist() == [0.0, 2.5, 5.0, 7.5]


def test_persistence_resets_after_cool_day(cfg):
    d = _daily(cfg, days=3)
    d.loc[d.index[1], ["utci", "wbgt", "heat_index"]] = [20, 18, 20]
    out = indices.htsi(d, cfg, roof_sheet_share=0.0)
    assert out["hot_run_days"].tolist() == [1, 0, 1]


def test_night_points_scale_with_tmin(cfg):
    cool = indices.htsi(_daily(cfg, tmin=26), cfg, 0.0)
    warm = indices.htsi(_daily(cfg, tmin=29.5), cfg, 0.0)
    hot = indices.htsi(_daily(cfg, tmin=32), cfg, 0.0)
    assert (cool["pts_night"] == 0).all()
    assert (0 < warm["pts_night"]).all() and (warm["pts_night"] < 10).all()
    assert (hot["pts_night"] == 10).all()


def test_indoor_points_need_a_hot_day_and_roof_data(cfg):
    hot = _daily(cfg, tmin=26)
    assert (indices.htsi(hot, cfg, 0.5)["pts_indoor"] == 5.0).all()
    assert (indices.htsi(hot, cfg, None)["pts_indoor"] == 0).all()
    assert indices.htsi(hot, cfg, None)["indoor_data_missing"].all()
    mild = _daily(cfg, tmax=33, tmin=24)
    assert (indices.htsi(mild, cfg, 0.5)["pts_indoor"] == 0).all()


def test_indoor_points_boosted_on_hot_nights_but_capped(cfg):
    d = indices.htsi(_daily(cfg, tmin=32), cfg, 0.5)
    assert (d["pts_indoor"] == 7.5).all()
    d = indices.htsi(_daily(cfg, tmin=32), cfg, 1.0)
    assert (d["pts_indoor"] == 10.0).all()


def test_htsi_capped_at_100(cfg):
    d = indices.htsi(_daily(cfg, days=4, tmax=47, tmin=33), cfg, 1.0)
    assert d["htsi"].max() == 100 and d["htsi_raw"].max() > 100


# ---------- vulnerability ----------

def test_pvi_neutralizes_flat_and_missing_indicators(cfg, wards):
    table, status = vulnerability.compute_pvi(wards, cfg)
    assert status["elderly_share"] == "neutral: no variation across wards"
    assert status["informal_housing_share"] == "neutral: data missing"
    assert status["outdoor_worker_share"] == "used"
    assert (table["elderly_share_n"] == 0.5).all()
    assert table["outdoor_worker_share_n"].tolist() == pytest.approx([0, 0.25, 0.5, 0.75, 1.0])


def test_pvi_in_range_and_ordered(cfg, wards):
    table, _ = vulnerability.compute_pvi(wards, cfg)
    assert table["pvi"].between(0, 100).all()
    assert table["pvi"].is_monotonic_increasing  # toy wards get steadily more vulnerable


# ---------- risk ----------

def test_risk_zero_without_heat(cfg):
    out = risk.score(pd.Series([0.0]), pvi=90, h_m=1.2, c_h=1.3, cfg=cfg)
    assert out["mri"].iloc[0] == 0 and out["alert_mri"].iloc[0] == "green"


def test_least_vulnerable_ward_keeps_floor_share(cfg):
    out = risk.score(pd.Series([100.0]), pvi=0, h_m=1.0, c_h=1.0, cfg=cfg)
    assert out["mri"].iloc[0] == pytest.approx(100 * cfg["risk"]["vulnerability_floor"])


def test_factor_defaults_and_clamps(cfg):
    b = cfg["risk"]["historical_factor"]
    assert risk.factor_or_default(np.nan, b) == (1.0, True)
    assert risk.factor_or_default(5.0, b) == (b["max"], False)


def test_alert_band_edges(cfg):
    out = risk.score(pd.Series([40.0, 60.0, 80.0, 100.0]), pvi=100, h_m=1.0, c_h=1.0, cfg=cfg)
    assert out["alert_mri"].tolist() == ["green", "yellow", "orange", "red"]


# ---------- pipeline + explanation ----------

@pytest.fixture
def scored(cfg, wards, wx):
    return pipeline.score_ward("W4", wx, wards, cfg)


def test_explanations_sum_exactly_to_scores(scored):
    for date, ex in scored["explanations"].items():
        for target in ("mri", "hri"):
            e = ex[target]
            assert sum(c.points for c in e.contributions) == pytest.approx(e.score, abs=1e-9)


def test_explanation_flags_neutral_and_missing_data(cfg, wards, wx):
    res = pipeline.score_ward("W5", wx, wards, cfg)
    e = next(iter(res["explanations"].values()))["mri"]
    notes = {c.key: c.note for c in e.contributions}
    assert "midpoint" in notes["elderly_share"]
    assert "default 1.0" in notes["factor"]           # W5 has no historical factor


def test_historical_factor_raises_mri_only(cfg, wards, wx):
    d = pipeline.score_ward("W4", wx, wards, cfg)["daily"]   # H_m = 1.1, C_h default 1.0
    assert (d["mri_raw"] > d["hri_raw"]).all()


def test_summary_is_readable(scored):
    e = next(iter(scored["explanations"].values()))["mri"]
    s = e.summary()
    assert "model estimate" in s and "UTCI" in s


def test_golden_day(cfg, wards, wx):
    """Regression guard: fixed synthetic input → fixed output. Update deliberately if the model changes."""
    d = pipeline.score_ward("W3", wx, wards, cfg)["daily"].iloc[0]
    assert d["htsi"] == pytest.approx(GOLDEN["htsi"], abs=0.05)
    assert d["mri"] == pytest.approx(GOLDEN["mri"], abs=0.05)


GOLDEN = {"htsi": 98.42, "mri": 65.941}
