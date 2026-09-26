import numpy as np
import pandas as pd
import pytest

from heatrisk.config import load_config
from synth import synthetic_weather


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture
def wx():
    return synthetic_weather()


@pytest.fixture
def wards():
    """Five-ward toy city with known vulnerability contrasts."""
    return pd.DataFrame({
        "ward_id": [f"W{i}" for i in range(1, 6)],
        "centroid_lat": 23.02, "centroid_lon": 72.57,
        "elderly_share": [0.093, 0.0931, 0.0932, 0.0931, 0.093],   # flat, like WorldPop
        "outdoor_worker_share": [0.10, 0.20, 0.30, 0.40, 0.50],
        "health_walk_km": [0.2, 0.5, 1.0, 2.0, 3.0],
        "cooling_gap": [0.05, 0.1, 0.2, 0.4, 0.6],
        "informal_housing_share": [np.nan] * 5,
        "under5_share": [0.08, 0.09, 0.10, 0.11, 0.12],
        "population_density": [5000, 10000, 20000, 30000, 40000],
        "roof_sheet_share": [0.0, 0.1, 0.2, 0.4, 0.6],
        "historical_factor": [1.0, 1.0, 1.0, 1.1, np.nan],
        "capacity_factor": [np.nan] * 5,
    })
