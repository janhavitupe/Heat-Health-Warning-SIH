import pandas as pd
import pytest

from heatrisk import work_windows as ww


def test_hour_status_follows_acgih_limits(cfg):
    heavy = cfg["work_windows"]["acclimatized"]["heavy"]          # [None, 27.5, 29.0, 30.5]
    assert ww.hour_status(27.0, heavy) == "45/15"                 # no continuous heavy work at any WBGT
    assert ww.hour_status(29.0, heavy) == "30/30"                 # limit is inclusive
    assert ww.hour_status(30.0, heavy) == "15/45"
    assert ww.hour_status(31.0, heavy) == "not_advised"
    assert ww.hour_status(20.0, cfg["work_windows"]["acclimatized"]["light"]) == "continuous"


def _day(wbgt_by_hour):
    idx = pd.date_range("2024-05-23 01:00", periods=24, freq="h", tz="Asia/Kolkata")   # hour-ending stamps
    return pd.DataFrame({"wbgt": wbgt_by_hour}, index=idx)


def test_schedule_merges_hours_and_respects_working_hours(cfg):
    wbgt = [24.0] * 24
    for h in range(11, 16):                        # hours ending 12:00..16:00 are hot
        wbgt[h] = 31.0
    s = ww.day_schedule(_day(wbgt), cfg, acclimatized=True)
    heavy = s["workloads"]["heavy"]
    assert {"status": "not_advised", "start": "11:00", "end": "16:00"} in heavy["restricted"]
    assert heavy["summary"].startswith("Heavy work: not advised 11:00–16:00")
    assert all(iv["start"] >= "06:00" for iv in heavy["restricted"])
    assert s["workloads"]["light"]["summary"] == "Light work: normal work all day"


def test_unacclimatized_is_stricter(cfg):
    wbgt = [28.2] * 24
    acc = ww.day_schedule(_day(wbgt), cfg, acclimatized=True)["workloads"]["moderate"]["restricted"]
    un = ww.day_schedule(_day(wbgt), cfg, acclimatized=False)["workloads"]["moderate"]["restricted"]
    order = ww.STATUSES.index
    assert order(un[0]["status"]) > order(acc[0]["status"])


def test_first_days_of_heatwave_use_unacclimatized_limits(cfg):
    events = [{"start": "2024-05-17", "end": "2024-05-30"}]
    assert ww.acclimatized_on("2024-05-17", events, cfg) is False
    assert ww.acclimatized_on("2024-05-19", events, cfg) is False     # day 3
    assert ww.acclimatized_on("2024-05-20", events, cfg) is True      # day 4
    assert ww.acclimatized_on("2024-06-05", events, cfg) is True
