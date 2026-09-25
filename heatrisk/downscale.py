"""Ward-level downscaling of grid weather (proposal §6.1).

Grid weather (Open-Meteo, ERA5) is coarser than a ward, so every ward in the
city receives nearly the same air temperature. The adjustment adds a fraction β
of the ward's satellite land-surface-temperature anomaly:

  T_ward = T_grid + β × (LST_ward − LST_city)

applied separately by day (Landsat daytime LST) and night (MODIS night LST),
because in Ahmedabad the two anomalies have different causes: night LST tracks
built-up share (r = +0.90) while daytime LST peaks in the bare-soil fringe.
Dew point is held fixed (the same air mass), so relative humidity is recomputed.

Tree shade on mean radiant temperature is handled in thermal.compute via the
ward's tree_cover.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from heatrisk.thermal import vapour_pressure_hpa
from heatrisk.weather import validate


def lst_anomalies(wards: pd.DataFrame) -> pd.DataFrame:
    """Each ward's day and night LST minus the city mean (°C); NaN where LST is missing."""
    out = pd.DataFrame({"ward_id": wards["ward_id"]})
    for period in ("day", "night"):
        col = f"lst_{period}"
        lst = wards[col] if col in wards else pd.Series(np.nan, index=wards.index)
        out[f"lst_{period}_anom"] = lst - lst.mean()
    return out


def temperature_offsets(ward_id: str, wards: pd.DataFrame, cfg: dict) -> dict:
    """Air-temperature offsets (°C) for one ward: {"day": ..., "night": ..., "missing": [...]}."""
    ds = cfg["downscaling"]
    anom = lst_anomalies(wards).set_index("ward_id").loc[ward_id]
    out, missing = {}, []
    for period in ("day", "night"):
        a = anom[f"lst_{period}_anom"]
        if pd.isna(a):
            missing.append(f"lst_{period}")
            a = 0.0
        out[period] = float(ds[f"beta_{period}"] * a)
    out["missing"] = missing
    return out


def relative_humidity(t_c, td_c) -> np.ndarray:
    """RH (%) from temperature and dew point, capped at 100."""
    return np.minimum(100 * vapour_pressure_hpa(td_c) / vapour_pressure_hpa(t_c), 100.0)


def downscale(wx: pd.DataFrame, ward_id: str, wards: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Ward-adjusted copy of a WeatherFrame. Offsets are stored in `attrs["downscaling"]`.

    Night hours take the night offset. After sunrise the offset moves linearly to
    the daytime one as GHI rises to `day_transition_wm2`, since the nocturnal heat
    island fades as the sun heats surfaces — and the daily minimum, which falls
    around sunrise, keeps its night-time adjustment.
    """
    off = temperature_offsets(ward_id, wards, cfg)
    w_day = np.clip(wx["ghi"].to_numpy() / cfg["downscaling"]["day_transition_wm2"], 0, 1)
    delta = off["night"] + (off["day"] - off["night"]) * w_day
    out = wx.copy()
    out["t2m"] = wx["t2m"] + delta
    out["td"] = np.minimum(wx["td"], out["t2m"])
    out["rh"] = relative_humidity(out["t2m"], out["td"])
    out = validate(out)
    out.attrs["downscaling"] = off
    return out
