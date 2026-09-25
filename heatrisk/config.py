"""Load and validate config.yaml.

All model weights and thresholds are read from one file so they can be
disclosed and changed without touching code (proposal §6.8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


class ConfigError(ValueError):
    pass


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    validate(cfg)
    return cfg


def _check_weights(name: str, weights: dict[str, float]) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ConfigError(f"{name} weights sum to {total}, expected 1.0")
    if any(w < 0 for w in weights.values()):
        raise ConfigError(f"{name} weights must be non-negative")


def _check_increasing_bands(name: str, bands: dict[str, float]) -> None:
    values = list(bands.values())
    if values != sorted(values) or len(set(values)) != len(values):
        raise ConfigError(f"{name} bands must be strictly increasing: {bands}")
    if values[-1] != 100:
        raise ConfigError(f"{name} bands must end at 100")


def validate(cfg: dict[str, Any]) -> None:
    ts = cfg["thermal_stress"]
    _check_weights("thermal_stress", ts["weights"])
    if set(ts["weights"]) != set(ts["normalization"]):
        raise ConfigError("thermal_stress weights and normalization must cover the same indicators")
    for ind, n in ts["normalization"].items():
        if n["full"] <= n["zero"]:
            raise ConfigError(f"normalization for {ind}: full must exceed zero")

    ds = cfg["downscaling"]
    for key in ("beta_day", "beta_night", "tree_cover_mrt_reduction"):
        if not 0 <= ds[key] <= 1:
            raise ConfigError(f"downscaling.{key} must be in [0, 1]")
    if ds["day_transition_wm2"] <= 0:
        raise ConfigError("downscaling.day_transition_wm2 must be positive")

    _check_weights("pvi", cfg["pvi"]["weights"])
    if cfg["pvi"].get("normalization", "percentile_rank") not in ("percentile_rank", "minmax"):
        raise ConfigError("pvi.normalization must be 'percentile_rank' or 'minmax'")
    _check_increasing_bands("htsi.categories", cfg["htsi"]["categories"])
    _check_increasing_bands("alerts.levels", cfg["alerts"]["levels"])

    spread = cfg["risk"]["vulnerability_spread"]
    if not 0 <= spread < 1:
        raise ConfigError("risk.vulnerability_spread must be in [0, 1)")
    cap = cfg["risk"]["capacity"]
    if cap["catchment_km"] <= 0 or not 0 <= cap["spread"] < 1:
        raise ConfigError("risk.capacity: catchment_km must be positive and spread in [0, 1)")
    for key in ("historical_factor", "capacity_factor"):
        f = cfg["risk"][key]
        if not f["min"] <= f["default"] <= f["max"]:
            raise ConfigError(f"risk.{key}: default must lie between min and max")

    if cfg["ensemble"].get("weighting", "model") not in ("member", "model"):
        raise ConfigError("ensemble.weighting must be 'member' or 'model'")
    fc = cfg["forecast"]
    if not 0 < fc["event_min_share"] <= 1 or fc["event_min_days"] < 1:
        raise ConfigError("forecast.event_min_share must be in (0, 1] and event_min_days >= 1")
    conf = cfg["ensemble"]["confidence"]
    if not 0 < conf["medium"] < conf["high"] < 1:
        raise ConfigError("ensemble.confidence must satisfy 0 < medium < high < 1")

    ww = cfg["work_windows"]
    n = len(ww["work_fractions"])
    for regime in ("acclimatized", "unacclimatized"):
        for load in ww["workloads"]:
            row = ww[regime][load]
            if len(row) != n:
                raise ConfigError(f"work_windows.{regime}.{load} needs {n} values")
            vals = [v for v in row if v is not None]
            if vals != sorted(vals):
                raise ConfigError(
                    f"work_windows.{regime}.{load}: less work time must allow equal or higher WBGT"
                )
