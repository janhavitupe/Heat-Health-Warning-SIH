import numpy as np
import pandas as pd
import pytest
import thermofeel as tf
from pythermalcomfort.models import heat_index_rothfusz, utci as ptc_utci

from heatrisk import thermal
from synth import synthetic_weather


def test_solar_noon_near_zenith_in_late_may():
    # Ahmedabad (23.0 N) near the summer solstice: sun almost overhead at solar noon (~12:40 IST)
    idx = pd.DatetimeIndex(["2024-06-21 13:10"], tz="Asia/Kolkata")  # hour ending 13:10 → mid 12:40
    cosz = thermal.cos_solar_zenith(idx, 23.0, 72.6)[0]
    assert cosz > 0.99


def test_sun_below_horizon_at_night():
    idx = pd.date_range("2024-05-20 22:00", periods=6, freq="h", tz="Asia/Kolkata")
    assert (thermal.cos_solar_zenith(idx, 23.0, 72.6) < 0).all()


def test_mrt_far_above_air_in_sun_and_below_at_night(cfg, wx):
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    noon = out.between_time("12:00", "14:00")
    night = out.between_time("01:00", "04:00")
    assert (noon["mrt"] - noon["t2m"]).min() > 15
    assert ((night["mrt"] - night["t2m"]) < 0).all()
    assert ((night["mrt"] - night["t2m"]) > -10).all()


def test_utci_matches_pythermalcomfort(cfg):
    wx = synthetic_weather(days=2, tmax=46, tmin=28)
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    ref = ptc_utci(tdb=wx.t2m.values, tr=out.mrt.values, v=wx.wind10.values, rh=wx.rh.values,
                   limit_inputs=False)
    assert np.nanmax(np.abs(out["utci"].values - np.asarray(ref.utci))) < 0.5


def test_heat_index_matches_pythermalcomfort(cfg, wx):
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    ref = heat_index_rothfusz(tdb=wx.t2m.values, rh=wx.rh.values, limit_inputs=False)
    assert np.nanmax(np.abs(out["heat_index"].values - np.asarray(ref.hi))) < 0.5


def test_wbgt_liljegren_close_to_simpler_method(cfg, wx):
    """Two independent WBGT methods should broadly agree (different physics, so ±2.5 °C)."""
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    simple = tf.calculate_wbgt(t2_k=wx.t2m.values + 273.15, mrt=out.mrt.values + 273.15,
                               va=wx.wind10.values, td_k=wx.td.values + 273.15) - 273.15
    day = out["cosz"] > 0.3
    assert np.abs(out["wbgt"].values[day] - simple[day]).max() < 2.5


@pytest.mark.parametrize("wind", [0.0, 0.1, 40.0])
def test_extreme_wind_is_clamped_not_nan(cfg, wind):
    wx = synthetic_weather(days=1)
    wx["wind10"] = wind
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    assert out[["utci", "wbgt", "heat_index"]].notna().all().all()


def test_saturated_air_is_finite(cfg):
    wx = synthetic_weather(days=1, rh_min=99.9, rh_max=100.0)
    out = thermal.compute(wx, 23.02, 72.57, cfg)
    assert np.isfinite(out[["mrt", "utci", "wbgt", "heat_index"]].values).all()
