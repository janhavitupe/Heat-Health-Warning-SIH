"""Refresh jobs: load wards, run the forecast and ensemble, and build replays.

Each job records a run (see db.py). On failure the run is marked "failed" with
the error and the API keeps serving the last good run.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable

import geopandas as gpd
import pandas as pd

from api import db
from heatrisk import ensemble, forecast, load_config, vulnerability
from heatrisk.config import ROOT
from heatrisk.pipeline import load_wards
from heatrisk.weather import fetch_archive, fetch_ensemble, fetch_forecast, fetch_previous_runs

log = logging.getLogger("heat.jobs")

DAILY_FIELDS = ["tmax", "tmin", "utci", "wbgt", "heat_index", "base", "pts_utci", "pts_wbgt", "pts_heat_index",
                "pts_night", "pts_persist", "pts_indoor", "indoor_data_missing", "hot_run_days", "htsi",
                "htsi_category", "pvi", "mri", "alert_mri", "hri", "alert_hri", "top_factors", "summary_mri",
                "explanation_mri", "explanation_hri"]
FORECAST_RUNS_KEPT = 48          # two days of hourly refreshes

# Replays: past events served through the same endpoints. Probabilities come from a time-lagged
# multi-model ensemble of archived forecasts issued 3-5 days ahead (see docs/forecast_phase4.md).
REPLAYS = {
    "may2024": {"title": "May 2024 heatwave", "start": "2024-05-01", "end": "2024-06-15",
                "prob_models": ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"], "prob_leads": [3, 4, 5],
                "note": "Weather: ERA5 reanalysis. Probabilities: forecasts issued 3-5 days ahead by ECMWF, GFS "
                        "and ICON (9 members), i.e. what the system would have shown 3 days before each day."},
}


def with_retries(job: Callable, attempts: int = 3, wait_s: float = 30, **kwargs):
    for i in range(attempts):
        try:
            return job(**kwargs)
        except Exception:
            log.exception("%s failed (attempt %d/%d)", job.__name__, i + 1, attempts)
            if i + 1 < attempts:
                time.sleep(wait_s)
    return None


def load_wards_table(conn) -> None:
    """(Re)load ward geometry and static attributes, including the PVI breakdown."""
    cfg, wards = load_config(), load_wards()
    geo = gpd.read_file(ROOT / "data" / "processed" / "wards.geojson").set_index("ward_id")
    pvi, status = vulnerability.compute_pvi(wards, cfg)
    merged = wards.merge(pvi, on="ward_id")
    conn.execute("DELETE FROM wards")
    for r in merged.to_dict("records"):
        attrs = {k: (None if pd.isna(v) else v) for k, v in r.items()
                 if k not in ("ward_id", "ward_no", "ward_name", "zone") and not isinstance(v, (list, dict))}
        attrs["pvi_status"] = status
        conn.execute("INSERT INTO wards VALUES (?, ?, ?, ?, ?, ?)",
                     (r["ward_id"], int(r["ward_no"]), r["ward_name"], r["zone"],
                      json.dumps(geo.loc[r["ward_id"], "geometry"].__geo_interface__), json.dumps(attrs, default=float)))
    db.log(conn, "wards_loaded", {"n": len(merged)})


def _clean(v):
    """A pandas/numpy scalar as a JSON-safe Python value (NaN → None, dates → YYYY-MM-DD)."""
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if v is None or (not isinstance(v, (str, bool)) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def store_scores(conn, run_id: int, daily: pd.DataFrame, hourly: pd.DataFrame, events: list[dict],
                 peaks: pd.DataFrame | None = None) -> None:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    if peaks is not None:
        peaks = peaks.assign(peak_day=pd.to_datetime(peaks["peak_day"]).dt.strftime("%Y-%m-%d"))
        daily = daily.merge(peaks, on="ward_id", how="left")
    fields = DAILY_FIELDS + ([c for c in peaks.columns if c != "ward_id"] if peaks is not None else [])
    conn.executemany("INSERT INTO daily_scores VALUES (?, ?, ?, ?)", [
        (run_id, r["ward_id"], r["date"], json.dumps({k: _clean(r[k]) for k in fields if k in r}))
        for r in daily.to_dict("records")])
    h = hourly.copy()
    h["time"] = pd.to_datetime(h["time"]).dt.strftime("%Y-%m-%dT%H:%M")
    conn.executemany("INSERT INTO hourly_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        (run_id, r.ward_id, r.time, r.t2m, r.mrt, r.utci, r.wbgt, r.heat_index) for r in h.itertuples()])
    conn.executemany("INSERT INTO events VALUES (?, ?)", [(run_id, json.dumps(e)) for e in events])


def store_probs(conn, run_id: int, probs: pd.DataFrame) -> None:
    p = probs.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.strftime("%Y-%m-%d")
    conn.executemany(f"INSERT INTO ensemble_probs VALUES (?, ?, ?, {', '.join('?' * len(db.PROB_COLUMNS))})", [
        (run_id, r["ward_id"], r["date"], *[_clean(r[c]) for c in db.PROB_COLUMNS]) for r in p.to_dict("records")])


def today(cfg: dict) -> pd.Timestamp:
    return pd.Timestamp.now(tz=cfg["city"]["timezone"]).tz_localize(None).normalize()


def run_forecast(conn) -> int:
    """Deterministic forecast for every ward (hourly job)."""
    cfg, wards = load_config(), load_wards()
    c, fcfg = cfg["city"]["centre"], cfg["forecast"]
    run_id = db.start_run(conn, "forecast", source="open-meteo forecast")
    try:
        wx = fetch_forecast(c["lat"], c["lon"], days=fcfg["days"], past_days=fcfg["past_days"])
        daily, hourly = forecast.run_wards(wx, wards, cfg)
        issue = today(cfg)
        store_scores(conn, run_id, daily, hourly, forecast.detect_events(daily, cfg, len(wards)),
                     forecast.ward_peaks(daily, hourly, issue))
        db.finish_run(conn, run_id, "ok", issued_date=issue.strftime("%Y-%m-%d"))
        db.prune(conn, "forecast", FORECAST_RUNS_KEPT)
        db.log(conn, "forecast_run", {"run_id": run_id})
        return run_id
    except Exception as e:
        db.finish_run(conn, run_id, "failed", error=repr(e)[:500])
        raise


def run_ensemble(conn) -> int:
    """Ensemble probabilities for every ward (daily job). All runs are kept for later reliability checks."""
    cfg, wards = load_config(), load_wards()
    c, fcfg = cfg["city"]["centre"], cfg["forecast"]
    run_id = db.start_run(conn, "ensemble", source="open-meteo ensemble: " + ",".join(cfg["ensemble"]["models"]))
    try:
        members = fetch_ensemble(c["lat"], c["lon"], cfg["ensemble"]["models"], days=fcfg["days"],
                                 past_days=fcfg["past_days"] + 1)
        probs = ensemble.probabilities(ensemble.score_members(members, wards, cfg), cfg)
        store_probs(conn, run_id, probs)
        issue = today(cfg)
        trig = ensemble.triggers(probs, cfg, issue)
        conn.executemany("INSERT INTO triggers VALUES (?, ?, ?, ?, ?, ?, ?)", [
            (run_id, r.ward_id, pd.Timestamp(r.date).strftime("%Y-%m-%d"), r.lead_days, r.rule, r.probability, r.action)
            for r in trig.itertuples()])
        db.finish_run(conn, run_id, "ok", issued_date=issue.strftime("%Y-%m-%d"), n_members=len(members))
        db.log(conn, "ensemble_run", {"run_id": run_id, "members": len(members), "triggers": len(trig)})
        return run_id
    except Exception as e:
        db.finish_run(conn, run_id, "failed", error=repr(e)[:500])
        raise


def build_replay(conn, name: str = "may2024") -> int:
    """Score a past event and store it (with lagged-ensemble probabilities) as a replay run."""
    spec = REPLAYS[name]
    cfg, wards = load_config(), load_wards()
    c = cfg["city"]["centre"]
    run_id = db.start_run(conn, "replay", name=name, source=spec["note"])
    try:
        wx = fetch_archive(c["lat"], c["lon"], spec["start"], spec["end"])
        daily, hourly = forecast.run_wards(wx, wards, cfg)
        store_scores(conn, run_id, daily, hourly, forecast.detect_events(daily, cfg, len(wards)))
        members = {f"{m}_m{lead:02d}": fetch_previous_runs(c["lat"], c["lon"], spec["start"], spec["end"], m, lead)
                   for m in spec["prob_models"] for lead in spec["prob_leads"]}
        store_probs(conn, run_id, ensemble.probabilities(ensemble.score_members(members, wards, cfg), cfg))
        db.delete_runs(conn, [r[0] for r in conn.execute(
            "SELECT run_id FROM runs WHERE kind='replay' AND name=? AND run_id<>?", (name, run_id))])
        db.finish_run(conn, run_id, "ok", issued_date=spec["start"], n_members=len(members))
        db.log(conn, "replay_built", {"name": name, "run_id": run_id})
        return run_id
    except Exception as e:
        db.finish_run(conn, run_id, "failed", error=repr(e)[:500])
        raise
