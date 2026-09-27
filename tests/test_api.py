"""API tests on a temporary database filled from synthetic weather (no network)."""

import warnings

import pytest

from synth import synthetic_weather

warnings.filterwarnings("ignore", category=DeprecationWarning)
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api import db, jobs  # noqa: E402
from api import main as api_main  # noqa: E402
from heatrisk import ensemble, forecast, load_config  # noqa: E402
from heatrisk.pipeline import WARDS_PARQUET, load_wards  # noqa: E402

pytestmark = pytest.mark.skipif(not WARDS_PARQUET.exists(), reason="run scripts/build_wards.py first")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("api") / "heat.db"
    orig = db.DB_PATH
    db.DB_PATH = path
    cfg, wards = load_config(), load_wards()
    wx = synthetic_weather(days=3, tmax=46.5, tmin=31)
    with db.connect(path) as conn:
        db.init(conn)
        jobs.load_wards_table(conn)
        run = db.start_run(conn, "forecast", source="synthetic")
        daily, hourly = forecast.run_wards(wx, wards, cfg)
        jobs.store_scores(conn, run, daily, hourly, forecast.detect_events(daily, cfg, len(wards)),
                          forecast.ward_peaks(daily, hourly, "2024-05-20"))
        db.finish_run(conn, run, "ok", issued_date="2024-05-20")
        ens = db.start_run(conn, "ensemble", source="synthetic")
        members = {"ecmwf_ifs025_m00": wx, "gfs025_m00": synthetic_weather(days=3, tmax=38, tmin=25)}
        jobs.store_probs(conn, ens, ensemble.probabilities(ensemble.score_members(members, wards, cfg), cfg))
        db.finish_run(conn, ens, "ok", issued_date="2024-05-20", n_members=2)
    with TestClient(api_main.app) as c:
        yield c
    db.DB_PATH = orig


def test_wards_geojson_has_scores_and_probabilities(client):
    j = client.get("/wards?day=2024-05-21").json()
    assert j["type"] == "FeatureCollection" and len(j["features"]) == 48
    p = j["features"][0]["properties"]
    for key in ("ward_name", "mri", "alert_mri", "htsi", "pvi", "p_red", "confidence", "top_factors"):
        assert key in p
    assert "explanation_mri" not in p                      # long explanations only in /ward
    assert j["meta"]["probability_members"] == 2 and "Model estimate" in j["meta"]["label"]


def test_ward_detail_explains_the_score(client):
    j = client.get("/ward/AMC-40").json()
    assert len(j["daily"]) == 3 and len(j["hourly"]) == 72
    d = j["daily"][1]
    ex = d["explanation_mri"]
    assert sum(c["points"] for c in ex["contributions"]) == pytest.approx(d["mri"], abs=0.1)
    assert {c["data_label"] for c in ex["contributions"]} >= {"live", "model_estimate"}
    assert "pvi_status" in j["attributes"] and "peak_day" in d


def test_days_and_events(client):
    d = client.get("/days").json()
    assert [x["date"] for x in d["days"]] == ["2024-05-20", "2024-05-21", "2024-05-22"]
    assert sum(d["days"][1]["counts"].values()) == 48
    e = client.get("/events").json()
    assert len(e["events"]) == 1 and e["events"][0]["start"] == "2024-05-20"


def test_config_is_disclosed(client):
    j = client.get("/config").json()
    assert j["config"]["alerts"]["levels"]["red"] == 100
    assert any(c["column"] == "informal_housing_share" for c in j["ward_columns"])


def test_errors(client):
    assert client.get("/ward/XX").status_code == 404
    assert client.get("/wards?replay=nope").status_code == 404
    assert client.get("/wards?replay=may2024").status_code == 503      # not built in this database
    assert client.get("/wards?day=1999-01-01").status_code == 404


# ---------- decision layer (Phase 6)

def test_ward_actions_and_work_windows(client):
    a = client.get("/ward/AMC-40/actions?day=2024-05-21").json()
    assert a["alert_mri"] in ("orange", "red") and a["actions"]
    assert all({"department", "action", "reason", "lead"} <= set(x) for x in a["actions"])
    w = client.get("/ward/AMC-40/work-windows?day=2024-05-21").json()
    assert w["available"] and set(w["workloads"]) == {"light", "moderate", "heavy", "very_heavy"}
    assert w["workloads"]["heavy"]["restricted"]                          # a 46.5 °C day restricts heavy work
    un = client.get("/ward/AMC-40/work-windows?day=2024-05-21&acclimatized=false").json()
    assert un["acclimatized"] is False


def test_ward_advisories(client):
    j = client.get("/ward/AMC-40/advisories?day=2024-05-21").json()
    assert len(j["advisories"]) == 9 and all(a["sms_fits"] for a in j["advisories"])
    gu = client.get("/ward/AMC-40/advisories?day=2024-05-21&lang=gu").json()["advisories"]
    assert {a["lang"] for a in gu} == {"gu"}
    assert client.get("/ward/AMC-40/advisories?lang=fr").status_code == 422


