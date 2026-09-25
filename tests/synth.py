"""Deterministic synthetic weather for tests (no network)."""

import numpy as np
import pandas as pd


def synthetic_weather(days: int = 3, tmax: float = 44.0, tmin: float = 30.0, rh_min: float = 15.0,
                      rh_max: float = 45.0, start: str = "2024-05-20") -> pd.DataFrame:
    """Deterministic pre-monsoon Ahmedabad-like hourly weather (no network)."""
    idx = pd.date_range(start, periods=24 * days, freq="h", tz="Asia/Kolkata")
    hour = idx.hour.to_numpy()
    # temperature peaks at 15:00, minimum at 05:00
    phase = np.cos((hour - 15) / 24 * 2 * np.pi)
    t = tmin + (tmax - tmin) * (phase + 1) / 2
    rh = rh_max - (rh_max - rh_min) * (phase + 1) / 2
    sun = np.clip(np.sin((hour - 6) / 13 * np.pi), 0, None)
    ghi = 950 * sun
    df = pd.DataFrame({
        "t2m": t, "rh": rh, "wind10": 4.0, "pressure": 1000.0,
        "ghi": ghi, "dni": 780 * sun, "dhi": 140 * sun, "cloud": 0.05,
    }, index=idx)
    # dew point from T and RH (Magnus)
    a, b = 17.62, 243.12
    gamma = np.log(df.rh / 100) + a * df.t2m / (b + df.t2m)
    df["td"] = b * gamma / (a - gamma)
    return df
