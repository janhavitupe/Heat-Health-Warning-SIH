"""Alert Engine and human-in-the-loop workflow (Phase 7).

  draft      created automatically: one alert per day and level (Orange, Red) listing the wards at
             that level, plus preparedness alerts from probability triggers (live mode)
  edit       an officer may change wards (within the draft's wards), audiences, languages,
             channels and the message templates while the alert is a draft
  approve    requires an officer's name and every rendered SMS to fit its length limit
  reject     requires an officer's name and a reason
  dispatch   only an approved alert can be dispatched (api/dispatch.py)

Every step is written to the audit log. Nothing is ever sent without explicit approval.
A new draft never duplicates wards already covered for the same day and level: if an
unreviewed draft exists it is superseded by one covering the extra wards too; if the day's
alert was already approved, the new draft covers only the additional wards (a CAP "Update").
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from api import db, decisions
from heatrisk import advisories, load_config

LEVELS = ["green", "yellow", "orange", "red"]
IST = timezone(timedelta(hours=5, minutes=30))
OPEN = ("draft", "approved", "dispatched")


class WorkflowError(ValueError):
    """An action that the alert's current state does not allow (HTTP 409/422)."""


def wf() -> dict:
    return load_config()["alert_workflow"]


# ---------- engine

def _ward_values(conn, run_id: int, ward_ids: list[str], day: str, level: str, probs: dict) -> dict:
    cfg = wf()
    names = dict(conn.execute("SELECT ward_id, ward_name FROM wards").fetchall())
    places = decisions.cooling_places()
    out = {}
    for wid in ward_ids:
        sched = decisions.schedule(conn, run_id, wid, day)
        peak = decisions.peak_hour(conn, run_id, wid, day)
        vals = {lang: advisories.values(names[wid], day, level, lang, sched, places.get(wid, []), peak,
                                        cfg["sender_name"]) for lang in cfg["languages"]}
        p = probs.get((wid, day), {})
        vals["_meta"] = {"ward_name": names[wid],
                         "p_level": p.get("p_red" if level == "red" else "p_orange"),
                         "cooling": [c["name"] for c in places.get(wid, [])]}
        out[wid] = vals
    return out


def _templates(level: str) -> dict:
    cfg = wf()
    return {lang: {aud: advisories.templates(level, lang, aud) for aud in cfg["audiences"]} for lang in cfg["languages"]}


def _create(conn, *, mode, replay, run_id, day, level, kind, wards, reason, probs, supersedes=None) -> int:
    cfg = wf()
    # order wards by risk so the first ward is the most urgent (used for "*" recipients and previews)
    order = {r["ward_id"]: json.loads(r["data"]).get("mri", 0) for r in conn.execute(
        "SELECT ward_id, data FROM daily_scores WHERE run_id=? AND date=?", (run_id, day))}
    wards = sorted(wards, key=lambda w: -order.get(w, 0))
    cur = conn.execute(
        "INSERT INTO alerts (mode, replay, run_id, date, level, kind, wards, audiences, languages, channels, templates, "
        "ward_values, reason, status, supersedes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'draft', ?, ?)",
        (mode, replay, run_id, day, level, kind, json.dumps(wards), json.dumps(cfg["audiences"]),
         json.dumps(cfg["languages"]), json.dumps(cfg["channels"]), json.dumps(_templates(level), ensure_ascii=False),
         json.dumps(_ward_values(conn, run_id, wards, day, level, probs), ensure_ascii=False, default=float),
         reason, supersedes, db.now()))
    alert_id = int(cur.lastrowid)
    db.log(conn, "alert_drafted", {"alert_id": alert_id, "date": day, "level": level, "kind": kind,
                                   "wards": wards, "supersedes": supersedes})
    return alert_id


