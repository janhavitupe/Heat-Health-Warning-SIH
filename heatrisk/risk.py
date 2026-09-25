"""Mortality and Hospitalization Risk Indices — proposal §6.5–6.6.

MRI = min(100, HTSI × (1 + spread × (PVI − 50)/50) × H_m)
HRI = min(100, HTSI × (1 + spread × (PVI − 50)/50) × C_h)

A ward of average vulnerability (PVI 50) carries the heat level unchanged, so a
city-wide extreme heat day can reach Red; vulnerability moves wards up or down.
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
    spread = cfg["risk"]["vulnerability_spread"]
    return 1.0 + spread * (pvi - 50.0) / 50.0


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
