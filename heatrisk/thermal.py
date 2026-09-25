"""Thermal stress indicators from a WeatherFrame (proposal §6.2).

UTCI  — thermofeel polynomial (Bröde et al., 2012)
WBGT  — thermofeel Liljegren et al. (2008) physical model
HI    — NWS Rothfusz regression with adjustments (thermofeel)
MRT   — simplified standing-person radiation model (see mean_radiant_temperature)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import thermofeel as tf

SIGMA = 5.670374419e-8  # Stefan–Boltzmann, W m⁻² K⁻⁴
K = 273.15


def cos_solar_zenith(index: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Cosine of the solar zenith angle (NOAA general solar position equations).

    Open-Meteo radiation is the mean over the preceding hour, so the sun position
    is evaluated at the middle of that hour.
    """
    t = (index - pd.Timedelta(minutes=30)).tz_convert("UTC")
    doy = t.dayofyear.to_numpy()
    hour = (t.hour + t.minute / 60).to_numpy()
    g = 2 * np.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                       - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    true_solar_min = hour * 60 + eqtime + 4 * lon
    ha = np.radians(true_solar_min / 4 - 180)
    phi = np.radians(lat)
    return np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(ha)


def vapour_pressure_hpa(td_c) -> np.ndarray:
    """Actual vapour pressure from dew point (Magnus formula), hPa."""
    td_c = np.asarray(td_c, dtype=float)
    return 6.112 * np.exp(17.62 * td_c / (243.12 + td_c))


def mean_radiant_temperature(wx: pd.DataFrame, cosz: np.ndarray, p: dict,
                             shade: float = 0.0) -> np.ndarray:
    """Outdoor MRT (°C) for a standing person.

    Absorbed radiation = shortwave (direct beam on the projected area, half the
    diffuse sky, half the ground-reflected) + longwave (half from the upper
    hemisphere — sky plus walls — and half from the ground). The body is then
    treated as a black body at equilibrium with that load.

    `shade` (0–1) is the share of the direct beam blocked, e.g. by tree canopy.
    """
    ta_k = wx["t2m"].to_numpy() + K
    ghi, dni, dhi = (wx[c].to_numpy() for c in ("ghi", "dni", "dhi"))
    sun_up = cosz > 0

    # Projected area factor of a standing person (Fanger / Jendritzky approximation)
    elev = np.degrees(np.arcsin(np.clip(cosz, 0, 1)))
    f_p = np.where(sun_up, 0.308 * np.cos(np.radians(elev * (1 - elev**2 / 48402))), 0.0)
    shortwave = p["shortwave_absorptivity"] * (
        f_p * (1 - shade) * np.where(sun_up, dni, 0.0) + 0.5 * dhi + 0.5 * p["ground_albedo"] * ghi
    )

    # Clear-sky emissivity (Brutsaert 1975) with cloud correction, capped at 1
    e = vapour_pressure_hpa(wx["td"])
    eps_sky = np.minimum(1.24 * (e / ta_k) ** (1 / 7) * (1 + 0.22 * wx["cloud"].to_numpy() ** 2), 1.0)
    l_sky = eps_sky * SIGMA * ta_k**4

    excess = np.where(ghi > 0, p["ground_excess_per_wm2"] * ghi, p["night_ground_excess_c"])
    l_ground = p["ground_emissivity"] * SIGMA * (ta_k + excess) ** 4
    svf = p["sky_view_factor"]
    l_upper = svf * l_sky + (1 - svf) * l_ground   # walls/buildings radiate like warm ground
    longwave = p["body_emissivity"] * (0.5 * l_upper + 0.5 * l_ground)

    return ((shortwave + longwave) / (p["body_emissivity"] * SIGMA)) ** 0.25 - K


def compute(wx: pd.DataFrame, lat: float, lon: float, cfg: dict,
            tree_cover: float = 0.0) -> pd.DataFrame:
    """Hourly MRT, UTCI, WBGT, and Heat Index (all °C) for one location.

    `tree_cover` (0–1, ward share under canopy) removes part of the direct beam
    from MRT; WBGT's globe model is left unshaded (Liljegren has no shade term).
    """
    ts = cfg["thermal_stress"]
    lim = ts["wind_limits"]
    cosz = cos_solar_zenith(wx.index, lat, lon)
    wind = wx["wind10"].clip(lim["min"], lim["max"]).to_numpy()
    t2_k = wx["t2m"].to_numpy() + K
    td_k = wx["td"].to_numpy() + K

    tree_cover = 0.0 if pd.isna(tree_cover) else float(np.clip(tree_cover, 0, 1))
    shade = tree_cover * cfg["downscaling"]["tree_cover_mrt_reduction"]
    mrt = mean_radiant_temperature(wx, cosz, ts["mrt"], shade)
    utci = tf.calculate_utci(t2_k=t2_k, va=wind, mrt=mrt + K, td_k=td_k) - K

    ghi = wx["ghi"].to_numpy()
    direct_horizontal = wx["dni"].to_numpy() * np.clip(cosz, 0, None)
    fdir = np.where(ghi > 0, np.clip(direct_horizontal / np.maximum(ghi, 1e-9), 0, 1), 0.0)
    wbgt = tf.calculate_wbgt_liljegren(
        t2_k=t2_k, rh=wx["rh"].to_numpy(), pressure=wx["pressure"].to_numpy(),
        va=wind, ssrd=ghi, fdir=fdir, cossza=np.clip(cosz, 0, 1),
    ) - K

    hi = tf.calculate_heat_index_adjusted(t2_k=t2_k, td_k=td_k) - K

    return pd.DataFrame(
        {"t2m": wx["t2m"], "mrt": mrt, "utci": utci, "wbgt": wbgt, "heat_index": hi, "cosz": cosz},
        index=wx.index,
    )
