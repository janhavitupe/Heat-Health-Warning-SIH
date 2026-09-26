"""Safe work windows for outdoor workers — proposal §6.10 (Innovation 4).

For every ward and hour, WBGT is compared with the ACGIH heat-stress limits in
config `work_windows` (TLV for acclimatized workers, Action Limit for
unacclimatized). Each limit applies to a share of every work/rest cycle, read
per hour as is usual in practice:

  75–100% work  → continuous work
  50–75%        → 45 min work / 15 min rest each hour
  25–50%        → 30 min work / 30 min rest
  0–25%         → 15 min work / 45 min rest
  above all     → work not advised

The status for an hour is the most work-intensive regime whose limit is at or
above the hour's WBGT. Unacclimatized limits are suggested for the first
`unacclimatized_first_days` days of a heatwave event: even local workers need
up to two weeks to adapt to heat beyond what they are used to (NIOSH/OSHA).
"""

from __future__ import annotations

import pandas as pd

STATUSES = ["continuous", "45/15", "30/30", "15/45", "not_advised"]
STATUS_TEXT = {
    "continuous": "normal work",
    "45/15": "15 min rest per hour",
    "30/30": "30 min rest per hour",
    "15/45": "45 min rest per hour",
    "not_advised": "not advised",
}
WORKLOAD_TEXT = {"light": "Light work", "moderate": "Moderate work", "heavy": "Heavy work", "very_heavy": "Very heavy work"}


def hour_status(wbgt: float, limits: list[float | None]) -> str:
    """Status for one hour given the four limits (75–100%, 50–75%, 25–50%, 0–25% work)."""
    for status, limit in zip(STATUSES, limits):
        if limit is not None and wbgt <= limit:
            return status
    return "not_advised"


def hourly_statuses(hourly: pd.DataFrame, cfg: dict, acclimatized: bool = True) -> pd.DataFrame:
    """Status per hour and workload. `hourly` needs a tz-aware `time` index or column and `wbgt`."""
    ww = cfg["work_windows"]
    table = ww["acclimatized" if acclimatized else "unacclimatized"]
    h = hourly.set_index("time") if "time" in hourly else hourly
    out = pd.DataFrame(index=h.index)
    out["wbgt"] = h["wbgt"]
    for load in ww["workloads"]:
        out[load] = [hour_status(v, table[load]) for v in h["wbgt"]]
    return out


def intervals(statuses: pd.Series) -> list[dict]:
    """Merge consecutive hours with the same status. Times mark the end of each hour."""
    runs, start, prev = [], None, None
    for t, s in statuses.items():
        if s != prev:
            if prev is not None:
                runs.append({"status": prev, "start": start, "end": last})
            start, prev = t - pd.Timedelta(hours=1), s
        last = t
    if prev is not None:
        runs.append({"status": prev, "start": start, "end": last})
    return [{"status": r["status"], "start": r["start"].strftime("%H:%M"), "end": r["end"].strftime("%H:%M")} for r in runs]


def day_schedule(hourly: pd.DataFrame, cfg: dict, acclimatized: bool = True) -> dict:
    """Schedule for one ward-day within working hours: per workload, restricted intervals and a summary line."""
    ww = cfg["work_windows"]
    first, last = ww["day_hours"]
    st = hourly_statuses(hourly, cfg, acclimatized)
    ends = st.index.hour.where(st.index.hour != 0, 24)          # hour ending 00:00 closes the day
    st = st[(ends > first) & (ends <= last)]
    out = {"acclimatized": acclimatized, "workloads": {}}
    for load in ww["workloads"]:
        ivs = [iv for iv in intervals(st[load]) if iv["status"] != "continuous"]
        out["workloads"][load] = {"restricted": ivs, "summary": summary_line(load, ivs)}
    out["max_wbgt"] = round(float(st["wbgt"].max()), 1) if len(st) else None
    return out


def summary_line(load: str, ivs: list[dict]) -> str:
    """e.g. "Heavy work: not advised 11:00–17:00; 30 min rest per hour 09:00–11:00, 17:00–18:00"."""
    if not ivs:
        return f"{WORKLOAD_TEXT[load]}: normal work all day"
    parts = {}
    for iv in ivs:
        parts.setdefault(iv["status"], []).append(f"{iv['start']}–{iv['end']}")
    ordered = [s for s in reversed(STATUSES) if s in parts]           # most restrictive first
    return f"{WORKLOAD_TEXT[load]}: " + "; ".join(f"{STATUS_TEXT[s]} {', '.join(parts[s])}" for s in ordered)


def acclimatized_on(date, events: list[dict], cfg: dict) -> bool:
    """False (use unacclimatized limits) during the first N days of a heatwave event."""
    n = cfg["work_windows"]["unacclimatized_first_days"]
    d = pd.Timestamp(date).normalize()
    for e in events:
        start = pd.Timestamp(e["start"])
        if start <= d <= pd.Timestamp(e["end"]) and (d - start).days < n:
            return False
    return cfg["work_windows"]["acclimatized_default"]
