"""FastAPI 엔드포인트 (F3014~F3017, NF3002) — 메모리 DB + 샘플 API + 고정 분석 결과."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.database import Database
from app.main import build_container, create_app
from app.offline import FixedAnalyzer, S1, S1_MESSAGE, SAVE_1, offline_apis

NOW = datetime(2026, 11, 20, 8, 41)
PLAN = {"performance_id": "PF1", "title": "연극 A", "venue_name": "○○아트홀", "date": "2026-11-21",
        "start_time": "19:00", "end_time": "21:00", "price": 30000}


@pytest.fixture
def client(monkeypatch):
    for name in ("KOPIS_API_KEY", "KAKAO_REST_API_KEY", "KMA_SERVICE_KEY", "GMS_KEY"):
        monkeypatch.setenv(name, "secret-value-should-not-leak")
    monkeypatch.setenv("LLM_BASE_URL", "")
    with offline_apis(NOW):
        container = build_container(Database(":memory:"), {
            "analyzer": FixedAnalyzer({S1_MESSAGE: S1, "1번 저장해줘": SAVE_1}),
            "planner": None, "summarizer": None, "now": lambda: NOW})
        yield TestClient(create_app(container), raise_server_exceptions=False)


def test_health_returns_booleans_only(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "services": {"kopis": True, "kakao": True, "kma": True, "llm": False}}
    assert "secret-value" not in client.get("/api/health").text


def test_chat_s1_and_save_via_chat(client):
    r = client.post("/api/chat", json={"message": S1_MESSAGE})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["recommendations"] and body["session_id"].startswith("s-")
    saved = client.post("/api/chat", json={"session_id": body["session_id"], "message": "1번 저장해줘"}).json()
    assert saved["saved_plan"]["title"] == body["recommendations"][0]["title"]
    assert client.get("/api/plans").json()["plans"][0]["id"] == saved["saved_plan"]["id"]


def test_chat_rejects_empty_message_with_error_format(client):
    r = client.post("/api/chat", json={"message": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_INPUT"


def test_plans_crud_with_overlaps(client):
    first = client.post("/api/plans", json=PLAN)
    assert first.status_code == 201 and first.json()["overlaps"] == []
    pid = first.json()["plan"]["id"]
    second = client.post("/api/plans", json={**PLAN, "title": "연극 B", "start_time": "20:00", "end_time": "22:00"}).json()
    assert [p["id"] for p in second["overlaps"]] == [pid]
    assert client.get("/api/plans").json()["plans"][0]["overlaps"] == [second["plan"]["id"]]
    patched = client.patch(f"/api/plans/{pid}", json={"start_time": "17:00", "end_time": "19:00", "memo": "일찍"}).json()
    assert patched["plan"]["memo"] == "일찍" and patched["overlaps"] == []
    assert client.get(f"/api/plans/{pid}").json()["plan"]["start_time"] == "17:00"
    assert client.delete(f"/api/plans/{pid}").json() == {"deleted": True}
    missing = client.get(f"/api/plans/{pid}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


def test_plan_validation(client):
    r = client.patch("/api/plans/1", json={"start_time": "25:00"})
    assert r.status_code == 422 and "start_time" in r.json()["error"]["message"]


def test_logs_list_detail_delete_and_no_update_routes(client):
    sid = client.post("/api/chat", json={"message": S1_MESSAGE}).json()["session_id"]
    sessions = client.get("/api/logs").json()["sessions"]
    assert sessions[0]["session_id"] == sid and sessions[0]["runs"] == 1
    events = client.get(f"/api/logs/{sid}").json()["events"]
    assert events[0]["type"] == "run.started" and [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert client.delete(f"/api/logs/{sid}").json()["deleted"] == len(events)
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in paths.items():
        if path.startswith("/api/logs"):
            assert not {"put", "patch"} & set(methods)


def test_unexpected_error_hides_details(client):
    container = client.app.state.container

    def boom(*_a, **_k):
        raise RuntimeError("internal stack detail")

    container.plans.list = boom
    r = client.get("/api/plans")
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "internal stack detail" not in r.text


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "커튼콜 플래너" in r.text
