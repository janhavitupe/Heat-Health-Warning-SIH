"""Export the WorldPop 2020 100 m population grid for every ward (cooling and health access, Phase 6).

One row per populated 100 m cell: lon, lat (cell centre), pop, ward_id.
Writes data/processed/pop_grid.parquet.

Usage:  python gee/export_pop_grid.py --project <gcp-project>
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import ee
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    ee.Initialize(project=args.project)

    gj = json.loads((ROOT / "data" / "processed" / "wards.geojson").read_text(encoding="utf-8"))
    pop = (ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq("country", "IND"))
           .filter(ee.Filter.eq("year", 2020)).mosaic().rename("pop"))
    img = pop.addBands(ee.Image.pixelLonLat())
    frames = []
    for f in gj["features"]:
        wid = f["properties"]["ward_id"]
        geom = ee.Geometry(f["geometry"])
        cells = img.sample(region=geom, scale=100, projection=pop.projection().atScale(100), geometries=False)
        # CSV download: getInfo() stops at 5,000 features, and large wards have more cells
        url = cells.getDownloadURL(filetype="csv", selectors=["pop", "longitude", "latitude"])
        df = pd.read_csv(io.StringIO(requests.get(url, timeout=300).text)).rename(columns={"longitude": "lon", "latitude": "lat"})
        df = df[df["pop"] > 0]
        df["ward_id"] = wid
        frames.append(df[["lon", "lat", "pop", "ward_id"]])
        print(f"  {wid}: {len(df)} cells, {df['pop'].sum():,.0f} people", flush=True)
    out = pd.concat(frames, ignore_index=True)
    dest = ROOT / "data" / "processed" / "pop_grid.parquet"
    out.to_parquet(dest, index=False)
    print(f"Wrote {len(out)} cells ({out['pop'].sum():,.0f} people) to {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
