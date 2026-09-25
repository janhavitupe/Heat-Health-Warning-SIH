"""Daily forecast run (Phase 4): deterministic + ensemble forecast → every ward.

  1. Open-Meteo deterministic forecast (past days + horizon) at the city grid point,
     scored for every ward (downscaling applied per ward) → trajectories, peaks, events.
  2. Open-Meteo ensemble (ECMWF, GFS, ICON members) scored the same way →
     P(Yellow+/Orange+/Red), most likely level, confidence, and probability triggers.

Outputs in data/forecast/<issue date>/ (not committed):
  wards_daily.csv   one row per ward-day: scores, alert, top factors, probabilities,
                    confidence, and the ward's peak day/hour
  hourly.csv        per ward and hour: t2m, MRT, UTCI, WBGT, Heat Index
  events.json       heatwave events (start, peak, end, wards affected)
  triggers.csv      probability trigger rules that fired
  summary.md        short human-readable summary
Usage:  python scripts/run_forecast.py [--no-ensemble] [--models ecmwf_ifs025,gfs025]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from heatrisk import ensemble, forecast, load_config  # noqa: E402
from heatrisk.config import ROOT  # noqa: E402
from heatrisk.pipeline import load_wards  # noqa: E402
from heatrisk.weather import fetch_ensemble, fetch_forecast  # noqa: E402

LEVELS = ensemble.LEVELS


def summary(issue: pd.Timestamp, table: pd.DataFrame, events: list[dict], trig: pd.DataFrame,
            n_members: int | None) -> str:
    fc = table[table["date"] >= issue]
    lines = [f"# Heat-health forecast — issued {issue:%d %b %Y}", "",
             f"Ensemble: {n_members} forecast runs." if n_members else "Ensemble: not run (deterministic only).", "",
             "| Day | Wards Yellow / Orange / Red | Highest-risk ward (MRI) | Max P(Red) |", "|---|---|---|---|"]
    for day, d in fc.groupby("date"):
        n = d["alert_mri"].value_counts()
        top = d.loc[d["mri"].idxmax()]
        pred = f"{d['p_red'].max():.0%}" if "p_red" in d else "—"
        lines.append(f"| {day:%a %d %b} | {n.get('yellow', 0)} / {n.get('orange', 0)} / {n.get('red', 0)} | "
                     f"{top['ward_name']} ({top['mri']:.0f}) | {pred} |")
    lines += ["", f"Heatwave events: {len(events)}"]
    for e in events:
        lines.append(f"- {e['start']} to {e['end']}{' (continues beyond forecast)' if e['open_ended'] else ''}: "
                     f"peak {e['peak']}, {e['peak_wards_orange_plus']} wards Orange+, {e['peak_wards_red']} Red")
    lines += ["", f"Probability triggers fired: {len(trig)}"]
    for (rule, action), g in (trig.groupby(["rule", "action"]) if len(trig) else []):
        lines.append(f"- {action}: {g['ward_id'].nunique()} wards ({rule})")
    lines += ["", "All scores are model estimates, not clinical predictions."]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ensemble", action="store_true")
    ap.add_argument("--models", help="comma-separated ensemble models (default: config)")
    args = ap.parse_args()

    cfg, wards = load_config(), load_wards()
    c, fcfg = cfg["city"]["centre"], cfg["forecast"]
    issue = pd.Timestamp.now(tz=cfg["city"]["timezone"]).tz_localize(None).normalize()

    t0 = time.time()
    wx = fetch_forecast(c["lat"], c["lon"], days=fcfg["days"], past_days=fcfg["past_days"])
    daily, hourly = forecast.run_wards(wx, wards, cfg)
    daily["date"] = pd.to_datetime(daily["date"])
    peaks = forecast.ward_peaks(daily, hourly, issue)
    events = forecast.detect_events(daily, cfg, len(wards))
    print(f"deterministic: {len(wards)} wards in {time.time() - t0:.0f}s")

    table = daily.merge(wards[["ward_id", "ward_name", "zone"]], on="ward_id")
    trig = pd.DataFrame(columns=["ward_id", "date", "lead_days", "rule", "probability", "action"])
    n_members = None
    if not args.no_ensemble:
        t1 = time.time()
        models = args.models.split(",") if args.models else cfg["ensemble"]["models"]
        members = fetch_ensemble(c["lat"], c["lon"], models, days=fcfg["days"], past_days=fcfg["past_days"] + 1)
        n_members = len(members)
        scores = ensemble.score_members(members, wards, cfg)
        probs = ensemble.probabilities(scores, cfg)
        probs["date"] = pd.to_datetime(probs["date"])
        table = table.merge(probs, on=["ward_id", "date"], how="left")
        trig = ensemble.triggers(probs, cfg, issue)
        print(f"ensemble: {n_members} members x {len(wards)} wards in {time.time() - t1:.0f}s")
    table = table.merge(peaks, on="ward_id", how="left")

    out = ROOT / "data" / "forecast" / f"{issue:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "wards_daily.csv", index=False)
    hourly.to_csv(out / "hourly.csv", index=False)
    (out / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    trig.to_csv(out / "triggers.csv", index=False)
    text = summary(issue, table, events, trig, n_members)
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
