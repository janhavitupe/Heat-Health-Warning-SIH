"""Forecast products: ward trajectories, peaks, and heatwave events (Phase 4).

  ward_peaks      per ward: the forecast day with the highest MRI and the hour of peak UTCI that day
  hourly_curves   per ward and hour: air temperature and thermal indicators (ward detail panel)
  detect_events   runs of ≥ event_min_days consecutive days on which at least event_min_share of
                  wards are at Orange or above (IMD also requires 2 consecutive days for a heatwave)
"""

from __future__ import annotations

import pandas as pd

from heatrisk import vulnerability
from heatrisk.pipeline import score_ward

ORANGE_PLUS = ("orange", "red")


def run_wards(wx: pd.DataFrame, wards: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score every ward on one WeatherFrame; return (daily table with explanations' top factors, hourly curves)."""
    pvi = vulnerability.compute_pvi(wards, cfg)
    daily, hourly = [], []
    for ward_id in wards["ward_id"]:
        res = score_ward(ward_id, wx, wards, cfg, pvi=pvi)
        d = res["daily"].reset_index()
        d["ward_id"] = ward_id
        d["top_factors"] = ["; ".join(f"{c.label} {c.points:+.0f}" for c in res["explanations"][t]["mri"].ranked()[:3])
                            for t in res["daily"].index]
        daily.append(d)
        h = res["hourly"][["t2m", "mrt", "utci", "wbgt", "heat_index"]].rename_axis("time").reset_index()
        h["ward_id"] = ward_id
        hourly.append(h)
    return pd.concat(daily, ignore_index=True), pd.concat(hourly, ignore_index=True)


def ward_peaks(daily: pd.DataFrame, hourly: pd.DataFrame, issue_date) -> pd.DataFrame:
    """Per ward, over days from `issue_date` on: peak day, peak MRI/HRI and alert, and hour of peak UTCI."""
    issue = pd.Timestamp(issue_date).normalize()
    fc = daily[pd.to_datetime(daily["date"]) >= issue]
    idx = fc.groupby("ward_id")["mri"].idxmax()
    peaks = fc.loc[idx, ["ward_id", "date", "mri", "hri", "alert_mri"]].rename(
        columns={"date": "peak_day", "mri": "peak_mri", "hri": "peak_hri", "alert_mri": "peak_alert"})
    h = hourly.assign(day=hourly["time"].dt.tz_localize(None).dt.normalize())
    h = h.merge(peaks[["ward_id", "peak_day"]], left_on=["ward_id", "day"], right_on=["ward_id", "peak_day"])
    hour = h.loc[h.groupby("ward_id")["utci"].idxmax(), ["ward_id", "time", "utci"]]
    # Open-Meteo timestamps mark the end of the hour, so a 15:00 stamp is the hour 14:00–15:00
    end = hour["time"].dt.hour
    hour["peak_hour"] = [f"{(e - 1) % 24:02d}:00–{e:02d}:00" for e in end]
    return peaks.merge(hour[["ward_id", "peak_hour", "utci"]].rename(columns={"utci": "peak_utci"}), on="ward_id")


def detect_events(daily: pd.DataFrame, cfg: dict, n_wards: int) -> list[dict]:
    """Group consecutive Orange/Red days into heatwave events.

    Returns one dict per event: start, peak (day with most wards at Orange+, then highest
    median MRI), end, days, wards affected, peak counts, and whether the event is still
    running at the end of the data (`open_ended`, i.e. the end is not yet known).
    """
    fcfg = cfg["forecast"]
    need = max(1, int(round(fcfg["event_min_share"] * n_wards)))
    by_day = daily.assign(hot=daily["alert_mri"].isin(ORANGE_PLUS),
                          red=daily["alert_mri"] == "red").groupby("date")
    city = pd.DataFrame({"n_orange_plus": by_day["hot"].sum(), "n_red": by_day["red"].sum(),
                         "median_mri": by_day["mri"].median()}).sort_index()
    on = city["n_orange_plus"] >= need
    run_id = (on != on.shift()).cumsum()
    last_day = city.index.max()
    events = []
    for _, days in city[on].groupby(run_id[on]):
        if len(days) < fcfg["event_min_days"]:
            continue
        peak = days.sort_values(["n_orange_plus", "median_mri"], ascending=False).index[0]
        span = daily[pd.to_datetime(daily["date"]).between(days.index[0], days.index[-1])]
        affected = sorted(span.loc[span["alert_mri"].isin(ORANGE_PLUS), "ward_id"].unique())
        events.append({
            "start": days.index[0].strftime("%Y-%m-%d"), "peak": peak.strftime("%Y-%m-%d"),
            "end": days.index[-1].strftime("%Y-%m-%d"), "days": len(days),
            "open_ended": bool(days.index[-1] == last_day),
            "peak_wards_orange_plus": int(days.loc[peak, "n_orange_plus"]),
            "peak_wards_red": int(days.loc[peak, "n_red"]), "peak_median_mri": round(float(days.loc[peak, "median_mri"]), 1),
            "wards_affected": affected,
        })
    return events
