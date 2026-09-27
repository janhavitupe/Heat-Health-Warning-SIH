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
  Alert workflow (Phase 7; write actions need X-API-Token when HEAT_API_TOKEN is set):
  POST /alerts/generate        draft alerts from the current run (never sends anything)
  GET  /alerts, /alerts/{id}   drafts and decided alerts, with rendered previews and deliveries
  PATCH /alerts/{id}           edit a draft (wards, audiences, languages, channels, text)
  POST /alerts/{id}/approve | /reject | /dispatch    officer decisions; dispatch needs approval
  GET  /alerts/{id}/cap.xml    CAP 1.2 export
  GET|POST /ivr/{id}/{ward}    TwiML voice script with keypad menu
  GET  /audit                  audit log
  GET  /dashboard              command dashboard summary for a day
  What-if and feedback (Phase 8):
  POST /scenarios/run          re-run a replayed heatwave with interventions (Scenario Estimate; nothing saved)
  POST /scenarios, GET /scenarios[/{id}]   save and compare named scenarios
  POST /reports                health-worker case report (stored only as counts, no identifiers)
  GET  /reports/summary        reports per day and ward, anomaly flags
  GET  /reports/recalibration  proposed H_m per ward (never applied automatically)
  POST /reports/synthetic      seed labelled synthetic reports for a replay demo

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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

from api import alerts, db, decisions, dispatch, jobs, loop, report_card, whatsapp_bot
from heatrisk import load_config
from heatrisk.config import ROOT

log = logging.getLogger("heat.api")
FRONTEND = ROOT / "frontend" / "dist"
LABEL_NOTE = "Model estimate - not a clinical prediction."


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler

    tz = load_config()["city"]["timezone"]
    sched = BackgroundScheduler(timezone=tz)

    def draft_alerts(conn):
        try:
            generate_drafts(conn, None)
        except Exception:
            log.exception("alert drafting failed")

    def forecast_job():
        with db.connect() as conn:
            if jobs.with_retries(jobs.run_forecast, conn=conn):
                draft_alerts(conn)

    def ensemble_job():
        with db.connect() as conn:
            if jobs.with_retries(jobs.run_ensemble, conn=conn, wait_s=300):
                draft_alerts(conn)

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])


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


# ---------- alert workflow (Phase 7)

def require_token(x_api_token: str | None = Header(None)):
    """Write actions need the token when HEAT_API_TOKEN is set (always set it outside a local demo)."""
    token = os.environ.get("HEAT_API_TOKEN")
    if token and x_api_token != token:
        raise HTTPException(401, "missing or wrong X-API-Token")


class OfficerAction(BaseModel):
    officer: str
    note: str = ""
    reason: str = ""


class AlertEdit(BaseModel):
    officer: str
    wards: list[str] | None = None
    audiences: list[str] | None = None
    languages: list[str] | None = None
    channels: list[str] | None = None
    templates: dict | None = None


def _probs_by_day(conn, prob_run) -> dict:
    out: dict = {}
    for (w, d), v in _probs(conn, prob_run).items():
        out.setdefault(d, {})[(w, d)] = v
    return out


def generate_drafts(conn, replay: str | None) -> list[int]:
    run, prob_run = _runs(conn, replay)
    start = None if replay else jobs.today(load_config()).strftime("%Y-%m-%d")
    return alerts.generate(conn, run, prob_run, replay, _probs_by_day(conn, prob_run), from_day=start)


def _alert_or_404(conn, alert_id: int) -> dict:
    try:
        return alerts.load(conn, alert_id)
    except KeyError:
        raise HTTPException(404, f"unknown alert {alert_id}") from None


def _workflow(fn, *args):
    try:
        return fn(*args)
    except alerts.WorkflowError as e:
        raise HTTPException(409, str(e)) from None


def _detail(conn, a: dict) -> dict:
    first = a["wards"][0]
    previews = {lang: {aud: alerts.render(a, first, lang, aud) for aud in a["audiences"]} for lang in a["languages"]}
    deliveries = [dict(r) for r in conn.execute(
        "SELECT ward_id, channel, recipient, audience, lang, status, provider, detail, at FROM deliveries WHERE alert_id=?",
        (a["alert_id"],))]
    return {**alerts.summary(a), "templates": a["templates"], "preview_ward": a["ward_values"][first]["_meta"]["ward_name"],
            "previews": previews, "problems": alerts.problems(a), "deliveries": deliveries,
            "dispatch_mode": dispatch.mode()}


