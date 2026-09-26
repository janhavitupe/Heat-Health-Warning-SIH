"""FastAPI service for the heat-health platform (Phase 5, proposal §8).

Endpoints (all accept ?replay=<name> to serve a past event, e.g. ?replay=may2024):
  GET /status              last refresh times, errors, available replays
  GET /days                days available, with city-wide alert counts (for the day slider)
  GET /wards?day=          GeoJSON of all wards with scores, alert levels and probabilities for a day
  GET /ward/{ward_id}      one ward: attributes, PVI breakdown, every day's scores and explanation,
                           probabilities, hourly curve, peak
  GET /forecast?day=       all wards for a day, without geometry
  GET /events              heatwave events
  GET /config              every weight and threshold, plus the data source label of each ward column
  Decision layer (Phase 6):
  GET /ward/{id}/actions       recommended actions for the ward-day (Heat Action Plan departments)
  GET /ward/{id}/work-windows  safe work schedule by workload (ACGIH WBGT limits)
  GET /ward/{id}/advisories    public advisories: 3 audiences × en/hi/gu, SMS and long text
  GET /priorities              wards ranked for action (municipal: MRI, healthcare: HRI) + city actions
  GET /cooling                 cooling gap per ward, deserts, existing cooling places, recommended new sites
  GET /allocation              where to send N mobile cooling units and M ambulances

Run:  uvicorn api.main:app --reload            (API only)
      HEAT_SCHEDULER=1 uvicorn api.main:app    (with hourly forecast / daily ensemble refresh)
Docs: /docs (OpenAPI)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import db, decisions, jobs
from heatrisk import load_config
from heatrisk.config import ROOT

log = logging.getLogger("heat.api")
FRONTEND = ROOT / "frontend" / "dist"
LABEL_NOTE = "Model estimate - not a clinical prediction."


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler

    tz = load_config()["city"]["timezone"]
    sched = BackgroundScheduler(timezone=tz)

    def forecast_job():
        with db.connect() as conn:
            jobs.with_retries(jobs.run_forecast, conn=conn)

    def ensemble_job():
        with db.connect() as conn:
            jobs.with_retries(jobs.run_ensemble, conn=conn, wait_s=300)

    sched.add_job(forecast_job, "cron", minute=5, id="forecast", max_instances=1, coalesce=True)
    sched.add_job(ensemble_job, "cron", hour=5, minute=45, id="ensemble", max_instances=1, coalesce=True)
    sched.start()
    with db.connect() as conn:          # fill an empty database straight away
        need_fc, need_ens = db.latest_run(conn, "forecast") is None, db.latest_run(conn, "ensemble") is None
    if need_fc or need_ens:
        threading.Thread(target=lambda: (need_fc and forecast_job(), need_ens and ensemble_job()), daemon=True).start()
    return sched


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db.connect() as conn:
        db.init(conn)
        if conn.execute("SELECT COUNT(*) FROM wards").fetchone()[0] == 0:
            jobs.load_wards_table(conn)
    sched = start_scheduler() if os.environ.get("HEAT_SCHEDULER") == "1" else None
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Heat-Health Early Warning API", version="0.5.0", lifespan=lifespan,
              description="Ward-level heat stress, vulnerability and risk for Ahmedabad. " + LABEL_NOTE)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


# ---------- helpers

def _runs(conn, replay: str | None) -> tuple[dict, dict | None]:
    """(run that holds scores, run that holds probabilities) for live data or a replay."""
    if replay:
        if replay not in jobs.REPLAYS:
            raise HTTPException(404, f"unknown replay '{replay}'; available: {sorted(jobs.REPLAYS)}")
        r = db.latest_run(conn, "replay", replay)
        if r is None:
            raise HTTPException(503, f"replay '{replay}' not built yet: run `python -m api.cli replay {replay}`")
        return dict(r), dict(r)
    fc = db.latest_run(conn, "forecast")
    if fc is None:
        raise HTTPException(503, "no forecast yet: run `python -m api.cli forecast` or start with HEAT_SCHEDULER=1")
    ens = db.latest_run(conn, "ensemble")
    return dict(fc), (dict(ens) if ens else None)


def _daily(conn, run_id: int, day: str | None = None, ward_id: str | None = None) -> list[dict]:
    sql, args = "SELECT ward_id, date, data FROM daily_scores WHERE run_id=?", [run_id]
    if day:
        sql, args = sql + " AND date=?", args + [day]
    if ward_id:
        sql, args = sql + " AND ward_id=?", args + [ward_id]
    return [{"ward_id": r["ward_id"], "date": r["date"], **json.loads(r["data"])}
            for r in conn.execute(sql + " ORDER BY ward_id, date", args)]


def _probs(conn, run: dict | None, day: str | None = None, ward_id: str | None = None) -> dict:
    if run is None:
        return {}
    sql, args = "SELECT * FROM ensemble_probs WHERE run_id=?", [run["run_id"]]
    if day:
        sql, args = sql + " AND date=?", args + [day]
    if ward_id:
        sql, args = sql + " AND ward_id=?", args + [ward_id]
    return {(r["ward_id"], r["date"]): {c: r[c] for c in db.PROB_COLUMNS} for r in conn.execute(sql, args)}


def _days(conn, run_id: int) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT date FROM daily_scores WHERE run_id=? ORDER BY date", (run_id,))]


def _default_day(conn, run: dict, replay: str | None) -> str:
    days = _days(conn, run["run_id"])
    if replay:
        ev = conn.execute("SELECT event FROM events WHERE run_id=? LIMIT 1", (run["run_id"],)).fetchone()
        return json.loads(ev[0])["peak"] if ev else days[0]
    today = jobs.today(load_config()).strftime("%Y-%m-%d")
    return today if today in days else next((d for d in days if d >= today), days[-1])


def _slim(row: dict) -> dict:
    """Daily row without the long explanation JSON (for map and list views)."""
    return {k: v for k, v in row.items() if not k.startswith("explanation_")}


def _meta(run: dict, prob_run: dict | None, replay: str | None) -> dict:
    return {"mode": "replay" if replay else "live", "replay": replay,
            "title": jobs.REPLAYS[replay]["title"] if replay else "Live forecast",
            "scores_updated": run["finished_at"], "issued_date": run["issued_date"],
            "probabilities_updated": prob_run["finished_at"] if prob_run else None,
            "probability_members": prob_run["n_members"] if prob_run else None,
            "probability_source": prob_run["source"] if prob_run else None, "label": LABEL_NOTE}


# ---------- endpoints

@app.get("/status")
def status():
    with db.connect() as conn:
        runs = {k: (dict(r) if (r := db.latest_run(conn, k)) else None) for k in ("forecast", "ensemble")}
        failures = [dict(r) for r in conn.execute(
            "SELECT kind, name, started_at, error FROM runs WHERE status='failed' ORDER BY run_id DESC LIMIT 5")]
        built = {r["name"] for r in conn.execute("SELECT name FROM runs WHERE kind='replay' AND status='ok'")}
    return {"latest": runs, "recent_failures": failures,
            "replays": [{"name": k, "title": v["title"], "built": k in built} for k, v in jobs.REPLAYS.items()]}


@app.get("/days")
def days(replay: str | None = None):
    with db.connect() as conn:
        run, prob_run = _runs(conn, replay)
        rows = pd.DataFrame(_daily(conn, run["run_id"]))
        probs = _probs(conn, prob_run)
        default = _default_day(conn, run, replay)
    out = []
    for day, d in rows.groupby("date"):
        counts = d["alert_mri"].value_counts().to_dict()
        p_red = [probs[(w, day)]["p_red"] for w in d["ward_id"] if (w, day) in probs]
        out.append({"date": day, "counts": {lvl: int(counts.get(lvl, 0)) for lvl in ("green", "yellow", "orange", "red")},
                    "max_mri": round(float(d["mri"].max()), 1), "max_p_red": max(p_red) if p_red else None})
    return {"meta": _meta(run, prob_run, replay), "default_day": default, "days": out}


@app.get("/wards")
def wards(day: str | None = None, replay: str | None = None):
    with db.connect() as conn:
        run, prob_run = _runs(conn, replay)
        day = day or _default_day(conn, run, replay)
        scores = {r["ward_id"]: _slim(r) for r in _daily(conn, run["run_id"], day)}
        if not scores:
            raise HTTPException(404, f"no data for {day}")
        probs = _probs(conn, prob_run, day)
        feats = []
        for w in conn.execute("SELECT * FROM wards ORDER BY ward_no"):
            attrs = json.loads(w["attributes"])
            props = {"ward_id": w["ward_id"], "ward_no": w["ward_no"], "ward_name": w["ward_name"], "zone": w["zone"],
                     "roof_sheet_share": attrs.get("roof_sheet_share"),
                     "informal_housing_share": attrs.get("informal_housing_share"),
                     "cooling_gap": attrs.get("cooling_gap"), "cooling_desert": attrs.get("cooling_desert"),
                     **scores.get(w["ward_id"], {}), **probs.get((w["ward_id"], day), {})}
            feats.append({"type": "Feature", "geometry": json.loads(w["geometry"]), "properties": props})
    return {"type": "FeatureCollection", "day": day, "meta": _meta(run, prob_run, replay), "features": feats}


@app.get("/ward/{ward_id}")
def ward(ward_id: str, replay: str | None = None):
    with db.connect() as conn:
        w = conn.execute("SELECT * FROM wards WHERE ward_id=?", (ward_id,)).fetchone()
        if w is None:
            raise HTTPException(404, f"unknown ward '{ward_id}'")
        run, prob_run = _runs(conn, replay)
        probs = _probs(conn, prob_run, ward_id=ward_id)
        daily = []
        for r in _daily(conn, run["run_id"], ward_id=ward_id):
            for k in ("explanation_mri", "explanation_hri"):
                r[k] = json.loads(r[k]) if r.get(k) else None
            r.update(probs.get((ward_id, r["date"]), {}))
            daily.append(r)
        hourly = [dict(h) for h in conn.execute(
            "SELECT time, t2m, mrt, utci, wbgt, heat_index FROM hourly_scores WHERE run_id=? AND ward_id=? ORDER BY time",
            (run["run_id"], ward_id))]
    attrs = json.loads(w["attributes"])
    return {"meta": _meta(run, prob_run, replay), "ward_id": ward_id, "ward_no": w["ward_no"],
            "ward_name": w["ward_name"], "zone": w["zone"], "attributes": attrs, "daily": daily, "hourly": hourly}


@app.get("/forecast")
def forecast_day(day: str | None = None, replay: str | None = None):
    with db.connect() as conn:
        run, prob_run = _runs(conn, replay)
        day = day or _default_day(conn, run, replay)
        probs = _probs(conn, prob_run, day)
        rows = [{**_slim(r), **probs.get((r["ward_id"], day), {})} for r in _daily(conn, run["run_id"], day)]
    return {"day": day, "meta": _meta(run, prob_run, replay), "wards": rows}


@app.get("/events")
def events(replay: str | None = None):
    with db.connect() as conn:
        run, prob_run = _runs(conn, replay)
        evs = [json.loads(r[0]) for r in conn.execute("SELECT event FROM events WHERE run_id=?", (run["run_id"],))]
        trig = [dict(r) for r in conn.execute(
            "SELECT ward_id, date, lead_days, rule, probability, action FROM triggers WHERE run_id=?",
            (prob_run["run_id"],))] if prob_run and not replay else []
    return {"meta": _meta(run, prob_run, replay), "events": evs, "triggers": trig}


@app.get("/config")
def config():
    sources = pd.read_csv(ROOT / "data" / "manual" / "column_sources.csv")
    return {"config": load_config(),
            "ward_columns": sources[["column", "description", "source", "year", "is_estimate", "label"]]
            .to_dict("records")}



# ---------- decision layer (Phase 6)

def _run_and_day(conn, replay, day):
    run, prob_run = _runs(conn, replay)
    return run, prob_run, day or _default_day(conn, run, replay)


def _ward_exists(conn, ward_id):
    if conn.execute("SELECT 1 FROM wards WHERE ward_id=?", (ward_id,)).fetchone() is None:
        raise HTTPException(404, f"unknown ward '{ward_id}'")


@app.get("/ward/{ward_id}/actions")
def ward_actions(ward_id: str, day: str | None = None, replay: str | None = None):
    with db.connect() as conn:
        _ward_exists(conn, ward_id)
        run, _, day = _run_and_day(conn, replay, day)
        return {"ward_id": ward_id, "day": day, **decisions.ward_actions(conn, run["run_id"], ward_id, day)}


@app.get("/ward/{ward_id}/work-windows")
def ward_work_windows(ward_id: str, day: str | None = None, replay: str | None = None,
                      acclimatized: bool | None = None):
    with db.connect() as conn:
        _ward_exists(conn, ward_id)
        run, _, day = _run_and_day(conn, replay, day)
        return {"ward_id": ward_id, "day": day, **decisions.schedule(conn, run["run_id"], ward_id, day, acclimatized)}


@app.get("/ward/{ward_id}/advisories")
def ward_advisories(ward_id: str, day: str | None = None, replay: str | None = None,
                    lang: str | None = Query(None, pattern="^(en|hi|gu)$")):
    with db.connect() as conn:
        _ward_exists(conn, ward_id)
        run, _, day = _run_and_day(conn, replay, day)
        return {"ward_id": ward_id, "day": day, **decisions.ward_advisories(conn, run["run_id"], ward_id, day, lang)}


@app.get("/priorities")
def priorities(day: str | None = None, replay: str | None = None,
               view: str = Query("municipal", pattern="^(municipal|healthcare)$")):
    with db.connect() as conn:
        run, prob_run, day = _run_and_day(conn, replay, day)
        return {"day": day, **decisions.priorities(conn, run["run_id"], day, _probs(conn, prob_run, day), view)}


@app.get("/cooling")
def cooling():
    with db.connect() as conn:
        return decisions.cooling_summary(conn)


@app.get("/allocation")
def allocation_plan(day: str | None = None, replay: str | None = None,
                    cooling_units: int = Query(5, ge=0, le=100), ambulances: int = Query(10, ge=0, le=500)):
    with db.connect() as conn:
        run, _, day = _run_and_day(conn, replay, day)
        return decisions.allocation_plan(conn, run["run_id"], day, cooling_units, ambulances)

# ---------- frontend (built React app), if present

if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")