def test_priorities_cooling_allocation(client):
    p = client.get("/priorities?day=2024-05-21&view=healthcare").json()
    assert [w["priority"] for w in p["wards"][:3]] == [1, 2, 3] and p["city_actions"]
    c = client.get("/cooling").json()
    assert len(c["wards"]) == 48 and "recommended_sites" in c
    al = client.get("/allocation?day=2024-05-21&cooling_units=3&ambulances=7").json()
    assert len(al["cooling_units"]) <= 3 and sum(x["ambulances"] for x in al["ambulances"]) == 7
    assert client.get("/allocation?cooling_units=-1").status_code == 422


# ---------- what-if and feedback (Phase 8)

def test_reports_are_counts_only_and_flag_anomalies(client):
    body = {"ward_id": "AMC-40", "date": "2024-05-21", "age_band": "60+", "severity": "severe", "outcome": "referred", "role": "asha"}
    for _ in range(6):
        assert client.post("/reports", json=body).status_code == 200
    client.post("/reports", json={**body, "ward_id": "AMC-01", "age_band": "15-44"})
    with db.connect() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(report_counts)")]
    assert not {"name", "phone", "patient", "address"} & set(cols)
    s = client.get("/reports/summary?day=2024-05-21").json()
    assert s["total_reports"] == 7 and not s["includes_synthetic"]
    assert any(f["ward_id"] == "AMC-40" for f in s["flags"])
    assert client.post("/reports", json={**body, "severity": "fatal?"}).status_code == 422
    r = client.get("/reports/recalibration").json()
    assert r["applied"] is False and r["wards"]


def test_scenario_endpoint(client):
    from api import jobs
    if not jobs.replay_weather_path("may2024").exists():
        pytest.skip("replay weather not built")
    r = client.post("/scenarios/run", json={"changes": [{"lever": "tree_cover", "wards": ["AMC-40"], "pp": 10}]}).json()
    assert r["label"] == "scenario_estimate" and r["wards"][0]["change"]["mean_mri"] < 0
    assert client.post("/scenarios/run", json={"changes": [{"lever": "tree_cover", "wards": ["AMC-40"], "pp": 99}]}).status_code == 422
    sid = client.post("/scenarios", json={"name": "t", "changes": [{"lever": "tree_cover", "wards": ["AMC-40"], "pp": 5}]}).json()["scenario_id"]
    assert client.get(f"/scenarios/{sid}").json()["result"]["label"] == "scenario_estimate"


def test_report_card(client):
    r = client.get("/report-card?format=json")
    assert r.status_code == 200
    card = r.json()
    assert card["mode"] == "live" and card["verification"] is None      # no reference observations for live runs
    s = card["summary"]
    assert s["red_ward_days"] == sum(w["red_days"] for w in card["wards"])
    assert 0 <= s["red_ward_days_alerted"] <= s["red_ward_days"] and len(card["wards"]) == 48
    page = client.get("/report-card").text
    assert page.startswith("<!doctype html>") and "not clinical predictions" in page
    assert client.get("/report-card?event=9").status_code == 404


def test_whatsapp_bot_replies_only_with_approved_alerts(client, monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("HEAT_WHATSAPP_REPLAY", raising=False)
    from datetime import date
    from api import alerts as al
    with db.connect() as conn:            # the synthetic forecast is dated 2024: draft all days, then date them today
        run, _ = api_main._runs(conn, None)
        al.generate(conn, run, None, None, {}, from_day=None)
        conn.execute("UPDATE alerts SET date=? WHERE mode='live'", (date.today().isoformat(),))
    drafts = [a for a in client.get("/alerts?status=draft").json()["alerts"] if a["mode"] == "live"]
    ward = drafts[0]["wards"][0]
    with db.connect() as conn:
        name = conn.execute("SELECT ward_name FROM wards WHERE ward_id=?", (ward,)).fetchone()[0]
    r = client.post("/whatsapp/inbound", data={"From": "whatsapp:+910000000000", "Body": name})
    assert r.status_code == 200 and "No heat alert has been issued" in r.text        # draft only: nothing shared
    aid = drafts[0]["alert_id"]
    client.post(f"/alerts/{aid}/approve", json={"officer": "Officer B", "note": ""})
    r = client.post("/whatsapp/inbound", data={"From": "whatsapp:+910000000000", "Body": f"{name} gujarati"})
    assert r.status_code == 200 and "<Message>" in r.text and "No heat alert" not in r.text
    with db.connect() as conn:
        logged = conn.execute("SELECT detail FROM audit_log WHERE action='whatsapp_reply'").fetchall()
    assert logged and all("+91" not in row[0] for row in logged)                     # phone never stored
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("HEAT_PUBLIC_URL", "https://example.ngrok.app")
    assert client.post("/whatsapp/inbound", data={"Body": name}).status_code == 403  # unsigned request refused


def test_whatsapp_preview_is_read_only(client):
    with db.connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    r = client.get("/whatsapp/preview", params={"text": "help"}).json()
    assert r["simulated"] and "ward name" in r["reply"]
    assert client.get("/whatsapp/preview", params={"text": "Nowhereville"}).json()["detail"]["query"] == "unknown"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
