import copy

import pytest

from heatrisk.config import ConfigError, load_config, validate


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_shipped_config_is_valid(cfg):
    assert cfg["city"]["name"] == "Ahmedabad"


def test_thermal_weights_must_sum_to_one(cfg):
    bad = copy.deepcopy(cfg)
    bad["thermal_stress"]["weights"]["utci"] = 0.9
    with pytest.raises(ConfigError, match="sum to"):
        validate(bad)


def test_pvi_weights_must_sum_to_one(cfg):
    bad = copy.deepcopy(cfg)
    bad["pvi"]["weights"]["elderly_share"] = 0.5
    with pytest.raises(ConfigError, match="pvi"):
        validate(bad)


def test_alert_bands_must_increase(cfg):
    bad = copy.deepcopy(cfg)
    bad["alerts"]["levels"]["yellow"] = 30
    with pytest.raises(ConfigError, match="alerts"):
        validate(bad)


def test_normalization_range_must_be_positive(cfg):
    bad = copy.deepcopy(cfg)
    bad["thermal_stress"]["normalization"]["wbgt"] = {"zero": 33.0, "full": 25.0}
    with pytest.raises(ConfigError, match="wbgt"):
        validate(bad)


def test_work_thresholds_rise_as_work_time_falls(cfg):
    bad = copy.deepcopy(cfg)
    bad["work_windows"]["acclimatized"]["light"] = [33.0, 31.0, 32.0, 32.5]
    with pytest.raises(ConfigError, match="work_windows"):
        validate(bad)


def test_unacclimatized_limits_are_stricter(cfg):
    ww = cfg["work_windows"]
    for load in ww["workloads"]:
        for acc, unacc in zip(ww["acclimatized"][load], ww["unacclimatized"][load]):
            if acc is not None and unacc is not None:
                assert unacc < acc
