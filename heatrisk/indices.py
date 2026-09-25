"""Human Thermal Stress Index (HTSI, 0–100) — proposal §6.3.

HTSI = min(100, [Σ wᵢ · normᵢ] + P_night + P_persist + P_indoor)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

INDICATORS = ("utci", "wbgt", "heat_index")


def normalize(value, zero: float, full: float):
    """Linear map: `zero` → 0, `full` → 100, clamped to [0, 100]."""
    return np.clip((np.asarray(value, dtype=float) - zero) / (full - zero) * 100.0, 0.0, 100.0)


def category(score: float, bands: dict[str, float]) -> str:
    for name, upper in bands.items():
        if score <= upper:
            return name
    return list(bands)[-1]


def daily_indicators(hourly: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Aggregate hourly thermal output to one row per local calendar day."""
    how = cfg["thermal_stress"]["daily_aggregation"]
    if how != "max_3h_mean":
        raise ValueError(f"unsupported daily_aggregation: {how}")
    dates = hourly.index.date
    g = hourly.groupby(dates)
    # mean of the 3 hottest hours per day (vectorized: rank within each day)
    daily = pd.DataFrame({
        ind: hourly[ind].where(g[ind].rank(ascending=False, method="first") <= 3).groupby(dates).mean()
        for ind in INDICATORS
    })
    daily["tmax"] = g["t2m"].max()
    daily["tmin"] = g["t2m"].min()
    daily["hours"] = g.size()
    daily.index = pd.to_datetime(daily.index).rename("date")
    # A partial first/last day would understate the daily peak or minimum
    return daily[daily["hours"] >= 20]


def htsi(daily: pd.DataFrame, cfg: dict, roof_sheet_share: float | None) -> pd.DataFrame:
    """Add normalized indicators, modifiers, HTSI and its category to daily rows.

    `roof_sheet_share` may be None/NaN when housing data is unavailable; P_indoor
    is then 0 and `indoor_data_missing` is set so the explanation can say so.
    """
    ts, h = cfg["thermal_stress"], cfg["htsi"]
    out = daily.copy()

    for ind in INDICATORS:
        n = ts["normalization"][ind]
        out[f"{ind}_n"] = normalize(out[ind], n["zero"], n["full"])
        out[f"pts_{ind}"] = ts["weights"][ind] * out[f"{ind}_n"]
    out["base"] = out[[f"pts_{i}" for i in INDICATORS]].sum(axis=1)

    night = h["night"]
    frac = (out["tmin"] - night["tmin_threshold_c"]) / (night["tmin_full_c"] - night["tmin_threshold_c"])
    out["pts_night"] = np.where(out["tmin"] >= night["tmin_threshold_c"],
                                np.clip(frac, 0, 1) * night["max_points"], 0.0)

    # Consecutive days at or above High, counted up to and including each day;
    # the first hot day earns no persistence points.
    per = h["persistence"]
    hot = (out["base"] >= per["min_base_score"]).astype(int)
    run = hot.groupby((hot == 0).cumsum()).cumsum()
    out["hot_run_days"] = run
    out["pts_persist"] = np.minimum((run - 1).clip(lower=0) * per["points_per_day"], per["max_points"])

    ind = h["indoor"]
    missing = roof_sheet_share is None or pd.isna(roof_sheet_share)
    share = 0.0 if missing else float(roof_sheet_share)
    indoor = ind["max_points"] * share * np.where(out["pts_night"] > 0, ind["night_multiplier"], 1.0)
    out["pts_indoor"] = np.where(out["base"] >= ind["min_base_score"],
                                 np.minimum(indoor, ind["max_points"]), 0.0)
    out["indoor_data_missing"] = missing

    raw = out["base"] + out["pts_night"] + out["pts_persist"] + out["pts_indoor"]
    out["htsi_raw"] = raw
    out["htsi"] = np.minimum(raw, 100.0)
    out["htsi_category"] = [category(v, h["categories"]) for v in out["htsi"]]
    return out
