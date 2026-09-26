"""Fetch health facilities, cooling points, and candidate cooling-centre sites
from OpenStreetMap (Overpass API) for the pilot city bounding box.

Outputs:
  data/raw/osm/<layer>.json         raw Overpass responses (not committed)
  data/processed/osm_points.geojson one point per feature, tagged with layer

Usage:  python scripts/fetch_osm.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from heatrisk.config import load_config  # noqa: E402

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "heat-health-sih/0.1 (research prototype)", "Accept": "application/json"}

# layer -> (Overpass filters, role in the model)
LAYERS: dict[str, tuple[list[str], str]] = {
    "hospital": (['nwr["amenity"="hospital"]', 'nwr["healthcare"="hospital"]'], "health_facility"),
    "clinic": (
        ['nwr["amenity"~"^(clinic|doctors)$"]', 'nwr["healthcare"~"^(clinic|centre|doctor)$"]'],
        "health_facility",
    ),
    "drinking_water": (['nwr["amenity"~"^(drinking_water|water_point)$"]'], "cooling_point"),
    "park": (['nwr["leisure"~"^(park|garden)$"]'], "cooling_point"),
    "school": (['nwr["amenity"~"^(school|college)$"]'], "candidate_site"),
    "community_centre": (['nwr["amenity"="community_centre"]'], "candidate_site"),
    # BRTS / bus stations: the Heat Action Plan distributes drinking water there
    "brts_station": (['nwr["amenity"="bus_station"]', 'nwr["public_transport"="station"]["bus"="yes"]'], "cooling_point"),
    # Named as cooling centres in the Heat Action Plan but not run by AMC: sensitivity layer only
    "mall": (['nwr["shop"="mall"]'], "community_cooling"),
    "place_of_worship": (['nwr["amenity"="place_of_worship"]'], "community_cooling"),
}


def query(filters: list[str], bbox: dict) -> dict:
    b = f'({bbox["south"]},{bbox["west"]},{bbox["north"]},{bbox["east"]})'
    body = "".join(f"{f}{b};" for f in filters)
    q = f"[out:json][timeout:90];({body});out center tags;"
    for attempt in range(4):
        r = requests.post(OVERPASS_URL, data={"data": q}, headers=HEADERS, timeout=120)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        wait = 15 * (attempt + 1)
        print(f"  Overpass returned {r.status_code}; retrying in {wait}s")
        time.sleep(wait)
    raise RuntimeError("Overpass request failed after retries")


def to_rows(layer: str, role: str, data: dict) -> list[dict]:
    rows = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        rows.append(
            {
                "osm_id": f'{el["type"]}/{el["id"]}',
                "layer": layer,
                "role": role,
                "name": tags.get("name") or tags.get("name:en"),
                "beds": tags.get("beds"),
                "source": "OpenStreetMap",
                "geometry": Point(lon, lat),
            }
        )
    return rows


def main() -> None:
    cfg = load_config()
    raw_dir = ROOT / "data" / "raw" / "osm"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for layer, (filters, role) in LAYERS.items():
        print(f"Fetching {layer} ...")
        data = query(filters, cfg["city"]["bbox"])
        (raw_dir / f"{layer}.json").write_text(json.dumps(data), encoding="utf-8")
        layer_rows = to_rows(layer, role, data)
        print(f"  {len(layer_rows)} features")
        rows.extend(layer_rows)
        time.sleep(2)  # be polite to the public Overpass server

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    # A feature matching two filters (e.g. amenity=hospital and healthcare=hospital) appears once per layer
    gdf = gdf.drop_duplicates(subset=["osm_id", "layer"])
    out = ROOT / "data" / "processed" / "osm_points.geojson"
    gdf.to_file(out, driver="GeoJSON")
    print(f"Wrote {len(gdf)} points to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