def _plan(conn, *, mode, replay, run_id, day, level, kind, wards, reason, probs) -> int | None:
    """Create a draft unless every ward is already covered (see module docstring)."""
    existing = [dict(r) for r in conn.execute(
        "SELECT * FROM alerts WHERE mode=? AND IFNULL(replay,'')=? AND date=? AND level=? AND kind=? AND status IN "
        f"({','.join('?' * len(OPEN))}) ORDER BY alert_id", (mode, replay or "", day, level, kind, *OPEN))]
    covered = {w for a in existing for w in json.loads(a["wards"])}
    new = [w for w in wards if w not in covered]
    if not new:
        return None
    drafts = [a for a in existing if a["status"] == "draft"]
    decided = [a for a in existing if a["status"] != "draft"]
    if drafts:
        keep = [w for a in drafts for w in json.loads(a["wards"])]
        for a in drafts:
            conn.execute("UPDATE alerts SET status='superseded', updated_at=? WHERE alert_id=?", (db.now(), a["alert_id"]))
        return _create(conn, mode=mode, replay=replay, run_id=run_id, day=day, level=level, kind=kind,
                       wards=keep + new, reason=reason, probs=probs, supersedes=drafts[-1]["alert_id"])
    return _create(conn, mode=mode, replay=replay, run_id=run_id, day=day, level=level, kind=kind, wards=new,
                   reason=reason + (" (additional wards)" if decided else ""), probs=probs,
                   supersedes=decided[-1]["alert_id"] if decided else None)


def generate(conn, run: dict, prob_run: dict | None, replay: str | None, probs_by_day: dict,
             from_day: str | None = None) -> list[int]:
    """Draft alerts for every day (from `from_day`) with wards at or above the minimum level."""
    mode = "replay" if replay else "live"
    min_i = LEVELS.index(wf()["min_level"])
    rows = [{"ward_id": r["ward_id"], "date": r["date"], **json.loads(r["data"])} for r in conn.execute(
        "SELECT ward_id, date, data FROM daily_scores WHERE run_id=? ORDER BY date", (run["run_id"],))]
    df = pd.DataFrame(rows)
    if from_day:
        df = df[df["date"] >= from_day]
    created = []
    for (day, level), g in df.groupby(["date", "alert_mri"]):
        if LEVELS.index(level) < min_i:
            continue
        probs = probs_by_day.get(day, {})
        n = len(g)
        aid = _plan(conn, mode=mode, replay=replay, run_id=run["run_id"], day=day, level=level, kind="level",
                    wards=list(g["ward_id"]), probs=probs,
                    reason=f"Mortality risk {level.title()} in {n} ward{'s' if n > 1 else ''}")
        if aid:
            created.append(aid)
    if prob_run and not replay:                      # probability triggers → preparedness alerts
        trig = pd.DataFrame([dict(r) for r in conn.execute(
            "SELECT ward_id, date, lead_days, probability FROM triggers WHERE run_id=?", (prob_run["run_id"],))])
        for day, g in (trig.groupby("date") if len(trig) else []):
            if from_day and day < from_day:
                continue
            aid = _plan(conn, mode=mode, replay=None, run_id=run["run_id"], day=day, level="orange", kind="preparedness",
                        wards=list(g["ward_id"]), probs=probs_by_day.get(day, {}),
                        reason=f"Chance of Red ≥ 40% within 3 days in {len(g)} wards (Orange preparedness)")
            if aid:
                created.append(aid)
    return created


# ---------- reading and rendering

def load(conn, alert_id: int) -> dict:
    r = conn.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
    if r is None:
        raise KeyError(alert_id)
    a = dict(r)
    for k in ("wards", "audiences", "languages", "channels", "templates", "ward_values"):
        a[k] = json.loads(a[k])
    return a


def render(alert: dict, ward_id: str, lang: str, audience: str) -> dict:
    tpl = alert["templates"][lang][audience]
    vals = alert["ward_values"][ward_id][lang]
    sms = advisories.fill(tpl["sms"], vals)
    return {"sms": sms, "sms_chars": len(sms), "sms_fits": len(sms) <= advisories.SMS_LIMIT[lang],
            "long": advisories.fill(tpl["long"], vals)}


