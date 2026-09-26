"""Build the frozen ward dataset for Phase 0.

Inputs:
  data/raw/amc_wards_datameet.geojson       ward boundaries (DataMeet, CC BY-SA 2.5 IN)
  data/raw/amc_facilities_datameet.kml      AMC libraries, ward/zonal offices
  data/processed/osm_points.geojson         from scripts/fetch_osm.py
  data/manual/ward_attributes.csv           census / survey attributes entered by hand
  data/manual/slum_ward_stats.csv           slum huts per ward (scripts/extract_slums.py)
  data/manual/column_sources.csv            provenance of every ward column

Outputs:
  data/processed/wards.geojson              boundaries + ids
  data/processed/wards.parquet              one row per ward, all static attributes
  data/processed/cooling_points.geojson     cooling points + candidate sites (all sources)
  data/processed/completeness.csv           fill rate per column (the Phase 0 exit check)

Usage:  python scripts/build_wards.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from heatrisk import access as access_mod  # noqa: E402
from heatrisk.config import load_config  # noqa: E402

RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
OUT = ROOT / "data" / "processed"
KML_NS = {"k": "http://www.opengis.net/kml/2.2"}
GEE_COLUMNS = [
    "population", "pop_60plus", "pop_under5",
    "lst_day", "lst_night", "ndvi", "builtup_frac", "tree_cover",
]

# KML folder name -> (layer, role). Public buildings are existing cooling options: the Heat
# Action Plan activates "temples, public buildings, malls" as cooling centres during alerts.
KML_LAYERS = {
    "library": ("library", "cooling_point"),
    "Ward Office": ("ward_office", "cooling_point"),
}


def load_wards() -> gpd.GeoDataFrame:
    g = gpd.read_file(RAW / "amc_wards_datameet.geojson")
    # Source was exported from KML with a constant z=0; Earth Engine rejects 3D coordinates
    g["geometry"] = shapely.force_2d(g.geometry.values)
    parts = g["Name"].str.strip().str.split(" ", n=1, expand=True)
    g["ward_no"] = parts[0].astype(int)
    g["ward_name"] = parts[1].str.title()
    g["ward_id"] = g["ward_no"].map(lambda n: f"AMC-{n:02d}")
    g = g.drop(columns="Name").sort_values("ward_no").reset_index(drop=True)
    return g[["ward_id", "ward_no", "ward_name", "geometry"]]


def _kml_name(name: str | None, layer: str) -> str | None:
    """AMC ward offices are named by ward only ("Odhav"); make the place type explicit."""
    if name and layer == "ward_office" and "office" not in name.lower():
        return f"{name.strip()} Ward Office"
    return name


def load_kml_points() -> gpd.GeoDataFrame:
    tree = ET.parse(RAW / "amc_facilities_datameet.kml")
    rows = []
    for folder in tree.getroot().iter("{http://www.opengis.net/kml/2.2}Folder"):
        fname = folder.findtext("k:name", default="", namespaces=KML_NS).strip()
        if fname not in KML_LAYERS:
            continue
        layer, role = KML_LAYERS[fname]
        for pm in folder.findall("k:Placemark", KML_NS):
            coords = pm.findtext(".//k:Point/k:coordinates", default="", namespaces=KML_NS).strip()
            if not coords:
                continue
            lon, lat = map(float, coords.split(",")[:2])
            rows.append(
                {
                    "osm_id": None,
                    "layer": layer,
                    "role": role,
                    "name": _kml_name(pm.findtext("k:name", default=None, namespaces=KML_NS), layer),
                    "beds": None,
                    "source": "AMC via DataMeet",
                    "geometry": Point(lon, lat),
                }
            )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def load_public_health_points() -> gpd.GeoDataFrame:
    """AMC Urban Health Centres (geocoded by scripts/geocode_uhcs.py) and the major public hospitals."""
    rows = []
    uhc = pd.read_csv(MANUAL / "amc_uhc_list.csv")
    for r in uhc.dropna(subset=["lat", "lon"]).itertuples():
        words = r.area_name.title().split()
        if len(words) == 2 and words[0] == words[1]:          # the AMC list repeats "<ward> <ward>"
            words = words[:1]
        rows.append({"osm_id": None, "layer": "uhc", "role": "health_facility",
                     "name": " ".join(words) + " Urban Health Centre",
                     "beds": None, "source": f"AMC UHC list 2024 ({r.coord_quality})", "geometry": Point(r.lon, r.lat)})
    beds = pd.read_csv(MANUAL / "hospital_beds.csv")
    for r in beds.dropna(subset=["lat", "lon"]).itertuples():
        rows.append({"osm_id": None, "layer": "public_hospital", "role": "health_facility", "name": r.name,
                     "beds": r.beds, "source": "data/manual/hospital_beds.csv", "geometry": Point(r.lon, r.lat)})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def count_by_ward(wards: gpd.GeoDataFrame, pts: gpd.GeoDataFrame, mask, name: str) -> pd.Series:
    j = gpd.sjoin(pts[mask], wards[["ward_id", "geometry"]], predicate="within")
    return j.groupby("ward_id").size().reindex(wards["ward_id"], fill_value=0).rename(name)


def main() -> None:
    cfg = load_config()
    metric = cfg["city"]["crs_metric"]

    wards = load_wards()
    wm = wards.to_crs(metric)
    wards["area_km2"] = (wm.area / 1e6).round(3)
    cent = wm.centroid
    cent_ll = gpd.GeoSeries(cent, crs=metric).to_crs(4326)
    wards["centroid_lat"] = cent_ll.y.round(5)
    wards["centroid_lon"] = cent_ll.x.round(5)

    # Points: OSM + AMC
    osm = gpd.read_file(OUT / "osm_points.geojson")
    pts = pd.concat([osm, load_kml_points(), load_public_health_points()], ignore_index=True)
    pts = gpd.GeoDataFrame(pts, crs="EPSG:4326")
    pts.to_file(OUT / "cooling_points.geojson", driver="GeoJSON")

    health = pts["role"] == "health_facility"
    counts = pd.concat(
        [
            count_by_ward(wards, pts, pts["layer"] == "hospital", "n_hospitals"),
            count_by_ward(wards, pts, pts["layer"] == "clinic", "n_clinics"),
            count_by_ward(wards, pts, pts["role"] == "cooling_point", "n_cooling_points"),
            count_by_ward(wards, pts, pts["role"] == "candidate_site", "n_candidate_sites"),
        ],
        axis=1,
    )
    wards = wards.merge(counts, left_on="ward_id", right_index=True)

    # Provisional healthcare-access proxy: straight-line km from ward centroid to the
    # nearest hospital. Replaced by population-weighted OSRM walking time in Phase 6.
    hosp_m = pts[pts["layer"] == "hospital"].to_crs(metric)
    near = gpd.sjoin_nearest(
        gpd.GeoDataFrame({"ward_id": wards["ward_id"]}, geometry=cent, crs=metric),
        hosp_m[["geometry"]],
        distance_col="d",
    ).groupby("ward_id")["d"].min()
    wards["nearest_hospital_km"] = (wards["ward_id"].map(near) / 1000).round(3)

    # Public hospital beds located in each ward. Capacity serving a ward is computed
    # later with a catchment method; this column is only where the beds physically are.
    beds = pd.read_csv(MANUAL / "hospital_beds.csv")
    wards["hospital_beds"] = wards["ward_id"].map(beds.groupby("ward_id")["beds"].sum()).fillna(0)

    # Hand-entered attributes (census, surveys)
    manual = pd.read_csv(MANUAL / "ward_attributes.csv", dtype={"ward_id": str})
    manual = manual.drop(columns=[c for c in ("ward_name",) if c in manual])
    wards = wards.merge(manual, on="ward_id", how="left", validate="one_to_one")

    # WorldPop + satellite zonal statistics exported by gee/export_ward_stats.py
    gee_path = MANUAL / "gee_ward_stats.csv"
    if gee_path.exists():
        gee = pd.read_csv(gee_path, dtype={"ward_id": str})
        wards = wards.merge(gee, on="ward_id", how="left", validate="one_to_one")
    else:
        print("gee_ward_stats.csv not found - population and satellite columns left empty")
        for col in GEE_COLUMNS:
            wards[col] = pd.NA
    # Walking access to cooling and health care (scripts/build_access.py)
    access_path = OUT / "ward_access.csv"
    if access_path.exists():
        wards = wards.merge(pd.read_csv(access_path, dtype={"ward_id": str}), on="ward_id", how="left",
                            validate="one_to_one")
    else:
        print("ward_access.csv not found - run scripts/build_access.py; access columns left empty")
        for col in ("cooling_gap", "cooling_gap_with_community", "health_walk_km", "cooling_desert"):
            wards[col] = pd.NA

    # Slum share from the AMC 2010-11 slum survey (scripts/extract_slums.py). Wards with no
    # listed slum get 0. The survey counted people in 2010; WorldPop is 2020, so the share is
    # a relative indicator (PVI min-max normalizes it), capped at 1.
    slum_path = MANUAL / "slum_ward_stats.csv"
    if slum_path.exists():
        slums = pd.read_csv(slum_path, dtype={"ward_id": str}).set_index("ward_id")
        wards["slum_huts"] = wards["ward_id"].map(slums["slum_huts"]).fillna(0)
        slum_pop = wards["ward_id"].map(slums["slum_pop_est"]).fillna(0)
        wards["informal_housing_share"] = (slum_pop / wards["population"]).clip(upper=1.0)
    else:
        print("slum_ward_stats.csv not found - informal_housing_share left as entered in ward_attributes.csv")
        wards["slum_huts"] = pd.NA
    # Public beds reachable per resident (E2SFCA), and from it C_h when enabled. A hospital
    # without coordinates is placed at its ward's centroid. A value entered by hand wins.
    cap = cfg["risk"]["capacity"]
    beds_xy = gpd.GeoDataFrame(
        beds, geometry=gpd.points_from_xy(beds["lon"], beds["lat"]), crs="EPSG:4326").to_crs(metric)
    centroids = wards.to_crs(metric).set_index("ward_id").geometry.centroid
    missing_xy = beds["lat"].isna().to_numpy()
    beds_xy.loc[missing_xy, "geometry"] = centroids.loc[beds.loc[missing_xy, "ward_id"]].to_numpy()
    access = access_mod.e2sfca(
        np.c_[centroids.x, centroids.y], wards.set_index("ward_id")["population"].to_numpy(dtype=float),
        np.c_[beds_xy.geometry.x, beds_xy.geometry.y], beds["beds"].to_numpy(dtype=float), cap["catchment_km"])
    wards["public_beds_access"] = wards["ward_id"].map(pd.Series(access * 1000, index=centroids.index))  # per 1,000
    if cap["spread"] > 0:   # disabled until private beds are in the data (see config.yaml)
        derived = access_mod.capacity_factor(wards.set_index("ward_id")["public_beds_access"],
                                             cfg["risk"]["capacity_factor"], cap["spread"])
        wards["capacity_factor"] = wards["capacity_factor"].fillna(wards["ward_id"].map(derived))
    wards["elderly_share"] = wards["pop_60plus"] / wards["population"]
    wards["under5_share"] = wards["pop_under5"] / wards["population"]
    wards["population_density"] = wards["population"] / wards["area_km2"]

    wards.drop(columns="geometry").pipe(pd.DataFrame).to_parquet(OUT / "wards.parquet", index=False)
    wards[["ward_id", "ward_no", "ward_name", "area_km2", "geometry"]].to_file(
        OUT / "wards.geojson", driver="GeoJSON"
    )

    # Completeness report against the provenance table
    sources = pd.read_csv(MANUAL / "column_sources.csv")
    missing_doc = sorted(set(wards.columns) - {"geometry"} - set(sources["column"]))
    if missing_doc:
        raise SystemExit(f"Columns without provenance in column_sources.csv: {missing_doc}")
    fill = wards.drop(columns="geometry").notna().mean().rename("filled_share")
    report = sources.merge(fill, left_on="column", right_index=True, how="left")
    report["filled_share"] = report["filled_share"].fillna(0).round(3)
    report["status"] = pd.cut(
        report["filled_share"], [-0.01, 0, 0.999, 1.0], labels=["missing", "partial", "complete"]
    )
    report.to_csv(OUT / "completeness.csv", index=False)

    print(f"{len(wards)} wards -> data/processed/wards.parquet, wards.geojson")
    print(f"{len(pts)} points -> data/processed/cooling_points.geojson")
    print(report[["column", "status", "filled_share", "is_estimate"]].to_string(index=False))


if __name__ == "__main__":
    main()
