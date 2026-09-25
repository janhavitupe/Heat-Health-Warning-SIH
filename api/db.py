"""SQLite storage for the prototype (PostGIS is the documented production path).

Every refresh is a *run*. The API serves the latest successful run of each kind,
so a failed refresh never replaces good data:

  forecast   deterministic forecast, refreshed hourly (past days + 5-day horizon)
  ensemble   ensemble probabilities, refreshed daily
  replay     a past event served through the same endpoints (e.g. "may2024")

Ward geometry is stored as GeoJSON text: with 48 wards no spatial queries are needed.
Daily rows are stored as JSON so the output schema can grow without migrations.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from heatrisk.config import ROOT

DB_PATH = Path(os.environ.get("HEAT_DB", ROOT / "data" / "api" / "heat.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS wards (
    ward_id TEXT PRIMARY KEY, ward_no INTEGER, ward_name TEXT, zone TEXT,
    geometry TEXT NOT NULL, attributes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT,
    issued_date TEXT, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT NOT NULL, n_members INTEGER, source TEXT, error TEXT);
CREATE INDEX IF NOT EXISTS runs_kind ON runs(kind, status, run_id);
CREATE TABLE IF NOT EXISTS daily_scores (
    run_id INTEGER, ward_id TEXT, date TEXT, data TEXT NOT NULL,
    PRIMARY KEY (run_id, ward_id, date));
CREATE TABLE IF NOT EXISTS hourly_scores (
    run_id INTEGER, ward_id TEXT, time TEXT, t2m REAL, mrt REAL, utci REAL, wbgt REAL, heat_index REAL,
    PRIMARY KEY (run_id, ward_id, time));
CREATE TABLE IF NOT EXISTS ensemble_probs (
    run_id INTEGER, ward_id TEXT, date TEXT, p_yellow REAL, p_orange REAL, p_red REAL,
    most_likely TEXT, p_most_likely REAL, confidence TEXT, n_members INTEGER,
    mri_p10 REAL, mri_median REAL, mri_p90 REAL, PRIMARY KEY (run_id, ward_id, date));
CREATE TABLE IF NOT EXISTS events (run_id INTEGER, event TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS triggers (
    run_id INTEGER, ward_id TEXT, date TEXT, lead_days INTEGER, rule TEXT, probability REAL, action TEXT);
-- Phase 7: alert drafts, human approval and dispatch
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, ward_id TEXT, date TEXT, level TEXT,
    status TEXT, created_at TEXT, decided_at TEXT, decided_by TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, detail TEXT);
"""

PROB_COLUMNS = ["p_yellow", "p_orange", "p_red", "most_likely", "p_most_likely", "confidence", "n_members",
                "mri_p10", "mri_median", "mri_p90"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path: Path | str | None = None):
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def log(conn: sqlite3.Connection, action: str, detail: dict | str = "", actor: str = "system") -> None:
    conn.execute("INSERT INTO audit_log (at, actor, action, detail) VALUES (?, ?, ?, ?)",
                 (now(), actor, action, detail if isinstance(detail, str) else json.dumps(detail)))


def start_run(conn: sqlite3.Connection, kind: str, name: str | None = None, source: str = "") -> int:
    cur = conn.execute("INSERT INTO runs (kind, name, started_at, status, source) VALUES (?, ?, ?, 'running', ?)",
                       (kind, name, now(), source))
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, status: str, issued_date: str | None = None,
               n_members: int | None = None, error: str | None = None) -> None:
    conn.execute("UPDATE runs SET status=?, finished_at=?, issued_date=?, n_members=?, error=? WHERE run_id=?",
                 (status, now(), issued_date, n_members, error, run_id))
    conn.commit()


def latest_run(conn: sqlite3.Connection, kind: str, name: str | None = None) -> sqlite3.Row | None:
    sql = "SELECT * FROM runs WHERE kind=? AND status='ok'"
    args: list = [kind]
    if name is not None:
        sql += " AND name=?"
        args.append(name)
    return conn.execute(sql + " ORDER BY run_id DESC LIMIT 1", args).fetchone()


def delete_runs(conn: sqlite3.Connection, run_ids: list[int]) -> None:
    """Delete runs and every row that belongs to them."""
    for table in ("daily_scores", "hourly_scores", "ensemble_probs", "events", "triggers", "runs"):
        conn.executemany(f"DELETE FROM {table} WHERE run_id=?", [(r,) for r in run_ids])


def prune(conn: sqlite3.Connection, kind: str, keep: int) -> None:
    """Delete all but the newest `keep` runs of a kind."""
    delete_runs(conn, [r[0] for r in conn.execute(
        "SELECT run_id FROM runs WHERE kind=? ORDER BY run_id DESC LIMIT -1 OFFSET ?", (kind, keep))])