def summary(alert: dict) -> dict:
    names = {w: alert["ward_values"][w]["_meta"]["ward_name"] for w in alert["wards"]}
    out = {k: v for k, v in alert.items() if k not in ("templates", "ward_values")}
    out["ward_names"] = [names[w] for w in alert["wards"]]
    return out


def problems(alert: dict) -> list[str]:
    """Rendered messages that do not fit (blocking approval)."""
    bad = []
    for w in alert["wards"]:
        for lang in alert["languages"]:
            for aud in alert["audiences"]:
                r = render(alert, w, lang, aud)
                if not r["sms_fits"]:
                    bad.append(f"{alert['ward_values'][w]['_meta']['ward_name']} {lang}/{aud}: SMS {r['sms_chars']} chars")
    return bad


# ---------- workflow

def _require(alert: dict, status: str, action: str) -> None:
    if alert["status"] != status:
        raise WorkflowError(f"cannot {action} an alert that is {alert['status']} (must be {status})")


def _officer(name: str | None) -> str:
    name = (name or "").strip()
    if not name:
        raise WorkflowError("an officer name is required")
    return name


def edit(conn, alert_id: int, officer: str, changes: dict) -> dict:
    officer = _officer(officer)
    a = load(conn, alert_id)
    _require(a, "draft", "edit")
    cfg = wf()
    allowed = {"wards": set(a["ward_values"]), "audiences": set(cfg["audiences"]),
               "languages": set(cfg["languages"]), "channels": set(cfg["channels"])}
    upd, diff = {}, {}
    for key, ok in allowed.items():
        if changes.get(key) is None:
            continue
        vals = list(dict.fromkeys(changes[key]))
        if not vals or not set(vals) <= ok:
            raise WorkflowError(f"{key} must be a non-empty subset of {sorted(ok)}")
        upd[key], diff[key] = json.dumps(vals), vals
    if changes.get("templates"):
        tpl = a["templates"]
        for lang, per_aud in changes["templates"].items():
            for aud, parts in per_aud.items():
                if lang not in tpl or aud not in tpl[lang]:
                    raise WorkflowError(f"unknown template {lang}/{aud}")
                for part in ("sms", "long"):
                    if parts.get(part) is not None:
                        tpl[lang][aud][part] = str(parts[part])
                        diff.setdefault("templates", []).append(f"{lang}/{aud}/{part}")
        upd["templates"] = json.dumps(tpl, ensure_ascii=False)
    if not upd:
        raise WorkflowError("nothing to change")
    sets = ", ".join(f"{k}=?" for k in upd)
    conn.execute(f"UPDATE alerts SET {sets}, updated_at=? WHERE alert_id=?", (*upd.values(), db.now(), alert_id))
    db.log(conn, "alert_edited", {"alert_id": alert_id, "changes": diff}, actor=officer)
    return load(conn, alert_id)


def approve(conn, alert_id: int, officer: str, note: str = "") -> dict:
    officer = _officer(officer)
    a = load(conn, alert_id)
    _require(a, "draft", "approve")
    bad = problems(a)
    if bad:
        raise WorkflowError("some messages are too long: " + "; ".join(bad[:5]))
    conn.execute("UPDATE alerts SET status='approved', decided_at=?, decided_by=?, decision_note=? WHERE alert_id=?",
                 (db.now(), officer, note, alert_id))
    db.log(conn, "alert_approved", {"alert_id": alert_id, "note": note}, actor=officer)
    return load(conn, alert_id)


