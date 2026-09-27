import pandas as pd
import pytest

from heatrisk import scenarios
from heatrisk.pipeline import WARDS_PARQUET
from synth import synthetic_weather

pytestmark = pytest.mark.skipif(not WARDS_PARQUET.exists(), reason="run scripts/build_wards.py first")


@pytest.fixture(scope="module")
def wards():
    return pd.read_parquet(WARDS_PARQUET)


@pytest.fixture(scope="module")
def hot():
    return synthetic_weather(days=4, tmax=46.5, tmin=31)


def test_tree_cover_cools_nights_and_lowers_risk_only_in_chosen_ward(wards, hot, cfg):
    r = scenarios.run(wards, hot, [{"lever": "tree_cover", "wards": ["AMC-35"], "pp": 10}], cfg)
    assert r["label"] == "scenario_estimate" and [w["ward_id"] for w in r["wards"]] == ["AMC-35"]
    ch = r["wards"][0]["change"]
    assert ch["mean_tmin"] == pytest.approx(-0.25, abs=0.02)        # 0.727 × 0.1 × −11.33 × 0.3
    assert ch["mean_utci"] < 0 and ch["mean_mri"] < 0 and ch["pvi"] == 0
    assert r["changes"][0]["night_air_change_c"] == pytest.approx(-0.25, abs=0.01)


def test_other_wards_do_not_move(wards, cfg):
    scen, affected, _ = scenarios.apply(wards, [{"lever": "tree_cover", "wards": ["AMC-35"], "pp": 20}], cfg)
    from heatrisk.downscale import temperature_offsets
    for wid in ("AMC-01", "AMC-40"):
        assert temperature_offsets(wid, scen, cfg)["night"] == pytest.approx(temperature_offsets(wid, wards, cfg)["night"])
    assert affected == ["AMC-35"]


def test_cool_roofs_lower_indoor_heat(wards, hot, cfg):
    r = scenarios.run(wards, hot, [{"lever": "cool_roofs", "wards": ["AMC-35"], "share": 0.5}], cfg)
    c = r["changes"][0]
    assert c["roof_share_after"] == pytest.approx(c["roof_share_before"] / 2, abs=0.001)
    assert r["wards"][0]["change"]["mean_mri"] < 0


def test_cool_roofs_report_missing_data(wards, hot, cfg):
    no_roofs = wards.assign(roof_sheet_share=float("nan"))
    r = scenarios.run(no_roofs, hot, [{"lever": "cool_roofs", "wards": ["AMC-35"], "share": 0.5}], cfg)
    assert "no effect" in r["changes"][0]["note"] and r["wards"][0]["change"]["mean_mri"] == 0


def test_roof_share_estimate_in_range(wards):
    s = wards["roof_sheet_share"]
    assert s.notna().all() and s.between(0.15, 0.55).all()      # between non-slum (17%) and slum (51%) rates


@pytest.mark.parametrize("change", [
    {"lever": "tree_cover", "wards": ["AMC-35"], "pp": 50},        # beyond the observed range
    {"lever": "tree_cover", "wards": ["AMC-99"], "pp": 5},
    {"lever": "cool_roofs", "wards": ["AMC-35"], "share": 1.5},
    {"lever": "magic"},
])
def test_invalid_changes_are_rejected(wards, hot, cfg, change):
    with pytest.raises(scenarios.ScenarioError):
        scenarios.run(wards, hot, [change], cfg)


@pytest.mark.skipif(not scenarios.ACCESS_CACHE.exists(), reason="run scripts/build_access.py first")
def test_cooling_centre_reduces_gap_and_pvi(wards, hot, cfg):
    import json
    site = json.loads((WARDS_PARQUET.parent / "cooling_sites.geojson").read_text())["features"][0]
    lon, lat = site["geometry"]["coordinates"]
    r = scenarios.run(wards, hot, [{"lever": "cooling_centre", "lon": lon, "lat": lat}], cfg)
    assert r["changes"][0]["people_newly_within_walk"] == pytest.approx(site["properties"]["people_newly_covered"], rel=0.01)
    assert all(w["change"]["pvi"] <= 0 for w in r["wards"]) and any(w["change"]["pvi"] < 0 for w in r["wards"])
