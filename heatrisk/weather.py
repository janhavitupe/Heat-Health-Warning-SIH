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
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"

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




def fetch_previous_runs(lat: float, lon: float, start: str, end: str, model: str, lead_days: int,
                        tz: str = "Asia/Kolkata") -> pd.DataFrame:
    """What an archived forecast issued `lead_days` earlier said for each hour (Open-Meteo Previous Runs API).

    Used to measure forecast skill by lead time over past events (Phase 4 reliability check).
    """
    suffix = f"_previous_day{lead_days}"
    params = {"latitude": lat, "longitude": lon, "hourly": ",".join(v + suffix for v in _OPEN_METEO_VARS),
              "models": model, "start_date": start, "end_date": end, "wind_speed_unit": "ms", "timezone": tz}
    r = requests.get(PREVIOUS_RUNS_URL, params=params, timeout=90)
    r.raise_for_status()
    payload = r.json()
    payload["hourly"] = {k.removesuffix(suffix): v for k, v in payload["hourly"].items()}
    return _to_frame(payload, tz)

def split_members(payload: dict, model: str, tz: str) -> dict[str, pd.DataFrame]:
    """Split an Open-Meteo ensemble response into one WeatherFrame per member.

    The control run's variables have plain names ("temperature_2m"); perturbed
    members carry a suffix ("temperature_2m_member01"). Hours before the run starts
    or after it ends are empty and are trimmed; a member with gaps inside that span
    is dropped rather than gap-filled.
    """
    hourly = payload["hourly"]
    suffixes = [""] + sorted({k.split("_member", 1)[1] for k in hourly if "_member" in k})
    frames = {}
    for suf in suffixes:
        key = f"{model}_m{suf or '00'}"
        cols = {new: hourly.get(old + (f"_member{suf}" if suf else "")) for old, new in _OPEN_METEO_VARS.items()}
        if any(v is None for v in cols.values()):
            continue
        df = pd.DataFrame(cols)
        df.index = pd.DatetimeIndex(pd.to_datetime(hourly["time"]), name="time").tz_localize(tz)
        required = ["t2m", "rh", "td", "wind10", "pressure", "cloud"]
        complete = df[required].notna().all(axis=1)
        if not complete.any():
            continue
        df = df.loc[complete.idxmax():complete[::-1].idxmax()]      # trim empty leading/trailing hours
        if df[required].isna().any().any():
            continue
        df["cloud"] = df["cloud"] / 100.0
        frames[key] = validate(df)
    return frames


def fetch_ensemble(lat: float, lon: float, models: list[str], days: int = 5, past_days: int = 4,
                   tz: str = "Asia/Kolkata") -> dict[str, pd.DataFrame]:
    """Hourly Open-Meteo ensemble forecast: {"<model>_m<NN>": WeatherFrame} for every member.

    `past_days` prepends recent days so persistence can be counted in every member (the
    first is partial, because the run starts at 00 UTC = 05:30 IST, and is dropped later).
    """
    members = {}
    for model in models:
        payload = _request(ENSEMBLE_URL, lat, lon, tz, models=model, forecast_days=days, past_days=past_days)
        members.update(split_members(payload, model, tz))
    return members


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
