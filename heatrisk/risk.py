"""Mortality and Hospitalization Risk Indices — proposal §6.5–6.6.

MRI = min(100, HTSI × (floor + (1 − floor) × PVI/100) × H_m)
HRI = min(100, HTSI × (floor + (1 − floor) × PVI/100) × C_h)
"""

from __future__ import annotations

import pandas as pd

from heatrisk.indices import category


def factor_or_default(value, bounds: dict) -> tuple[float, bool]:
    """Clamp a ward factor to its configured bounds; use the default when missing."""
    if value is None or pd.isna(value):
        return float(bounds["default"]), True
    return float(min(max(float(value), bounds["min"]), bounds["max"])), False


def vulnerability_multiplier(pvi: float, cfg: dict) -> float:
    floor = cfg["risk"]["vulnerability_floor"]
    return floor + (1 - floor) * pvi / 100.0


def score(htsi: pd.Series, pvi: float, h_m: float, c_h: float, cfg: dict) -> pd.DataFrame:
    mult = vulnerability_multiplier(pvi, cfg)
    bands = cfg["alerts"]["levels"]
    out = pd.DataFrame(index=htsi.index)
    out["mri_raw"] = htsi * mult * h_m
    out["hri_raw"] = htsi * mult * c_h
    out["mri"] = out["mri_raw"].clip(upper=100.0)
    out["hri"] = out["hri_raw"].clip(upper=100.0)
    out["alert_mri"] = [category(v, bands) for v in out["mri"]]
    out["alert_hri"] = [category(v, bands) for v in out["hri"]]
    return out