@app.post("/alerts/generate", dependencies=[Depends(require_token)])
def alerts_generate(replay: str | None = None):
    with db.connect() as conn:
        ids = generate_drafts(conn, replay)
    return {"created": ids}


@app.get("/alerts")
def alerts_list(replay: str | None = None, status: str | None = None):
    sql, args = "SELECT alert_id FROM alerts WHERE mode=? AND IFNULL(replay,'')=?", ["replay" if replay else "live", replay or ""]
    if status:
        sql, args = sql + " AND status=?", args + [status]
    with db.connect() as conn:
        ids = [r[0] for r in conn.execute(sql + " ORDER BY date, alert_id", args)]
        return {"dispatch_mode": dispatch.mode(), "alerts": [alerts.summary(alerts.load(conn, i)) for i in ids]}


@app.get("/alerts/{alert_id}")
def alert_detail(alert_id: int):
    with db.connect() as conn:
        return _detail(conn, _alert_or_404(conn, alert_id))


@app.get("/alerts/{alert_id}/preview")
def alert_preview(alert_id: int, ward: str, lang: str = "en", audience: str = "public"):
    with db.connect() as conn:
        a = _alert_or_404(conn, alert_id)
        if ward not in a["ward_values"] or lang not in a["templates"] or audience not in a["templates"][lang]:
            raise HTTPException(404, "unknown ward, language or audience for this alert")
        return alerts.render(a, ward, lang, audience)


@app.patch("/alerts/{alert_id}", dependencies=[Depends(require_token)])
def alert_edit(alert_id: int, body: AlertEdit):
    with db.connect() as conn:
        _alert_or_404(conn, alert_id)
        a = _workflow(alerts.edit, conn, alert_id, body.officer, body.model_dump(exclude={"officer"}))
        return _detail(conn, a)


@app.post("/alerts/{alert_id}/approve", dependencies=[Depends(require_token)])
def alert_approve(alert_id: int, body: OfficerAction):
    with db.connect() as conn:
        _alert_or_404(conn, alert_id)
        return _detail(conn, _workflow(alerts.approve, conn, alert_id, body.officer, body.note))


@app.post("/alerts/{alert_id}/reject", dependencies=[Depends(require_token)])
def alert_reject(alert_id: int, body: OfficerAction):
    with db.connect() as conn:
        _alert_or_404(conn, alert_id)
        return _detail(conn, _workflow(alerts.reject, conn, alert_id, body.officer, body.reason))


@app.post("/alerts/{alert_id}/dispatch", dependencies=[Depends(require_token)])
def alert_dispatch(alert_id: int, body: OfficerAction):
    with db.connect() as conn:
        _alert_or_404(conn, alert_id)
        result = _workflow(dispatch.dispatch, conn, alert_id, body.officer)
        return {**result, "alert": _detail(conn, alerts.load(conn, alert_id))}


@app.post("/alerts/{alert_id}/refresh-status", dependencies=[Depends(require_token)])
def alert_refresh(alert_id: int):
    with db.connect() as conn:
        _alert_or_404(conn, alert_id)
        return {"changed": dispatch.refresh_status(conn, alert_id)}


@app.get("/alerts/{alert_id}/cap.xml")
def alert_cap(alert_id: int):
    with db.connect() as conn:
        xml = alerts.cap_xml(conn, _alert_or_404(conn, alert_id))
    return Response(xml, media_type="application/xml",
                    headers={"Content-Disposition": f'inline; filename="heat-alert-{alert_id}.xml"'})


def _twiml_response(alert_id: int, ward_id: str, lang: str, audience: str, digit: str | None):
    with db.connect() as conn:
        a = _alert_or_404(conn, alert_id)
    if ward_id not in a["ward_values"] or lang not in a["templates"]:
        raise HTTPException(404, "unknown ward or language for this alert")
    xml = alerts.twiml(a, ward_id, lang, audience, digit=digit, base_url=os.environ.get("HEAT_PUBLIC_URL"))
    return Response(xml, media_type="application/xml")


