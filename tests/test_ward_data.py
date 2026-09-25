"""Checks on the frozen ward dataset produced by scripts/build_wards.py."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "wards.parquet").exists(), reason="run scripts/build_wards.py first"
)


@pytest.fixture(scope="module")
def wards():
    return pd.read_parquet(PROCESSED / "wards.parquet")


def test_48_unique_wards(wards):
    assert len(wards) == 48
    assert wards["ward_id"].is_unique
    assert wards["ward_no"].tolist() == list(range(1, 49))


def test_boundaries_valid_and_inside_city_bbox():
    g = gpd.read_file(PROCESSED / "wards.geojson")
    assert g.is_valid.all()
    assert not g.has_z.any(), "3D coordinates break Earth Engine"
    w, s, e, n = g.total_bounds
    assert 72.4 < w < e < 72.75 and 22.85 < s < n < 23.2


def test_city_area_plausible(wards):
    # AMC covers roughly 440–470 km²
    assert 400 < wards["area_km2"].sum() < 500


def test_every_column_has_provenance(wards):
    sources = pd.read_csv(ROOT / "data" / "manual" / "column_sources.csv")
    assert set(wards.columns) <= set(sources["column"])


def test_shares_are_fractions(wards):
    cols = [c for c in wards.columns if c.endswith("_share") or c in ("builtup_frac", "tree_cover")]
    for c in cols:
        vals = wards[c].dropna()
        assert ((vals >= 0) & (vals <= 1)).all(), c


def test_factors_within_config_bounds(wards):
    from heatrisk.config import load_config

    risk = load_config()["risk"]
    for col, key in (("historical_factor", "historical_factor"), ("capacity_factor", "capacity_factor")):
        vals = wards[col].dropna()
        assert ((vals >= risk[key]["min"]) & (vals <= risk[key]["max"])).all(), col
