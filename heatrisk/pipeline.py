"""End-to-end scoring for one ward: weather → thermal → HTSI → PVI → MRI/HRI → explanation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from heatrisk import downscale as ds
from heatrisk import explain, indices, risk, thermal, vulnerability
from heatrisk.config import ROOT

WARDS_PARQUET = ROOT / "data" / "processed" / "wards.parquet"


def load_wards(path: str | Path = WARDS_PARQUET) -> pd.DataFrame:
    return pd.read_parquet(path)


def score_ward(ward_id: str, wx: pd.DataFrame, wards: pd.DataFrame, cfg: dict,
               downscale: bool = True) -> dict:
    """Score one ward for every full day in `wx` (grid weather).

    Returns {"daily": DataFrame, "hourly": DataFrame, "pvi": dict, "pvi_status": dict,
             "downscaling": dict, "explanations": {date: {"mri": ..., "hri": ...}}}.
    With `downscale`, `wx` is first adjusted to the ward (§6.1) and tree shade
    applied to MRT; pass False to score the raw grid weather.
    """
    ward = wards.set_index("ward_id").loc[ward_id]
    pvi_table, pvi_status = vulnerability.compute_pvi(wards, cfg)
    pvi_row = pvi_table.set_index("ward_id").loc[ward_id].to_dict()

    if downscale:
        wx = ds.downscale(wx, ward_id, wards, cfg)
        tree_cover = ward.get("tree_cover", 0.0)
    else:
        tree_cover = 0.0
    hourly = thermal.compute(wx, ward["centroid_lat"], ward["centroid_lon"], cfg, tree_cover)
    daily = indices.htsi(indices.daily_indicators(hourly, cfg), cfg, ward.get("roof_sheet_share"))

    h_m, h_default = risk.factor_or_default(ward.get("historical_factor"), cfg["risk"]["historical_factor"])
    c_h, c_default = risk.factor_or_default(ward.get("capacity_factor"), cfg["risk"]["capacity_factor"])
    daily = daily.join(risk.score(daily["htsi"], pvi_row["pvi"], h_m, c_h, cfg))
    daily["pvi"] = pvi_row["pvi"]

    explanations = {}
    for date, row in daily.iterrows():
        r = row.to_dict()
        explanations[date] = {
            "mri": explain.explain_day(r, pvi_row, pvi_status, h_m, h_default, "mri", cfg),
            "hri": explain.explain_day(r, pvi_row, pvi_status, c_h, c_default, "hri", cfg),
        }
    return {"daily": daily, "hourly": hourly, "pvi": pvi_row, "pvi_status": pvi_status,
            "downscaling": wx.attrs.get("downscaling", {}), "explanations": explanations}
