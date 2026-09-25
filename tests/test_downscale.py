import copy

import numpy as np
import pandas as pd
import pytest

from heatrisk import downscale, pipeline, thermal
from heatrisk.config import ConfigError, validate


@pytest.fixture
def lst_wards(wards):
    """Toy wards with satellite attributes: W5 is the dense, bare, warm-night ward."""
    return wards.assign(
        lst_day=[45.0, 46.0, 47.0, 48.0, 49.0],
        lst_night=[27.0, 28.0, 29.0, 30.0, 31.0],
        tree_cover=[0.20, 0.15, 0.10, 0.05, 0.0],
    )


def test_anomalies_are_relative_to_city_mean(lst_wards):
    a = downscale.lst_anomalies(lst_wards)
    assert a["lst_night_anom"].tolist() == pytest.approx([-2, -1, 0, 1, 2])
    assert a["lst_day_anom"].sum() == pytest.approx(0)


def test_night_hours_shift_by_beta_night(lst_wards, wx, cfg):
    out = downscale.downscale(wx, "W5", lst_wards, cfg)
    ds = cfg["downscaling"]
    night, full_sun = wx["ghi"] == 0, wx["ghi"] >= ds["day_transition_wm2"]
    shift = out["t2m"] - wx["t2m"]
    assert shift[night].to_numpy() == pytest.approx(ds["beta_night"] * 2.0)
    assert shift[full_sun].to_numpy() == pytest.approx(ds["beta_day"] * 2.0)
    morning = ~night & ~full_sun                               # partial sun: between the two
    lo, hi = sorted([ds["beta_day"] * 2.0, ds["beta_night"] * 2.0])
    assert shift[morning].between(lo - 1e-9, hi + 1e-9).all()
    assert out.attrs["downscaling"]["missing"] == []


def test_day_hours_use_day_anomaly(lst_wards, wx, cfg):
    c = copy.deepcopy(cfg)
    c["downscaling"]["beta_day"] = 0.3
    out = downscale.downscale(wx, "W1", lst_wards, c)
    day = wx["ghi"] >= c["downscaling"]["day_transition_wm2"]
    assert (out["t2m"] - wx["t2m"])[day].to_numpy() == pytest.approx(0.3 * -2.0)


def test_dew_point_held_and_humidity_recomputed(lst_wards, wx, cfg):
    out = downscale.downscale(wx, "W5", lst_wards, cfg)
    night = wx["ghi"] == 0
    assert out["td"].to_numpy() == pytest.approx(wx["td"].to_numpy())
    assert (out["rh"][night] < wx["rh"][night]).all()          # warmer air, same moisture
    assert out["rh"].to_numpy() == pytest.approx(
        downscale.relative_humidity(out["t2m"], out["td"]), abs=1e-9)
    # recomputing RH from the unchanged frame reproduces the input to within rounding
    assert downscale.relative_humidity(wx["t2m"], wx["td"]) == pytest.approx(wx["rh"].to_numpy(), abs=1e-6)


def test_cooling_never_pushes_dew_point_above_air(wx, lst_wards, cfg):
    c = copy.deepcopy(cfg)
    c["downscaling"]["beta_night"] = 1.0
    moist = wx.assign(td=wx["t2m"] - 0.5)                      # near-saturated air
    out = downscale.downscale(moist, "W1", lst_wards, c)      # W1 is cooled by 2 °C at night
    assert (out["td"] <= out["t2m"]).all()
    assert (out["rh"] <= 100).all()


def test_missing_lst_means_no_adjustment(wards, wx, cfg):
    out = downscale.downscale(wx, "W3", wards, cfg)            # toy wards have no LST columns
    assert out["t2m"].equals(wx["t2m"])
    assert out.attrs["downscaling"]["missing"] == ["lst_day", "lst_night"]


def test_tree_cover_cools_daytime_mrt_only(wx, cfg):
    bare = thermal.compute(wx, 23.02, 72.57, cfg)
    shaded = thermal.compute(wx, 23.02, 72.57, cfg, tree_cover=0.4)
    day = bare["cosz"] > 0.2
    assert (shaded["mrt"][day] < bare["mrt"][day] - 0.5).all()
    assert (shaded["utci"][day] < bare["utci"][day]).all()
    assert shaded["mrt"][bare["cosz"] <= 0].to_numpy() == pytest.approx(bare["mrt"][bare["cosz"] <= 0].to_numpy())
    assert thermal.compute(wx, 23.02, 72.57, cfg, tree_cover=np.nan)["mrt"].equals(bare["mrt"])


def test_pipeline_downscales_by_default(lst_wards, wx, cfg):
    warm = pipeline.score_ward("W5", wx, lst_wards, cfg)
    cool = pipeline.score_ward("W1", wx, lst_wards, cfg)
    raw = pipeline.score_ward("W5", wx, lst_wards, cfg, downscale=False)
    assert (warm["daily"]["tmin"] > cool["daily"]["tmin"]).all()
    assert (warm["daily"]["tmin"] > raw["daily"]["tmin"]).all()
    assert warm["downscaling"]["night"] == pytest.approx(cfg["downscaling"]["beta_night"] * 2.0)
    assert raw["downscaling"] == {}


def test_beta_must_be_a_fraction(cfg):
    bad = copy.deepcopy(cfg)
    bad["downscaling"]["beta_night"] = 1.5
    with pytest.raises(ConfigError, match="beta_night"):
        validate(bad)


def test_greening_regression_cools(cfg):
    """The what-if simulator relies on more vegetation meaning cooler nights."""
    reg = cfg["downscaling"]["lst_regression"]
    assert reg["night_ndvi"]["slope"] < 0
    assert reg["night_builtup_frac"]["slope"] > 0


@pytest.mark.skipif(not pipeline.WARDS_PARQUET.exists(), reason="run scripts/build_wards.py first")
def test_real_wards_night_offsets_vary(cfg):
    w = pd.read_parquet(pipeline.WARDS_PARQUET)
    night = [downscale.temperature_offsets(i, w, cfg)["night"] for i in w["ward_id"]]
    assert sum(night) == pytest.approx(0, abs=1e-9)
    assert max(night) - min(night) > 0.5