@app.api_route("/ivr/{alert_id}/{ward_id}", methods=["GET", "POST"])
def ivr(alert_id: int, ward_id: str, lang: str = "en", audience: str = "public"):
    return _twiml_response(alert_id, ward_id, lang, audience, None)


@app.post("/ivr/{alert_id}/{ward_id}/menu")
async def ivr_menu(alert_id: int, ward_id: str, request: Request, lang: str = "en", audience: str = "public"):
    from urllib.parse import parse_qs

    digit = (parse_qs((await request.body()).decode()).get("Digits") or [None])[0]
    return _twiml_response(alert_id, ward_id, lang, audience, digit)


@app.get("/whatsapp/preview")
def whatsapp_preview(text: str = Query(..., max_length=200), replay: str | None = None):
    """What the WhatsApp reply bot would answer (simulated, read-only; nothing is sent)."""
    with db.connect() as conn:
        reply, detail = whatsapp_bot.reply(conn, text, replay)
    return {"reply": reply, "detail": detail, "simulated": True}


@app.post("/whatsapp/inbound")
async def whatsapp_inbound(request: Request):
    """Twilio WhatsApp webhook: reply to a ward name with that ward's officer-approved alert."""
    from urllib.parse import parse_qsl

    params = dict(parse_qsl((await request.body()).decode()))
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if token:
        base = os.environ.get("HEAT_PUBLIC_URL")
        if not base:
            raise HTTPException(403, "set HEAT_PUBLIC_URL (the public https address Twilio calls) to verify requests")
        url = base.rstrip("/") + request.url.path + (f"?{request.url.query}" if request.url.query else "")
        if not whatsapp_bot.valid_signature(token, url, params, request.headers.get("X-Twilio-Signature")):
            raise HTTPException(403, "invalid Twilio signature")
    xml = whatsapp_bot.handle(params, os.environ.get("HEAT_WHATSAPP_REPLAY") or None)
    return Response(xml, media_type="application/xml")


@app.get("/audit")
def audit(limit: int = Query(100, ge=1, le=1000), alert_id: int | None = None):
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit * 5 if alert_id else limit,))]
    for r in rows:
        try:
            r["detail"] = json.loads(r["detail"]) if r["detail"] else None
        except ValueError:
            pass
    if alert_id is not None:
        rows = [r for r in rows if isinstance(r["detail"], dict) and r["detail"].get("alert_id") == alert_id][:limit]
    return {"entries": rows}


@app.get("/dashboard")
def dashboard(day: str | None = None, replay: str | None = None,
              view: str = Query("municipal", pattern="^(municipal|healthcare)$")):
    """One call for the command screen: status, event, counts, priorities with drivers and actions,
    work hours in the top wards, cooling deserts and alerts awaiting review."""
    with db.connect() as conn:
        run, prob_run, day = _run_and_day(conn, replay, day)
        probs = _probs(conn, prob_run, day)
        pr = decisions.priorities(conn, run["run_id"], day, probs, view)
        top = pr["wards"][:5]
        for w in top:
            acts = decisions.ward_actions(conn, run["run_id"], w["ward_id"], day)["actions"]
            w["n_actions"] = len(acts)
            w["actions"] = [a["action"] for a in acts[:3]]
            sched = decisions.schedule(conn, run["run_id"], w["ward_id"], day)
            w["heavy_work"] = sched["workloads"]["heavy"]["summary"] if sched.get("available") else None
        evs = [json.loads(r[0]) for r in conn.execute("SELECT event FROM events WHERE run_id=?", (run["run_id"],))]
        active = next((e for e in evs if e["start"] <= day <= e["end"]), None) or next(
            (e for e in evs if e["start"] > day), None)
        cool = decisions.cooling_summary(conn)
        mode = "replay" if replay else "live"
        pending = conn.execute("SELECT COUNT(*) FROM alerts WHERE mode=? AND IFNULL(replay,'')=? AND status='draft'",
                               (mode, replay or "")).fetchone()[0]
        counts = {lvl: 0 for lvl in ("green", "yellow", "orange", "red")}
        for r in conn.execute("SELECT data FROM daily_scores WHERE run_id=? AND date=?", (run["run_id"], day)):
            counts[json.loads(r[0])["alert_mri"]] += 1
        rep_sum = loop.summary(conn, run["run_id"], replay, None)
        report_flags = [f for f in rep_sum["flags"] if f["date"] == day]
    return {"day": day, "view": view, "meta": _meta(run, prob_run, replay), "counts": counts, "event": active,
            "event_index": evs.index(active) if active else None,
            "report_flags": report_flags, "reports_synthetic": rep_sum["includes_synthetic"],
            "worst_level": pr["worst_level"], "city_actions": pr["city_actions"], "top_wards": top,
            "cooling": {"city_share_within_walk": cool["city_share_within_walk"],
                        "deserts": [w["ward_name"] for w in cool["wards"] if w.get("cooling_desert")],
                        "recommended_sites": len(cool["recommended_sites"]["features"])},
            "alerts_pending_review": pending, "dispatch_mode": dispatch.mode()}


