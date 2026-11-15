import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import analysis, llm
from app.db import Database, iso
from app.main import app
from app.stats import BASELINE

REPORT_KEYS = {"id", "t", "window_minutes", "engine", "model", "summary", "findings", "facts", "data_points",
               "disclaimer"}
FINDING_KEYS = {"condition", "likelihood", "evidence", "action"}


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


def fill(db, seconds=120, sqi=None, **values):
    """Store `seconds` of rows ending now: baseline vitals with some values overridden."""
    sqi = sqi or {}
    now = datetime.now(timezone.utc)
    for i in range(seconds):
        vitals = {n: {"value": values.get(n, b), "status": "green", "sqi": sqi.get(n, 1.0)}
                  for n, b in BASELINE.items()}
        db.record_sample(iso(now - timedelta(seconds=seconds - i)), float(i), "nominal", vitals,
                         values.get("dose_rate", 12.0), 4.2 + i * 0.0001, "green", "green")


def report_for(db, minutes=10):
    return analysis.local_report(analysis.window_stats(db, minutes))


def test_history_round_trip_and_thinning(db):
    fill(db, seconds=1000, hr=75.0)
    points = db.history("hr", 60)
    assert 0 < len(points) <= 300
    assert points[0]["value"] == 75.0 and points[0]["status"] == "green"
    assert [p["t"] for p in points] == sorted(p["t"] for p in points)
    assert db.stats()["rows"] == 1000
    with pytest.raises(KeyError):
        db.history("nope", 60)


def test_checkins_and_alerts_round_trip(db):
    db.add_checkin(3, 7.0, "first")
    stored = db.add_checkin(5, 8.5, "second")
    assert db.checkins()[0] == stored
    db.log_alert({"metric": "hr", "level": "amber", "origin": "physiological", "title": "Heart rate up"})
    assert db.alert_log(10)[0]["title"] == "Heart rate up"


def test_finds_hypoxia(db):
    fill(db, spo2=88.5, hr=88.0, resp_rate=19.0)
    report = report_for(db)
    top = report["findings"][0]
    assert "hypoxia" in top["condition"] and top["likelihood"] == "high"
    assert any("88.5" in line for line in top["evidence"])
    assert report["engine"] == "local" and report["data_points"] == 120


def test_nominal_has_no_findings(db):
    fill(db)
    report = report_for(db)
    assert report["findings"] == []
    assert "Nothing unusual" in report["summary"]
    assert len(report["facts"]) >= 2


def test_untrusted_ecg_is_a_sensor_problem_not_a_body_condition(db):
    # The stale held values would look like low HRV and high HR if they were believed
    fill(db, sqi={"hr": 0.0, "hrv_rmssd": 0.0}, hr=95.0, hrv_rmssd=15.0)
    conditions = [f["condition"] for f in report_for(db)["findings"]]
    assert conditions == ["Possible sensor problem: ECG electrodes"]


def test_empty_database_says_too_little_data(db):
    report = report_for(db)
    assert report["findings"] == []
    assert "Not enough data" in report["summary"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_analysis_route_returns_contract(client):
    assert client.get("/api/analysis/latest").status_code == 404
    report = client.post("/api/analysis", json={"minutes": 5}).json()
    assert set(report) == REPORT_KEYS
    assert report["window_minutes"] == 5 and report["engine"] == "local" and report["model"] is None
    assert all(set(f) == FINDING_KEYS for f in report["findings"])
    assert client.get("/api/analysis/latest").json() == report
    assert client.post("/api/analysis").json()["window_minutes"] == 60


def test_history_alerts_and_stats_routes(client):
    assert client.get("/api/history?metric=hr&minutes=5").json()["metric"] == "hr"
    assert client.get("/api/history?metric=nope").status_code == 404
    assert isinstance(client.get("/api/alerts/log").json(), list)
    assert set(client.get("/api/stats").json()) == {"rows", "first", "last", "size_kb"}


class FailingClient:
    class messages:
        @staticmethod
        def parse(**_):
            raise TimeoutError("too slow")


def test_model_layer_falls_back_without_a_key(monkeypatch, db):
    for name in ("ANTHROPIC_API_KEY", "VITALIS_USE_BEDROCK"):
        monkeypatch.delenv(name, raising=False)
    fill(db)
    stats = analysis.window_stats(db, 10)
    local = analysis.local_report(stats)
    assert llm.refine(stats, local) == local


def test_model_layer_falls_back_when_the_client_raises(monkeypatch, db):
    monkeypatch.setattr(llm, "make_client", lambda: (FailingClient(), "test-model"))
    fill(db)
    stats = analysis.window_stats(db, 10)
    local = analysis.local_report(stats)
    assert llm.refine(stats, local) == local


def test_model_layer_marks_a_valid_reply(monkeypatch, db):
    class Reply:
        parsed_output = llm.ModelReport(summary="All normal.", findings=[], facts=["a", "b"])

    class Client:
        class messages:
            @staticmethod
            def parse(**kwargs):
                assert set(json.loads(kwargs["messages"][0]["content"])) == {"statistics", "local_findings"}
                return Reply

    monkeypatch.setattr(llm, "make_client", lambda: (Client(), "test-model"))
    fill(db)
    stats = analysis.window_stats(db, 10)
    report = llm.refine(stats, analysis.local_report(stats))
    assert report["engine"] == "llm" and report["model"] == "test-model" and report["summary"] == "All normal."
