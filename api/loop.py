"""Phase 8 storage and logic behind the API: what-if scenarios and health-worker reports.

Reports are stored only as counts per (ward, day, age band, severity, outcome, reporter
role); a submission increments a count and nothing else about it is kept. Synthetic demo
reports carry synthetic = 1 and are shown as such.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from api import db, jobs
from heatrisk import feedback, load_config, scenarios
from heatrisk.pipeline import load_wards


class InputError(ValueError):
    pass


# ---------- scenarios

@lru_cache(maxsize=4)
def _weather(name: str) -> pd.DataFrame:
    path = jobs.replay_weather_path(name)
    if not path.exists():
        raise InputError(f"replay weather for '{name}' not found: run `python -m api.cli replay {name}`")
    return pd.read_parquet(path)


def run_scenario(changes: list[dict], replay: str | None = None) -> dict:
    cfg = load_config()
    name = replay or cfg["scenarios"]["default_replay"]
    if name not in jobs.REPLAYS:
        raise InputError(f"unknown replay '{name}'")
    try:
        result = scenarios.run(load_wards(), _weather(name), changes, cfg)
    except scenarios.ScenarioError as e:
        raise InputError(str(e)) from None
    names = load_wards().set_index("ward_id")["ward_name"]
    for w in result["wards"]:
        w["ward_name"] = names[w["ward_id"]]
    result.update({"replay": name, "period": jobs.REPLAYS[name]["title"]})
    return result


def save_scenario(conn, name: str, author: str, changes: list[dict], replay: str | None) -> int:
    if not (name or "").strip():
        raise InputError("a scenario name is required")
    result = run_scenario(changes, replay)
    cur = conn.execute("INSERT INTO scenarios (name, author, created_at, replay, spec, result) VALUES (?,?,?,?,?,?)",
                       (name.strip(), (author or "").strip() or None, db.now(), result["replay"],
                        json.dumps(changes), json.dumps(result)))
    db.log(conn, "scenario_saved", {"scenario_id": cur.lastrowid, "name": name.strip()}, actor=(author or "unknown"))
    return int(cur.lastrowid)


# ---------- reports

def _mode(replay: str | None) -> tuple[str, str]:
    return ("replay", replay) if replay else ("live", "")


def add_report(conn, report: dict, replay: str | None, synthetic: bool = False, count: int = 1) -> None:
    fb = load_config()["feedback"]
    checks = {"age_band": fb["age_bands"], "severity": fb["severities"], "outcome": fb["outcomes"], "role": fb["roles"]}
    for key, allowed in checks.items():
        if report.get(key) not in allowed:
            raise InputError(f"{key} must be one of {allowed}")
    if conn.execute("SELECT 1 FROM wards WHERE ward_id=?", (report.get("ward_id"),)).fetchone() is None:
        raise InputError("unknown ward")
    try:
        day = pd.Timestamp(report.get("date")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        raise InputError("date must be YYYY-MM-DD") from None
    mode, rep = _mode(replay)
    conn.execute(
        "INSERT INTO report_counts VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET count = count + excluded.count",
        (mode, rep, report["ward_id"], day, report["age_band"], report["severity"], report["outcome"], report["role"],
         int(synthetic), count))


def counts(conn, replay: str | None) -> pd.DataFrame:
    mode, rep = _mode(replay)
    return pd.DataFrame([dict(r) for r in conn.execute(
        "SELECT ward_id, date, SUM(count) AS reports, MAX(synthetic) AS synthetic FROM report_counts "
        "WHERE mode=? AND replay=? GROUP BY ward_id, date", (mode, rep))], columns=["ward_id", "date", "reports", "synthetic"])


def scores(conn, run_id: int) -> pd.DataFrame:
    pop = dict(conn.execute("SELECT ward_id, json_extract(attributes, '$.population') FROM wards").fetchall())
    rows = [{"ward_id": r[0], "date": r[1], "mri": json.loads(r[2])["mri"]} for r in conn.execute(
        "SELECT ward_id, date, data FROM daily_scores WHERE run_id=?", (run_id,))]
    df = pd.DataFrame(rows)
    df["population"] = df["ward_id"].map(pop)
    return df


def seed_synthetic(conn, run_id: int, replay: str, total: int = 69) -> int:
    """Synthetic demo reports for a replay (69 = heatstroke cases reported in Ahmedabad, May 2024),
    with an injected cluster in Vatva on 23-24 May to demonstrate the anomaly flag."""
    mode, rep = _mode(replay)
    conn.execute("DELETE FROM report_counts WHERE mode=? AND replay=? AND synthetic=1", (mode, rep))
    syn = feedback.synthetic_reports(scores(conn, run_id), total,
                                     anomaly={"ward_id": "AMC-47", "dates": ["2024-05-23", "2024-05-24"], "extra": 6})
    for r in syn.itertuples():
        add_report(conn, {"ward_id": r.ward_id, "date": r.date, "age_band": "15-44", "severity": "moderate",
                          "outcome": "treated", "role": "asha"}, replay, synthetic=True, count=int(r.reports))
    db.log(conn, "synthetic_reports_seeded", {"replay": replay, "reports": int(syn["reports"].sum())})
    return int(syn["reports"].sum())


def summary(conn, run_id: int, replay: str | None, day: str | None) -> dict:
    cfg = load_config()
    c, s = counts(conn, replay), scores(conn, run_id)
    names = dict(conn.execute("SELECT ward_id, ward_name FROM wards").fetchall())
    fl = feedback.flags(c[["ward_id", "date", "reports"]], s, cfg) if len(c) else pd.DataFrame()
    fl_records = fl.assign(ward_name=fl["ward_id"].map(names)).to_dict("records") if len(fl) else []
    out = {"total_reports": int(c["reports"].sum()) if len(c) else 0,
           "includes_synthetic": bool(len(c) and c["synthetic"].max()),
           "flags": fl_records,
           "by_day": c.groupby("date")["reports"].sum().astype(int).to_dict() if len(c) else {}}
    if day:
        d = c[c["date"] == day]
        exp = feedback.expected(d.set_index("ward_id")["reports"], s[s["date"] == day]) if len(d) else pd.Series(dtype=float)
        out["day"] = {"date": day, "wards": [
            {"ward_id": w, "ward_name": names[w], "reports": int(r), "expected": round(float(exp.get(w, 0)), 2)}
            for w, r in d.set_index("ward_id")["reports"].items()]}
    return out


def recalibration(conn, run_id: int, replay: str | None) -> dict:
    cfg = load_config()
    c = counts(conn, replay)
    if c.empty:
        return {"wards": [], "note": "no reports yet"}
    cur = pd.Series({r[0]: r[1] for r in conn.execute(
        "SELECT ward_id, json_extract(attributes, '$.historical_factor') FROM wards")}, dtype=float)
    r = feedback.recalibrate(c[["ward_id", "date", "reports"]], scores(conn, run_id), cur, cfg)
    names = dict(conn.execute("SELECT ward_id, ward_name FROM wards").fetchall())
    r["ward_name"] = r["ward_id"].map(names)
    return {"applied": False, "auto_apply": cfg["feedback"]["auto_apply_recalibration"],
            "note": "Proposal only: the authority reviews and, if accepted, records the new H_m in "
                    "data/manual/ward_attributes.csv (historical_factor) with a changelog entry.",
            "includes_synthetic": bool(c["synthetic"].max()),
            "wards": r.sort_values("p_value").where(r.notna(), None).to_dict("records")}
