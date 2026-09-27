"""Alert workflow (Phase 7) on a temporary database with a synthetic heatwave run (no network)."""

import json
import warnings
from pathlib import Path

import pytest

from synth import synthetic_weather

warnings.filterwarnings("ignore", category=DeprecationWarning)
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api import alerts, db, dispatch, jobs  # noqa: E402
from api import main as api_main  # noqa: E402
from heatrisk import forecast, load_config  # noqa: E402
from heatrisk.pipeline import WARDS_PARQUET, load_wards  # noqa: E402

pytestmark = pytest.mark.skipif(not WARDS_PARQUET.exists(), reason="run scripts/build_wards.py first")
XSD = Path(__file__).parent / "data" / "CAP-v1.2.xsd"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("alerts") / "heat.db"
    orig = db.DB_PATH
    db.DB_PATH = path
    cfg, wards = load_config(), load_wards()
    wx = synthetic_weather(days=3, tmax=46.5, tmin=31)
    with db.connect(path) as conn:
        db.init(conn)
        jobs.load_wards_table(conn)
        run = db.start_run(conn, "forecast", source="synthetic")
        daily, hourly = forecast.run_wards(wx, wards, cfg)
        jobs.store_scores(conn, run, daily, hourly, forecast.detect_events(daily, cfg, len(wards)))
        db.finish_run(conn, run, "ok", issued_date="2024-05-20")
        created = alerts.generate(conn, dict(db.latest_run(conn, "forecast")), None, None, {})
    with TestClient(api_main.app) as c:
        c.created = created
        yield c
    db.DB_PATH = orig


def _first(client, level="red"):
    lst = client.get("/alerts").json()["alerts"]
    return next(a for a in lst if a["level"] == level and a["status"] == "draft")


def test_engine_drafts_once_per_day_and_level(client):
    assert client.created
    lst = client.get("/alerts").json()["alerts"]
    keys = [(a["date"], a["level"], a["kind"]) for a in lst]
    assert len(keys) == len(set(keys))
    assert all(a["status"] == "draft" for a in lst)
    with db.connect() as conn:                         # running the engine again adds nothing
        assert alerts.generate(conn, dict(db.latest_run(conn, "forecast")), None, None, {}) == []


def test_nothing_is_sent_without_approval(client):
    a = _first(client)
    r = client.post(f"/alerts/{a['alert_id']}/dispatch", json={"officer": "Officer A"})
    assert r.status_code == 409 and "approved" in r.json()["detail"]
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 0


def test_approval_and_rejection_need_a_named_officer_and_reason(client):
    a = _first(client)
    assert client.post(f"/alerts/{a['alert_id']}/approve", json={"officer": "  "}).status_code == 409
    assert client.post(f"/alerts/{a['alert_id']}/reject", json={"officer": "Officer A"}).status_code == 409


def test_edit_approve_dispatch_and_audit(client):
    a = _first(client)
    aid = a["alert_id"]
    e = client.patch(f"/alerts/{aid}", json={"officer": "Officer A", "channels": ["sms"], "languages": ["en", "gu"],
                                            "templates": {"en": {"public": {"sms": "{level} {day}, {ward}: stay cool. Call 108 -{sender}"}}}}).json()
    assert e["channels"] == ["sms"] and "stay cool" in e["previews"]["en"]["public"]["sms"]
    assert client.patch(f"/alerts/{aid}", json={"officer": "Officer A", "wards": ["AMC-99"]}).status_code == 409
    assert client.post(f"/alerts/{aid}/approve", json={"officer": "Officer A", "note": "ok"}).json()["status"] == "approved"
    assert client.patch(f"/alerts/{aid}", json={"officer": "Officer A", "channels": ["voice"]}).status_code == 409
    d = client.post(f"/alerts/{aid}/dispatch", json={"officer": "Officer A"}).json()
    assert d["mode"] == "simulated" and d["messages"] > 0 and set(d["status"]) == {"simulated"}
    assert {x["channel"] for x in d["alert"]["deliveries"]} == {"sms"}
    assert {x["lang"] for x in d["alert"]["deliveries"]} <= {"en", "gu"}
    assert client.post(f"/alerts/{aid}/dispatch", json={"officer": "Officer A"}).status_code == 409
    actions = [x["action"] for x in client.get(f"/audit?alert_id={aid}").json()["entries"]]
    assert actions[::-1] == ["alert_drafted", "alert_edited", "alert_approved", "alert_dispatched"]
    assert {x["actor"] for x in client.get(f"/audit?alert_id={aid}").json()["entries"]} == {"system", "Officer A"}


def test_cap_is_valid_cap_1_2(client):
    xmlschema = pytest.importorskip("xmlschema")
    a = client.get("/alerts").json()["alerts"][0]
    xml = client.get(f"/alerts/{a['alert_id']}/cap.xml").text
    xmlschema.XMLSchema(str(XSD)).validate(xml)
    assert "<severity>" in xml and xml.count("<info>") == len(a["languages"])


def test_ivr_twiml(client):
    a = client.get("/alerts").json()["alerts"][0]
    w = a["wards"][0]
    t = client.get(f"/ivr/{a['alert_id']}/{w}?lang=hi").text
    assert t.startswith("<?xml") and 'language="hi-IN"' in t and "<Say" in t
    m = client.post(f"/ivr/{a['alert_id']}/{w}/menu?lang=gu", content="Digits=2",
                    headers={"Content-Type": "application/x-www-form-urlencoded"}).text
    assert "ઠંડી જગ્યાઓ" in m                              # nearest cooling places, in Gujarati


def test_token_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("HEAT_API_TOKEN", "secret")
    a = client.get("/alerts").json()["alerts"][-1]
    assert client.post(f"/alerts/{a['alert_id']}/approve", json={"officer": "X"}).status_code == 401
    assert client.get("/alerts").status_code == 200        # reading stays open


def test_twilio_mode_refuses_the_example_recipients(monkeypatch):
    monkeypatch.setenv("HEAT_DISPATCH_MODE", "twilio")
    monkeypatch.setattr(dispatch, "RECIPIENTS", Path("does-not-exist.csv"))
    with pytest.raises(alerts.WorkflowError):
        dispatch.recipients()
