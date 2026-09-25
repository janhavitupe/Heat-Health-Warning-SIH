"""End-to-end scoring: weather → downscaling → thermal → HTSI → PVI → MRI/HRI → explanation.

score_ward() scores one ward in full detail; score_city() scores every ward and
returns the tidy long table that the backtest and the API use.
"""

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
               downscale: bool = True, pvi: tuple[pd.DataFrame, dict] | None = None) -> dict:
    """Score one ward for every full day in `wx` (grid weather).

    Returns {"daily": DataFrame, "hourly": DataFrame, "pvi": dict, "pvi_status": dict,
             "downscaling": dict, "explanations": {date: {"mri": ..., "hri": ...}}}.
    With `downscale`, `wx` is first adjusted to the ward (§6.1) and tree shade
    applied to MRT; pass False to score the raw grid weather. `pvi` is the result
    of vulnerability.compute_pvi(wards, cfg), passed in to avoid recomputing it.
    """
    ward = wards.set_index("ward_id").loc[ward_id]
    pvi_table, pvi_status = pvi if pvi is not None else vulnerability.compute_pvi(wards, cfg)
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


CITY_COLUMNS = ["ward_id", "date", "tmax", "tmin", "utci", "wbgt", "heat_index", "htsi", "htsi_category",
                "pvi", "mri", "alert_mri", "hri", "alert_hri", "top_factors"]


def score_city(wx: pd.DataFrame | dict[str, pd.DataFrame], wards: pd.DataFrame, cfg: dict,
               downscale: bool = True, top: int = 3) -> pd.DataFrame:
    """Score every ward; one row per ward-day (columns CITY_COLUMNS).

    `wx` is either one grid WeatherFrame shared by all wards (the grid is coarser
    than a ward, so this is the usual case) or a {ward_id: WeatherFrame} mapping.
    `top_factors` lists the largest MRI contributions, e.g.
    "Whole-body heat stress (UTCI) +48; Hot night — little overnight recovery +10; ...".
    """
    pvi = vulnerability.compute_pvi(wards, cfg)
    frames = []
    for ward_id in wards["ward_id"]:
        ward_wx = wx[ward_id] if isinstance(wx, dict) else wx
        res = score_ward(ward_id, ward_wx, wards, cfg, downscale=downscale, pvi=pvi)
        d = res["daily"].reset_index()
        d["ward_id"] = ward_id
        d["top_factors"] = [
            "; ".join(f"{c.label} {c.points:+.0f}" for c in res["explanations"][date]["mri"].ranked()[:top])
            for date in res["daily"].index
        ]
        frames.append(d[CITY_COLUMNS])
    return pd.concat(frames, ignore_index=True)
