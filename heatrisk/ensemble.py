"""Probabilistic alerts from ensemble forecasts — proposal §6.9 (Innovation 2).

The full pipeline (downscaling → thermal → HTSI → PVI → MRI/HRI) runs once per
ensemble member and ward. For each ward and day:

  P(alert ≥ level) = share of members whose MRI reaches that level

With `ensemble.weighting: model` (the tested default) each model's members share an
equal part of the probability; with `member` every run counts once ("83 of 122 runs"). The
most likely level is the level with the largest share, and its share sets the
confidence label (config `ensemble.confidence`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from heatrisk import vulnerability
from heatrisk.indices import category
from heatrisk.pipeline import score_ward

LEVELS = ["green", "yellow", "orange", "red"]


def model_of(member: str) -> str:
    """"ecmwf_ifs025_m07" → "ecmwf_ifs025"."""
    return member.rsplit("_m", 1)[0]


def score_members(members: dict[str, pd.DataFrame], wards: pd.DataFrame, cfg: dict,
                  target: str = "mri") -> pd.DataFrame:
    """Score every member for every ward: long table (member, model, ward_id, date, htsi, <target>, level)."""
    pvi = vulnerability.compute_pvi(wards, cfg)
    bands = cfg["alerts"]["levels"]
    frames = []
    for member, wx in members.items():
        for ward_id in wards["ward_id"]:
            d = score_ward(ward_id, wx, wards, cfg, pvi=pvi, explain_scores=False)["daily"]
            frames.append(pd.DataFrame({
                "member": member, "model": model_of(member), "ward_id": ward_id, "date": d.index,
                "htsi": d["htsi"].to_numpy(), target: d[target].to_numpy(),
            }))
    out = pd.concat(frames, ignore_index=True)
    out["level"] = [category(v, bands) for v in out[target]]
    return out


def member_weights(scores: pd.DataFrame, how: str) -> pd.Series:
    """Weight per row so each (ward, date) sums to 1: equal per member, or equal per model."""
    if how == "member":
        n = scores.groupby(["ward_id", "date"])["member"].transform("nunique")
        return 1.0 / n
    if how == "model":
        per_model = scores.groupby(["ward_id", "date", "model"])["member"].transform("nunique")
        n_models = scores.groupby(["ward_id", "date"])["model"].transform("nunique")
        return 1.0 / (per_model * n_models)
    raise ValueError(f"unknown ensemble.weighting: {how}")


def probabilities(scores: pd.DataFrame, cfg: dict, target: str = "mri") -> pd.DataFrame:
    """Per ward and day: p_yellow/p_orange/p_red (P(level or worse)), most likely level, confidence,
    member count, and the 10th/50th/90th percentile of the score across members."""
    ens = cfg["ensemble"]
    w = member_weights(scores, ens.get("weighting", "model"))
    rank = scores["level"].map(LEVELS.index).to_numpy()
    df = scores[["ward_id", "date"]].copy()
    for k, lvl in enumerate(LEVELS):
        df[f"is_{lvl}"] = (rank == k) * w.to_numpy()
    g = df.groupby(["ward_id", "date"])
    exact = g[[f"is_{lvl}" for lvl in LEVELS]].sum()
    exact.columns = LEVELS
    out = pd.DataFrame(index=exact.index)
    out["p_yellow"] = exact[["yellow", "orange", "red"]].sum(axis=1)
    out["p_orange"] = exact[["orange", "red"]].sum(axis=1)
    out["p_red"] = exact["red"]
    out["most_likely"] = exact.idxmax(axis=1)
    out["p_most_likely"] = exact.max(axis=1)
    conf = ens["confidence"]
    out["confidence"] = np.select([out["p_most_likely"] >= conf["high"], out["p_most_likely"] >= conf["medium"]],
                                  ["high", "medium"], "low")
    key = ["ward_id", "date"]
    out["n_members"] = scores.groupby(key)["member"].nunique()
    stats = scores.groupby(key)[target].quantile([0.1, 0.5, 0.9]).unstack()
    out[[f"{target}_p10", f"{target}_median", f"{target}_p90"]] = stats.to_numpy()
    return out.reset_index()


def triggers(probs: pd.DataFrame, cfg: dict, issue_date) -> pd.DataFrame:
    """Evaluate probability trigger rules (config `ensemble.triggers`) for days after `issue_date`.

    A rule {when: p_red, at_least: 0.40, lead_days_max: 3, action: ...} fires for every
    ward-day with lead time 1..lead_days_max whose probability meets the threshold.
    """
    issue = pd.Timestamp(issue_date).normalize()
    lead = (pd.to_datetime(probs["date"]) - issue).dt.days
    rows = []
    for rule in cfg["ensemble"].get("triggers", []):
        hit = probs[(lead >= 1) & (lead <= rule["lead_days_max"]) & (probs[rule["when"]] >= rule["at_least"])]
        for r in hit.itertuples():
            rows.append({"ward_id": r.ward_id, "date": r.date, "lead_days": int((pd.Timestamp(r.date) - issue).days),
                         "rule": f"{rule['when']} >= {rule['at_least']:.0%} within {rule['lead_days_max']} days",
                         "probability": getattr(r, rule["when"]), "action": rule["action"]})
    return pd.DataFrame(rows, columns=["ward_id", "date", "lead_days", "rule", "probability", "action"])
