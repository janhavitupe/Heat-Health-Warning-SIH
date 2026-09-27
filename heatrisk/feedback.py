"""Health-worker feedback: anomaly flags and post-season recalibration — proposal §6.13 (Innovation 6).

Reports arrive as counts per ward, day, age band, severity and outcome. No identifiers
are ever collected or stored.

  expected cases   the day's city-wide report total shared across wards in proportion to
                   population × MRI (the model's share of risk). No absolute calibration is
                   needed, so it works from the first season.
  anomaly flag     reported ≥ min_reports, ≥ anomaly_ratio × expected, and Poisson
                   P(X ≥ reported | expected) < p_threshold: the ward has far more cases than
                   its modelled share, even if its risk score is lower.
  recalibration    after a season, H_m per ward = (reported + k) / (expected + k), shrunk
                   toward 1 by k = prior_cases pseudo-cases and clamped to the configured
                   bounds, proposed only where the season's count differs significantly from
                   expected (two-sided Poisson p < recalibration_p). Always a *proposal* for
                   authority review, never applied automatically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson


def expected(day_counts: pd.Series, scores: pd.DataFrame) -> pd.Series:
    """Expected reports per ward for one day. `scores` needs ward_id, population, mri."""
    share = scores.set_index("ward_id")
    weight = share["population"] * share["mri"].clip(lower=0)
    total = day_counts.sum()
    return (total * weight / weight.sum()).rename("expected") if weight.sum() > 0 else weight * 0


def flags(counts: pd.DataFrame, scores: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Anomalies over all days. `counts`: ward_id, date, reports. `scores`: ward_id, date, population, mri."""
    fb = cfg["feedback"]
    rows = []
    for day, c in counts.groupby("date"):
        obs = c.set_index("ward_id")["reports"]
        s = scores[scores["date"] == day]
        if s.empty or obs.sum() == 0:
            continue
        exp = expected(obs, s)
        both = pd.concat([exp, obs.reindex(exp.index).fillna(0).rename("reports")], axis=1)
        both["ratio"] = both["reports"] / both["expected"].replace(0, np.nan)
        both["p_value"] = poisson.sf(both["reports"] - 1, both["expected"].clip(lower=1e-9))
        hit = both[(both["reports"] >= fb["min_reports"]) & (both["ratio"] >= fb["anomaly_ratio"])
                   & (both["p_value"] < fb["p_threshold"])]
        for wid, r in hit.iterrows():
            rows.append({"ward_id": wid, "date": day, "reports": int(r["reports"]),
                         "expected": round(float(r["expected"]), 2), "ratio": round(float(r["ratio"]), 1),
                         "p_value": float(r["p_value"])})
    return pd.DataFrame(rows, columns=["ward_id", "date", "reports", "expected", "ratio", "p_value"])


def recalibrate(counts: pd.DataFrame, scores: pd.DataFrame, current: pd.Series, cfg: dict) -> pd.DataFrame:
    """Proposed H_m per ward from a season of reports (never applied automatically).

    `current` is the present historical_factor per ward_id (NaN = default).
    """
    fb, bounds = cfg["feedback"], cfg["risk"]["historical_factor"]
    k = fb["prior_cases"]
    exp_total, obs_total = {}, {}
    for day, c in counts.groupby("date"):
        obs = c.set_index("ward_id")["reports"]
        s = scores[scores["date"] == day]
        if s.empty:
            continue
        for wid, e in expected(obs, s).items():
            exp_total[wid] = exp_total.get(wid, 0.0) + e
            obs_total[wid] = obs_total.get(wid, 0.0) + float(obs.get(wid, 0))
    out = pd.DataFrame({"expected": pd.Series(exp_total), "reported": pd.Series(obs_total)}).fillna(0)
    out.index.name = "ward_id"
    out["raw_ratio"] = out["reported"] / out["expected"].replace(0, np.nan)
    # two-sided Poisson test: is the season's count really different from expected?
    lo = poisson.cdf(out["reported"], out["expected"].clip(lower=1e-9))
    hi = poisson.sf(out["reported"] - 1, out["expected"].clip(lower=1e-9))
    out["p_value"] = np.minimum(1.0, 2 * np.minimum(lo, hi))
    shrunk = ((out["reported"] + k) / (out["expected"] + k)).clip(bounds["min"], bounds["max"]).round(2)
    out["current_h_m"] = current.reindex(out.index).fillna(bounds["default"]).round(2)
    out["evidence"] = np.where(out["p_value"] < fb["recalibration_p"], "significant", "not significant")
    out["proposed_h_m"] = np.where(out["evidence"] == "significant", shrunk, out["current_h_m"])
    out["change"] = (out["proposed_h_m"] - out["current_h_m"]).round(2)
    return out.reset_index().round({"expected": 1, "raw_ratio": 2})


def synthetic_reports(scores: pd.DataFrame, total: int, seed: int = 7,
                      anomaly: dict | None = None) -> pd.DataFrame:
    """Plausible SYNTHETIC counts for demos. Days get cases in proportion to city risk
    (population × exp((MRI − 60)/10), so a heatwave dominates); within a day, wards share
    them by population × MRI, the same rule the anomaly flag uses. Counts are Poisson draws.
    `anomaly` = {"ward_id", "dates", "extra"} injects a cluster so the flag can be demonstrated."""
    rng = np.random.default_rng(seed)
    s = scores.copy()
    day_w = (s["population"] * np.exp((s["mri"] - 60) / 10)).groupby(s["date"]).sum()
    day_total = total * day_w / day_w.sum()
    share = s["population"] * s["mri"].clip(lower=0)
    share = share / share.groupby(s["date"]).transform("sum")
    s["reports"] = rng.poisson(s["date"].map(day_total) * share)
    if anomaly:
        hit = s["ward_id"].eq(anomaly["ward_id"]) & s["date"].isin(anomaly["dates"])
        s.loc[hit, "reports"] += anomaly["extra"]
    return s.loc[s["reports"] > 0, ["ward_id", "date", "reports"]].reset_index(drop=True)
