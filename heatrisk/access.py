"""Spatial access to facilities — enhanced two-step floating catchment area (E2SFCA).

Luo & Qi (2009), Health & Place 15:1100–1107, with the continuous Gaussian
distance decay commonly used since:

  G(d) = (exp(-½(d/d0)²) − exp(-½)) / (1 − exp(-½))   for d ≤ d0, else 0

  step 1  each facility j:  R_j = capacity_j / Σ_k P_k · G(d_kj)   (capacity per person it serves)
  step 2  each ward i:      A_i = Σ_j R_j · G(d_ij)                 (capacity per person reachable)

Used for the hospital capacity factor C_h (proposal §6.5) and, in Phase 6, for
cooling-point access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def gaussian_decay(d_km: np.ndarray, d0_km: float) -> np.ndarray:
    d = np.asarray(d_km, dtype=float)
    g = (np.exp(-0.5 * (d / d0_km) ** 2) - np.exp(-0.5)) / (1 - np.exp(-0.5))
    return np.where(d <= d0_km, g, 0.0)


def e2sfca(demand_xy: np.ndarray, population: np.ndarray, supply_xy: np.ndarray,
           capacity: np.ndarray, d0_km: float) -> np.ndarray:
    """Accessibility (capacity per person) for each demand point. Coordinates in metres."""
    d = np.linalg.norm(demand_xy[:, None, :] - supply_xy[None, :, :], axis=2) / 1000.0   # (wards, facilities)
    g = gaussian_decay(d, d0_km)
    served = (population[:, None] * g).sum(axis=0)
    ratio = np.divide(capacity, served, out=np.zeros_like(capacity, dtype=float), where=served > 0)
    return (g * ratio[None, :]).sum(axis=1)


def capacity_factor(access: pd.Series, bounds: dict, spread: float) -> pd.Series:
    """Map accessibility to C_h: the ward with the least access gets 1 + spread, the most 1 − spread.

    Percentile rank (like PVI), so the median ward gets 1.0; clamped to the configured bounds.
    """
    shortage = (access.rank(ascending=False, method="average") - 1) / (len(access) - 1)   # 1 = least access
    return (1 + spread * (2 * shortage - 1)).clip(bounds["min"], bounds["max"])