def reject(conn, alert_id: int, officer: str, reason: str) -> dict:
    officer = _officer(officer)
    if not (reason or "").strip():
        raise WorkflowError("a reason is required to reject an alert")
    a = load(conn, alert_id)
    _require(a, "draft", "reject")
    conn.execute("UPDATE alerts SET status='rejected', decided_at=?, decided_by=?, decision_note=? WHERE alert_id=?",
                 (db.now(), officer, reason.strip(), alert_id))
    db.log(conn, "alert_rejected", {"alert_id": alert_id, "reason": reason.strip()}, actor=officer)
    return load(conn, alert_id)


# ---------- CAP 1.2

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
SEVERITY = {"yellow": "Moderate", "orange": "Severe", "red": "Extreme"}
RESPONSE = {"yellow": "Monitor", "orange": "Prepare", "red": "Avoid"}
LANG_TAG = {"en": "en-IN", "hi": "hi-IN", "gu": "gu-IN"}
EVENT = {"en": "Heat wave", "hi": "लू (हीट वेव)", "gu": "લૂ (હીટ વેવ)"}


def _iso(ts: datetime) -> str:
    return ts.astimezone(IST).replace(microsecond=0).isoformat()


def identifier(a: dict) -> str:
    return f"in.ahmedabad.heat-prototype.{a['alert_id']}"


