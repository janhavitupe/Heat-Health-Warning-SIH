"""Derive HTSI normalization thresholds from the local climatology (Phase 3).

Each thermal indicator is scaled so that a day as rare as a given Tmax scores a
given HTSI point. Anchors come from the Ahmedabad Heat Action Plan (2019) colour
signals: Tmax ≤ 41 °C is "no alert" (so the top of that band scores 40, the edge
of High) and Tmax ≥ 45 °C is Red "extreme heat" (scores 80, the edge of Extreme).
The 43 °C Yellow/Orange boundary is printed as a check on linearity (target 60).

Reads data/processed/climatology_daily.parquet (scripts/build_climatology.py) and
prints the zero/full values to copy into config.yaml → thermal_stress.normalization.
Usage:  python scripts/calibrate_htsi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from heatrisk import indices, load_config  # noqa: E402
from heatrisk.config import ROOT  # noqa: E402

CLIMATOLOGY = ROOT / "data" / "processed" / "climatology_daily.parquet"
LOW = (41.0, 40)     # (Tmax °C, HTSI points)
HIGH = (45.0, 80)
CHECK = (43.0, 60)


def thresholds(clim: pd.DataFrame, ind: str) -> tuple[float, float]:
    """(zero, full) so the indicator's value at the LOW/HIGH Tmax percentiles maps to their points."""
    (t_lo, p_lo), (t_hi, p_hi) = LOW, HIGH
    v_lo = clim[ind].quantile((clim["tmax"] <= t_lo).mean())
    v_hi = clim[ind].quantile((clim["tmax"] <= t_hi).mean())
    slope = (p_hi - p_lo) / (v_hi - v_lo)          # points per °C
    zero = v_lo - p_lo / slope
    return zero, zero + 100 / slope


def main() -> None:
    cfg = load_config()
    clim = pd.read_parquet(CLIMATOLOGY)
    years = f"{clim.index.min().year}–{clim.index.max().year}"
    print(f"Climatology: {len(clim)} days, {years}")
    for t, _ in (LOW, CHECK, HIGH):
        print(f"  Tmax {t} °C is the {100 * (clim['tmax'] <= t).mean():.2f}th percentile")

    print("\nnormalization:")
    for ind in indices.INDICATORS:
        zero, full = thresholds(clim, ind)
        v_check = clim[ind].quantile((clim["tmax"] <= CHECK[0]).mean())
        check = (v_check - zero) / (full - zero) * 100
        now = cfg["thermal_stress"]["normalization"][ind]
        print(f"  {ind}: {{zero: {zero:.1f}, full: {full:.1f}}}   "
              f"(config {now['zero']}–{now['full']}; {CHECK[0]:.0f} °C-equivalent scores {check:.0f}, target {CHECK[1]})")

    cats = indices.htsi(clim, cfg, None)["htsi_category"].value_counts(normalize=True) * 100
    print("\nHTSI categories over the climatology with the current config:")
    for name in cfg["htsi"]["categories"]:
        print(f"  {name:10s} {cats.get(name, 0):5.1f}%")


if __name__ == "__main__":
    main()
