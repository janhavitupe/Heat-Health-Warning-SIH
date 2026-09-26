"""Geocode AMC Urban Health Centres (data/manual/amc_uhc_list.csv) with OpenStreetMap Nominatim.

Each centre is looked up by its area name, then its address. A hit is kept only
if it falls inside a ward whose AMC zone matches the zone given in the AMC list;
otherwise the row is left without coordinates and flagged for manual entry.
Results are written back to the CSV (lat, lon, ward_id_guess, coord_quality), so
the script only queries rows that are still missing coordinates.

Usage:  python scripts/geocode_uhcs.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "manual" / "amc_uhc_list.csv"
URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "heat-health-sih/0.1 (research prototype)"}
# The AMC list uses the older zone names for the western extension
ZONE_ALIASES = {"NEW WEST": {"NORTH WEST", "SOUTH WEST", "WEST"}}


def lookup(q: str):
    r = requests.get(URL, params={"q": q, "format": "json", "limit": 3, "countrycodes": "in"}, headers=HEADERS, timeout=30)
    time.sleep(1.1)                      # Nominatim usage policy: at most 1 request per second
    r.raise_for_status()
    return [(float(h["lat"]), float(h["lon"])) for h in r.json()]


def main() -> None:
    uhc = pd.read_csv(CSV)
    for col in ("lat", "lon"):
        uhc[col] = pd.to_numeric(uhc[col], errors="coerce")
    if "coord_quality" not in uhc:
        uhc["coord_quality"] = pd.NA
    wards = gpd.read_file(ROOT / "data" / "processed" / "wards.geojson")
    zones = pd.read_parquet(ROOT / "data" / "processed" / "wards.parquet").set_index("ward_id")["zone"].str.upper()

    todo = uhc.index[uhc["lat"].isna()]   # includes earlier "not_found" rows, which are retried
    print(f"{len(todo)} of {len(uhc)} centres need coordinates")
    for i in todo:
        row = uhc.loc[i]
        area = str(row["area_name"]).title()
        zone = str(row["zone"]).upper()
        ok_zones = ZONE_ALIASES.get(zone, {zone})
        words = area.split()
        # AMC writes area names as "<ward> <locality>" (e.g. "Vatva Madninagar"): also try each part
        queries = [(f"{area}, Ahmedabad", "nominatim_area")]
        if len(words) > 1:
            queries += [(f"{' '.join(words[1:])}, Ahmedabad", "nominatim_locality"),
                        (f"{words[0]}, Ahmedabad", "nominatim_ward_name")]
        queries.append((f"{row['name_and_address']}, Ahmedabad", "nominatim_address"))
        for q, quality in queries:
            hit = None
            for lat, lon in lookup(q):
                w = wards[wards.contains(Point(lon, lat))]
                if len(w) and zones[w.ward_id.iloc[0]] in ok_zones:
                    hit = (lat, lon, w.ward_id.iloc[0])
                    break
            if hit:
                uhc.loc[i, ["lat", "lon", "ward_id_guess", "coord_quality"]] = [hit[0], hit[1], hit[2], quality]
                break
        else:
            # last resort: the centroid of the 2015 ward with the same name, clearly labelled
            names = wards.assign(key=wards.ward_name.str.upper().str.replace(r"[^A-Z]", "", regex=True))
            match = names[names.key == words[0].upper()]
            if len(match):
                c = match.to_crs(32643).geometry.centroid.to_crs(4326).iloc[0]
                uhc.loc[i, ["lat", "lon", "ward_id_guess", "coord_quality"]] = [c.y, c.x, match.ward_id.iloc[0], "ward_centroid"]
            else:
                uhc.loc[i, "coord_quality"] = "not_found"
        print(f"  {area:30s} {uhc.loc[i, 'coord_quality']}")
    uhc.to_csv(CSV, index=False)
    print(uhc["coord_quality"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    sys.exit(main())
