"""Weather input.

Every source (Open-Meteo forecast, ERA5 / historical archive, ensemble members)
is converted to one hourly "WeatherFrame" so the rest of the pipeline never
depends on where the data came from:

  index     hourly timestamps, tz-aware (Asia/Kolkata), marking the END of each hour
  t2m       air temperature at 2 m, °C
  rh        relative humidity, %
  td        dew point, °C
  wind10    wind speed at 10 m, m/s
  pressure  surface pressure, hPa
  ghi       global horizontal irradiance, W/m² (mean over the preceding hour)
  dni       direct normal irradiance, W/m²
  dhi       diffuse horizontal irradiance, W/m²
  cloud     cloud cover, 0–1
"""

from __future__ import annotations

import pandas as pd
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

COLUMNS = ["t2m", "rh", "td", "wind10", "pressure", "ghi", "dni", "dhi", "cloud"]

_OPEN_METEO_VARS = {
    "temperature_2m": "t2m",
    "relative_humidity_2m": "rh",
    "dew_point_2m": "td",
    "wind_speed_10m": "wind10",
    "surface_pressure": "pressure",
    "shortwave_radiation": "ghi",
    "direct_normal_irradiance": "dni",
    "diffuse_radiation": "dhi",
    "cloud_cover": "cloud",
}


def _to_frame(payload: dict, tz: str) -> pd.DataFrame:
    hourly = payload["hourly"]
    df = pd.DataFrame({new: hourly[old] for old, new in _OPEN_METEO_VARS.items()})
    df.index = pd.DatetimeIndex(pd.to_datetime(hourly["time"]), name="time").tz_localize(tz)
    df["cloud"] = df["cloud"] / 100.0
    return validate(df)


def _request(url: str, lat: float, lon: float, tz: str, **extra) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_OPEN_METEO_VARS),
        "wind_speed_unit": "ms",
        "timezone": tz,
        **extra,
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_forecast(lat: float, lon: float, days: int = 5, past_days: int = 3,
                   tz: str = "Asia/Kolkata") -> pd.DataFrame:
    """Hourly Open-Meteo forecast, with a few past days so persistence can be counted."""
    return _to_frame(_request(FORECAST_URL, lat, lon, tz, forecast_days=days, past_days=past_days), tz)


def fetch_archive(lat: float, lon: float, start: str, end: str,
                  tz: str = "Asia/Kolkata") -> pd.DataFrame:
    """Hourly reanalysis-based history (Open-Meteo archive, ERA5 family) for backtests."""
    return _to_frame(_request(ARCHIVE_URL, lat, lon, tz, start_date=start, end_date=end), tz)


def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"WeatherFrame missing columns: {sorted(missing)}")
    if df.index.tz is None:
        raise ValueError("WeatherFrame index must be timezone-aware")
    df = df[COLUMNS].astype(float)
    # Radiation can be missing at night in some sources; zero is correct there
    df[["ghi", "dni", "dhi"]] = df[["ghi", "dni", "dhi"]].fillna(0.0).clip(lower=0.0)
    return df