def cap_xml(conn, a: dict) -> str:
    """CAP 1.2 XML for an alert: one <info> per language, one <area> per ward (outline simplified)."""
    import xml.etree.ElementTree as ET

    import geopandas as gpd
    from shapely.geometry import shape

    cfg = wf()
    ET.register_namespace("", CAP_NS)
    q = lambda tag: f"{{{CAP_NS}}}{tag}"  # noqa: E731
    sent = datetime.fromisoformat(a["decided_at"] or a["created_at"])
    if a["mode"] == "replay":                  # a replay is issued "as if" on the morning of the event day
        d = pd.Timestamp(a["date"])
        sent = datetime(d.year, d.month, d.day, 6, 0, tzinfo=IST)
    if a["status"] in ("draft", "rejected", "superseded"):
        status = "Draft"
    else:
        status = "Exercise" if a["mode"] == "replay" else "Actual"
    root = ET.Element(q("alert"))
    for tag, val in (("identifier", identifier(a)), ("sender", cfg["cap_sender"]), ("sent", _iso(sent)),
                     ("status", status), ("msgType", "Update" if a["supersedes"] else "Alert"), ("scope", "Public")):
        ET.SubElement(root, q(tag)).text = val
    if a["supersedes"]:
        prev = conn.execute("SELECT alert_id, decided_at, created_at FROM alerts WHERE alert_id=?", (a["supersedes"],)).fetchone()
        if prev:
            ET.SubElement(root, q("references")).text = (
                f"{cfg['cap_sender']},in.ahmedabad.heat-prototype.{prev['alert_id']},"
                f"{_iso(datetime.fromisoformat(prev['decided_at'] or prev['created_at']))}")
    if a["mode"] == "replay":
        ET.SubElement(root, q("note")).text = f"Replay of a past event ({a['replay']}); not a real warning."

    day = pd.Timestamp(a["date"])
    lead = (day.date() - sent.astimezone(IST).date()).days
    urgency = "Immediate" if lead <= 0 else "Expected" if lead == 1 else "Future"
    ps = [a["ward_values"][w]["_meta"].get("p_level") for w in a["wards"]]
    ps = [p for p in ps if p is not None]
    certainty = "Likely" if not ps or sorted(ps)[len(ps) // 2] >= 0.5 else "Possible"
    effective = datetime(day.year, day.month, day.day, 0, 0, tzinfo=IST)
    first = a["wards"][0]

    geoms = {r["ward_id"]: shape(json.loads(r["geometry"])) for r in conn.execute(
        f"SELECT ward_id, geometry FROM wards WHERE ward_id IN ({','.join('?' * len(a['wards']))})", a["wards"])}
    g = gpd.GeoSeries(geoms, crs=4326).to_crs(32643).simplify(cfg["cap_polygon_tolerance_m"]).to_crs(4326)

    for lang in a["languages"]:
        info = ET.SubElement(root, q("info"))
        for tag, val in (("language", LANG_TAG[lang]), ("category", "Met"), ("category", "Health"), ("event", EVENT[lang]),
                         ("responseType", RESPONSE[a["level"]]), ("urgency", urgency), ("severity", SEVERITY[a["level"]]),
                         ("certainty", certainty), ("effective", _iso(effective)),
                         ("expires", _iso(effective + timedelta(days=1))), ("senderName", cfg["sender_name"])):
            ET.SubElement(info, q(tag)).text = val
        head = a["ward_values"][first][lang]["level"]
        ET.SubElement(info, q("headline")).text = f"{head}: {len(a['wards'])} ward(s), {a['date']}"
        ET.SubElement(info, q("description")).text = (
            f"{a['reason']}. Wards: " + ", ".join(a["ward_values"][w]["_meta"]["ward_name"] for w in a["wards"]))
        if "public" in a["audiences"]:
            ET.SubElement(info, q("instruction")).text = render(a, first, lang, "public")["long"]
        for w in a["wards"]:
            area = ET.SubElement(info, q("area"))
            ET.SubElement(area, q("areaDesc")).text = f"{a['ward_values'][w]['_meta']['ward_name']} ward, Ahmedabad"
            geom = g[w]
            poly = max(geom.geoms, key=lambda p: p.area) if geom.geom_type == "MultiPolygon" else geom
            ET.SubElement(area, q("polygon")).text = " ".join(f"{y:.5f},{x:.5f}" for x, y in poly.exterior.coords)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# ---------- IVR voice (TwiML). Hindi and Gujarati prompts are drafts needing native-speaker review.

IVR_PROMPTS = {
    "en": {"menu": "Press 1 to hear this message again. Press 2 to hear the nearest cooling places.",
           "cooling": "Nearest cooling places: {places}.", "bye": "Stay safe. Goodbye."},
    "hi": {"menu": "यह संदेश फिर से सुनने के लिए 1 दबाएं। नज़दीकी ठंडी जगहें सुनने के लिए 2 दबाएं।",
           "cooling": "नज़दीकी ठंडी जगहें: {places}।", "bye": "सुरक्षित रहें। धन्यवाद।"},
    "gu": {"menu": "આ સંદેશ ફરીથી સાંભળવા 1 દબાવો. નજીકની ઠંડી જગ્યાઓ સાંભળવા 2 દબાવો.",
           "cooling": "નજીકની ઠંડી જગ્યાઓ: {places}.", "bye": "સુરક્ષિત રહો. આભાર."},
}


def twiml(a: dict, ward_id: str, lang: str, audience: str = "public", digit: str | None = None,
          base_url: str | None = None) -> str:
    """TwiML for the voice call. Without `base_url` (no public callback), the message plays twice."""
    from xml.sax.saxutils import escape

    voice = wf()["voice"][lang]
    say = lambda text: f'<Say voice="{voice}" language="{LANG_TAG[lang]}">{escape(text)}</Say>'  # noqa: E731
    p = IVR_PROMPTS[lang]
    msg = render(a, ward_id, lang, audience)["long"]
    if digit == "2":
        places = ", ".join(a["ward_values"][ward_id]["_meta"]["cooling"]) or "—"
        body = say(p["cooling"].format(places=places)) + say(p["bye"])
    elif not base_url:
        body = say(msg) + '<Pause length="1"/>' + say(msg) + say(p["bye"])
    else:
        action = f"{base_url}/ivr/{a['alert_id']}/{ward_id}/menu?lang={lang}&amp;audience={audience}"
        body = (f'<Gather numDigits="1" timeout="6" action="{action}" method="POST">'
                + say(msg) + say(p["menu"]) + "</Gather>" + say(p["bye"]))
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
