import pandas as pd
import pytest

from heatrisk import forecast
from synth import synthetic_weather


def _daily(levels_by_day: dict[str, list[str]]) -> pd.DataFrame:
    """Toy ward-day table: {date: [alert level per ward]}."""
    mri = {"green": 30, "yellow": 50, "orange": 70, "red": 90}
    rows = [{"date": pd.Timestamp(d), "ward_id": f"W{i}", "alert_mri": lvl, "mri": mri[lvl]}
            for d, lvls in levels_by_day.items() for i, lvl in enumerate(lvls)]
    return pd.DataFrame(rows)


def test_event_needs_consecutive_days_and_enough_wards(cfg):
    d = _daily({
        "2024-05-10": ["orange", "orange", "green", "green"],   # one isolated hot day → no event
        "2024-05-11": ["green"] * 4,
        "2024-05-12": ["orange", "green", "green", "green"],     # 1 of 4 wards = 25% → counts
        "2024-05-13": ["red", "orange", "green", "green"],
        "2024-05-14": ["red", "red", "orange", "green"],
        "2024-05-15": ["green"] * 4,
    })
    ev = forecast.detect_events(d, cfg, n_wards=4)
    assert len(ev) == 1
    e = ev[0]
    assert (e["start"], e["peak"], e["end"], e["days"]) == ("2024-05-12", "2024-05-14", "2024-05-14", 3)
    assert e["wards_affected"] == ["W0", "W1", "W2"] and not e["open_ended"]


def test_event_running_off_the_end_is_open_ended(cfg):
    d = _daily({"2024-05-20": ["orange"] * 4, "2024-05-21": ["red"] * 4})
    assert forecast.detect_events(d, cfg, n_wards=4)[0]["open_ended"]


def test_run_wards_and_peaks(cfg, wards):
    wx = synthetic_weather(days=4, tmax=44)
    daily, hourly = forecast.run_wards(wx, wards, cfg)
    assert len(daily) == 4 * len(wards) and daily["top_factors"].str.len().gt(0).all()
    peaks = forecast.ward_peaks(daily, hourly, issue_date="2024-05-21")
    assert len(peaks) == len(wards)
    assert (pd.to_datetime(peaks["peak_day"]) >= pd.Timestamp("2024-05-21")).all()
    # synthetic temperature peaks at 15:00 and radiation around midday, so UTCI peaks in the early afternoon
    assert peaks["peak_hour"].str.match(r"1[1-5]:00–1[2-6]:00").all()