@app.get("/report-card")
def report_card_view(replay: str | None = None, event: int = Query(0, ge=0),
                     format: str = Query("html", pattern="^(html|json)$")):
    """Post-event report card (Phase 9): predicted vs observed, early warning, reports, officer actions."""
    with db.connect() as conn:
        run, prob_run = _runs(conn, replay)
        try:
            card = report_card.build(conn, run, prob_run, replay, event)
        except LookupError as e:
            raise HTTPException(404, str(e)) from None
    return card if format == "json" else HTMLResponse(report_card.render_html(card))


# ---------- what-if scenarios and health-worker feedback (Phase 8)

class ScenarioRun(BaseModel):
    changes: list[dict]
    replay: str | None = None


class ScenarioSave(ScenarioRun):
    name: str
    author: str = ""


class Report(BaseModel):
    ward_id: str
    date: str
    age_band: str
    severity: str
    outcome: str
    role: str


def _loop(fn, *args):
    try:
        return fn(*args)
    except loop.InputError as e:
        raise HTTPException(422, str(e)) from None


@app.post("/scenarios/run")
def scenario_run(body: ScenarioRun):
    return _loop(loop.run_scenario, body.changes, body.replay)


@app.post("/scenarios", dependencies=[Depends(require_token)])
def scenario_save(body: ScenarioSave):
    with db.connect() as conn:
        sid = _loop(loop.save_scenario, conn, body.name, body.author, body.changes, body.replay)
    return {"scenario_id": sid}


@app.get("/scenarios")
def scenario_list():
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT scenario_id, name, author, created_at, replay, spec, result FROM scenarios "
                                              "ORDER BY scenario_id DESC")]
    for r in rows:
        r["spec"] = json.loads(r["spec"])
        r["city"] = json.loads(r.pop("result"))["city"]
    return {"scenarios": rows}


@app.get("/scenarios/{scenario_id}")
def scenario_get(scenario_id: int):
    with db.connect() as conn:
        r = conn.execute("SELECT * FROM scenarios WHERE scenario_id=?", (scenario_id,)).fetchone()
    if r is None:
        raise HTTPException(404, f"unknown scenario {scenario_id}")
    out = dict(r)
    out["spec"], out["result"] = json.loads(out["spec"]), json.loads(out["result"])
    return out


@app.post("/reports", dependencies=[Depends(require_token)])
def report_add(body: Report, replay: str | None = None):
    with db.connect() as conn:
        _loop(loop.add_report, conn, body.model_dump(), replay)
        db.log(conn, "report_received", {"ward_id": body.ward_id, "date": body.date, "replay": replay}, actor=body.role)
    return {"stored": "count incremented; no personal details kept"}


@app.get("/reports/summary")
def report_summary(replay: str | None = None, day: str | None = None):
    with db.connect() as conn:
        run, _ = _runs(conn, replay)
        return loop.summary(conn, run["run_id"], replay, day)


@app.get("/reports/recalibration")
def report_recalibration(replay: str | None = None):
    with db.connect() as conn:
        run, _ = _runs(conn, replay)
        return loop.recalibration(conn, run["run_id"], replay)


@app.post("/reports/synthetic", dependencies=[Depends(require_token)])
def report_synthetic(replay: str = "may2024"):
    with db.connect() as conn:
        run, _ = _runs(conn, replay)
        n = loop.seed_synthetic(conn, run["run_id"], replay)
    return {"synthetic_reports": n, "label": "SYNTHETIC demo data"}

# ---------- frontend (built React app), if present

if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(FRONTEND / "favicon.svg", media_type="image/svg+xml")
