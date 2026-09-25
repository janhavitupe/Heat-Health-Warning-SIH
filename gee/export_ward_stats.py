"""Per-ward zonal statistics from Google Earth Engine.

Computes, for every ward in data/processed/wards.geojson:
  population, pop_60plus, pop_under5   WorldPop 2020 constrained age-sex structures (sum)
  lst_day                              Landsat 8/9 summer daytime LST, °C (mean)
  lst_night                            MODIS MOD11A2 summer night-time LST, °C (mean)
  ndvi                                 Sentinel-2 summer median NDVI (mean)
  builtup_frac, tree_cover             ESA WorldCover v200 class shares

Writes data/manual/gee_ward_stats.csv, which scripts/build_wards.py merges.

Setup (once):
  pip install earthengine-api
  earthengine authenticate
Usage:
  python gee/export_ward_stats.py --project <your-gcp-project-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from heatrisk.config import load_config  # noqa: E402

YEARS = range(2021, 2026)
AGES_60PLUS = [60, 65, 70, 75, 80]
AGES_UNDER5 = [0, 1]


def summer_filter(cfg: dict) -> ee.Filter:
    months = cfg["downscaling"]["lst_season_months"]
    return ee.Filter.And(
        ee.Filter.calendarRange(min(YEARS), max(YEARS), "year"),
        ee.Filter.calendarRange(min(months), max(months), "month"),
    )


def worldpop(region: ee.Geometry) -> ee.Image:
    img = (
        ee.ImageCollection("WorldPop/GP/100m/pop_age_sex_cons_unadj")
        .filter(ee.Filter.eq("country", "IND"))
        .filter(ee.Filter.eq("year", 2020))
        .filterBounds(region)
        .mosaic()
    )
    old = [f"{s}_{a}" for s in "MF" for a in AGES_60PLUS]
    young = [f"{s}_{a}" for s in "MF" for a in AGES_UNDER5]
    return ee.Image.cat(
        img.select("population").rename("population"),
        img.select(old).reduce(ee.Reducer.sum()).rename("pop_60plus"),
        img.select(young).reduce(ee.Reducer.sum()).rename("pop_under5"),
    )


def landsat_lst(region: ee.Geometry, flt: ee.Filter) -> ee.Image:
    def prep(img: ee.Image) -> ee.Image:
        qa = img.select("QA_PIXEL")
        clear = (
            qa.bitwiseAnd(1 << 1).eq(0)       # dilated cloud
            .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
            .And(qa.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
        )
        lst = img.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
        return lst.updateMask(clear).rename("lst_day")

    col = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterBounds(region)
        .filter(flt)
        .map(prep)
    )
    return col.median()


def modis_night_lst(region: ee.Geometry, flt: ee.Filter) -> ee.Image:
    return (
        ee.ImageCollection("MODIS/061/MOD11A2")
        .filterBounds(region)
        .filter(flt)
        .select("LST_Night_1km")
        .median()
        .multiply(0.02)
        .subtract(273.15)
        .rename("lst_night")
    )


def sentinel_ndvi(region: ee.Geometry, flt: ee.Filter) -> ee.Image:
    def prep(img: ee.Image) -> ee.Image:
        scl = img.select("SCL")
        clear = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return img.normalizedDifference(["B8", "B4"]).updateMask(clear).rename("ndvi")

    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filter(flt)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .map(prep)
        .median()
    )


def worldcover() -> ee.Image:
    m = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    return ee.Image.cat(m.eq(50).rename("builtup_frac"), m.eq(10).rename("tree_cover"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    args = ap.parse_args()
    ee.Initialize(project=args.project)

    cfg = load_config()
    gj = json.loads((ROOT / "data" / "processed" / "wards.geojson").read_text(encoding="utf-8"))
    wards = ee.FeatureCollection(
        [ee.Feature(f["geometry"], {"ward_id": f["properties"]["ward_id"]}) for f in gj["features"]]
    )
    region = wards.geometry().bounds()
    flt = summer_filter(cfg)

    # (image, reducer, scale in metres)
    jobs = [
        (worldpop(region), ee.Reducer.sum(), 100),
        (landsat_lst(region, flt), ee.Reducer.mean(), 30),
        (modis_night_lst(region, flt), ee.Reducer.mean(), 1000),
        (sentinel_ndvi(region, flt), ee.Reducer.mean(), 10),
        (worldcover(), ee.Reducer.mean(), 10),
    ]

    frames = []
    for img, reducer, scale in jobs:
        bands = img.bandNames().getInfo()
        fc = img.reduceRegions(collection=wards, reducer=reducer, scale=scale, tileScale=4)
        df = pd.DataFrame([f["properties"] for f in fc.getInfo()["features"]]).set_index("ward_id")
        # Earth Engine names a single-band result after the reducer ("mean"/"sum")
        if len(bands) == 1:
            df = df.rename(columns={"mean": bands[0], "sum": bands[0]})
        frames.append(df[bands])
        print(f"  {', '.join(bands)} done")

    out = pd.concat(frames, axis=1).round(4).reset_index()

    dest = ROOT / "data" / "manual" / "gee_ward_stats.csv"
    out.to_csv(dest, index=False)
    print(f"Wrote {len(out)} wards to {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
