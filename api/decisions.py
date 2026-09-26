"""Decision-layer responses (Phase 6): actions, work windows, advisories, cooling, allocation.

Everything is computed on request from the stored run (scores, hourly WBGT, events)
and the ward table, so the answers always match what the map shows.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from heatrisk import actions, advisories, allocation, load_config, work_windows
from heatrisk.config import ROOT

PROC = ROOT / "data" / "processed"


def ward_table(conn) -> pd.DataFrame:
    rows = [{"ward_id": w["ward_id"], "ward_name": w["ward_name"], "zone": w["zone"], **json.loads(w["attributes"])}
            for w in conn.execute("SELECT * FROM wards ORDER BY ward_no")]
    return pd.DataFrame(rows).drop(columns=["pvi_status"], errors="ignore")


@lru_cache(maxsize=1)
def cooling_places() -> dict:
    p = PROC / "ward_cooling_points.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def day_row(conn, run_id: int, ward_id: str, day: str) -> dict | None:
    r = conn.execute("SELECT data FROM daily_scores WHERE run_id=? AND ward_id=? AND date=?",
                     (run_id, ward_id, day)).fetchone()
    return json.loads(r[0]) if r else None


def hourly_day(conn, run_id: int, ward_id: str, day: str) -> pd.DataFrame:
    rows = conn.execute("SELECT time, wbgt FROM hourly_scores WHERE run_id=? AND ward_id=? AND time > ? AND time <= ?",
                        (run_id, ward_id, f"{day}T00:00", f"{(pd.Timestamp(day) + pd.Timedelta(days=1)):%Y-%m-%d}T00:00")).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(load_config()["city"]["timezone"])
    return df.set_index("time")


def peak_hour(conn, run_id: int, ward_id: str, day: str) -> str | None:
    """Start of the hour with the highest UTCI that day (stamps mark the end of the hour)."""
    r = conn.execute("SELECT time FROM hourly_scores WHERE run_id=? AND ward_id=? AND time > ? AND time <= ? "
                     "ORDER BY utci DESC LIMIT 1", (run_id, ward_id, f"{day}T00:00", f"{day}T23:59")).fetchone()
    if r is None:
        return None
    return (pd.Timestamp(r[0]) - pd.Timedelta(hours=1)).strftime("%H:%M")


def events(conn, run_id: int) -> list[dict]:
    return [json.loads(r[0]) for r in conn.execute("SELECT event FROM events WHERE run_id=?", (run_id,))]


def schedule(conn, run_id: int, ward_id: str, day: str, acclimatized: bool | None = None) -> dict:
    cfg = load_config()
    h = hourly_day(conn, run_id, ward_id, day)
    if h.empty:
        return {"available": False}
    suggested = work_windows.acclimatized_on(day, events(conn, run_id), cfg)
    acc = suggested if acclimatized is None else acclimatized
    out = work_windows.day_schedule(h, cfg, acc)
    out.update({"available": True, "suggested_acclimatized": suggested,
                "note": ("First days of a heatwave: limits for unacclimatized workers suggested."
                         if not suggested else "Limits for acclimatized workers (ACGIH TLV).") +
                        " WBGT assumes work in full sun; shaded work is less restricted."})
    return out


def ward_actions(conn, run_id: int, ward_id: str, day: str) -> dict:
    row = day_row(conn, run_id, ward_id, day)
    if row is None:
        return {"actions": []}
    wards = ward_table(conn)
    ranks = actions.attribute_ranks(wards)
    ward = wards.set_index("ward_id").loc[ward_id].to_dict()
    ex = json.loads(row["explanation_mri"]) if row.get("explanation_mri") else None
    return {"alert_mri": row["alert_mri"], "alert_hri": row["alert_hri"],
            "actions": actions.ward_actions(row, ex, ward, ranks.loc[ward_id].to_dict())}


def ward_advisories(conn, run_id: int, ward_id: str, day: str, lang: str | None = None) -> dict:
    row = day_row(conn, run_id, ward_id, day)
    if row is None:
        return {"advisories": []}
    name = conn.execute("SELECT ward_name FROM wards WHERE ward_id=?", (ward_id,)).fetchone()[0]
    kwargs = {"schedule": schedule(conn, run_id, ward_id, day), "cooling": cooling_places().get(ward_id, []),
              "peak": peak_hour(conn, run_id, ward_id, day)}
    items = advisories.render_all(name, day, row["alert_mri"], **kwargs)
    if lang:
        items = [a for a in items if a["lang"] == lang]
    return {"level": row["alert_mri"], "advisories": items}


def day_frame(conn, run_id: int, day: str, probs: dict) -> pd.DataFrame:
    rows = [{"ward_id": r["ward_id"], **json.loads(r["data"]), **probs.get((r["ward_id"], day), {})}
            for r in conn.execute("SELECT ward_id, data FROM daily_scores WHERE run_id=? AND date=?", (run_id, day))]
    return pd.DataFrame(rows)


def priorities(conn, run_id: int, day: str, probs: dict, view: str) -> dict:
    df = day_frame(conn, run_id, day, probs)
    if df.empty:
        return {"wards": [], "city_actions": []}
    names = ward_table(conn).set_index("ward_id")[["ward_name", "zone"]]
    ranked = actions.priority_ranking(df, view).join(names, on="ward_id")
    worst = max(df["alert_mri"], key=actions.LEVELS.index)
    cols = ["priority", "ward_id", "ward_name", "zone", "mri", "alert_mri", "hri", "alert_hri", "p_red", "top_factors"]
    return {"view": view, "worst_level": worst, "city_actions": actions.city_actions(worst),
            "wards": ranked[[c for c in cols if c in ranked]].where(ranked.notna(), None).to_dict("records")}


def cooling_summary(conn) -> dict:
    cfg = load_config()["cooling"]
    wards = ward_table(conn)
    cols = ["ward_id", "ward_name", "zone", "population", "cooling_gap", "cooling_gap_with_community", "cooling_desert",
            "health_walk_km"]
    sites_path, pts_path = PROC / "cooling_sites.geojson", PROC / "cooling_points.geojson"
    sites = json.loads(sites_path.read_text(encoding="utf-8")) if sites_path.exists() else {"features": []}
    pts = json.loads(pts_path.read_text(encoding="utf-8")) if pts_path.exists() else {"features": []}
    existing = [f for f in pts["features"] if f["properties"]["layer"] in cfg["existing_layers"]]
    w = wards[[c for c in cols if c in wards]]
    covered = (w["population"] * (1 - w["cooling_gap"])).sum() / w["population"].sum() if "cooling_gap" in w else None
    return {"walk_minutes": cfg["walk_minutes"], "walk_speed_kmh": cfg["walk_speed_kmh"],
            "city_share_within_walk": round(float(covered), 3) if covered is not None else None,
            "wards": w.where(w.notna(), None).to_dict("records"),
            "existing_points": {"type": "FeatureCollection", "features": existing},
            "recommended_sites": sites}


def allocation_plan(conn, run_id: int, day: str, n_cooling: int, n_ambulances: int) -> dict:
    cfg = load_config()["cooling"]
    df = day_frame(conn, run_id, day, {})
    wards = ward_table(conn)[["ward_id", "ward_name", "population", "area_km2", "cooling_gap"]]
    d = df[["ward_id", "mri", "hri"]].merge(wards, on="ward_id")
    reach_km = cfg["walk_minutes"] * cfg["walk_speed_kmh"] / 60
    cu = allocation.cooling_units(d, n_cooling, reach_km)
    am = allocation.ambulances(d, n_ambulances)
    return {"day": day, "cooling_units": cu.to_dict("records"), "ambulances": am.to_dict("records"),
            "method": "Cooling units: greedy, risk-weighted people brought within a 15-min walk. "
                      "Ambulances: D'Hondt shares of population × HRI."}
