"""F3021 구성 A/B/C를 그래프 수준에서 비교 (저장된 샘플 + LLM 대역).

W1: 집 위치를 '망원동 성미산로 근처'처럼 말해 분석은 통과하지만 카카오가 못 찾는 경우(실측 NO_RESULT).
  A(단일 Agent)  → 집 좌표 없이 진행 → 이동시간 판정 불가 → 헛된 재계획 3회 → 상한 도달
  B(Worker LLM 끔) → Worker가 규칙으로 재계획 요청 → Planner가 사용자에게 되묻기
  C(Worker LLM 켬) → Worker LLM이 '근처'를 빼고 재시도 → 추천 성공 (LLM +1회)
"""

from datetime import datetime

import pytest

from app.agent.state import ArgChange, WorkerDecision
from app.offline import FixedAnalyzer, S1, S1_MESSAGE, analysis, build_offline, offline_apis

NOW = datetime(2026, 11, 20, 8, 41)
W1 = "토요일 저녁 6시 이후 대학로 연극, 밤 11시 반까지 집(망원동 성미산로 근처)에 가야 해. 5만원 이하"
TABLE = {
    S1_MESSAGE: S1,
    W1: analysis("plan_request", "귀가 조건이 있는 추천 요청", date="2026-11-21", start_after="18:00",
                 region="대학로", genre="연극", home_by="23:30", home_location="망원동 성미산로 근처",
                 budget_max=50000),
}


def repair_worker(**ctx):
    return WorkerDecision(action="retry", changes=[ArgChange(name="query", value="망원동 성미산로")],
                          reason="'근처'를 빼면 검색할 수 있음")


@pytest.fixture
def run(monkeypatch):
    for name in ("KOPIS_API_KEY", "KAKAO_REST_API_KEY", "KMA_SERVICE_KEY"):
        monkeypatch.setenv(name, "fake-key")

    def _run(mode, message, worker=None):
        with offline_apis(NOW):
            service, _, logs = build_offline(NOW, FixedAnalyzer(TABLE), mode=mode, worker=worker)
            r = service.chat("s", message)
            return r, logs.events("s")
    return _run


def _types(events):
    return [e["type"] for e in events]


def _done(events):
    return next(e["payload"] for e in events if e["type"] == "run.completed")


def test_w1_mode_a_wastes_replans_without_home_location(run):
    r, events = run("A", W1)
    assert r["status"] == "limit_reached" and r["replan_count"] == 3
    assert "worker.decision" not in _types(events) and "plan.tasks" not in _types(events)


def test_w1_mode_b_asks_user_instead_of_futile_replans(run):
    r, events = run("B", W1)
    assert r["status"] == "clarify" and r["replan_count"] == 0 and "집" in r["reply"]
    decision = next(e["payload"] for e in events if e["type"] == "worker.decision")
    assert decision["by"] == "rule" and decision["action"] == "request_replan"
    assert "get_transit_time" not in [e["payload"]["tool"] for e in events if e["type"] == "tool.requested"]


def test_w1_mode_c_repairs_and_recommends_with_one_extra_llm_call(run):
    r, events = run("C", W1, worker=repair_worker)
    assert r["status"] == "ok" and r["recommendations"] and r["recommendations"][0]["showtimes"][0]["home_arrival"]
    assert any("망원동 성미산로" in note for note in r["defaults_applied"])
    worker_llm = [e for e in events if e["type"] == "llm.decision" and e["payload"]["kind"] == "worker_retry"]
    assert len(worker_llm) == 1
    assert _done(events)["llm_calls"] == 2  # 분석(대역) 1 + Worker 1 — 계획·요약은 대역에서 끔


def test_w1_mode_c_follows_llm_choice_to_ask(run):
    def ask_worker(**_ctx):
        return WorkerDecision(action="request_replan", changes=[], reason="어느 장소인지 추측해야 함")

    r, _ = run("C", W1, worker=ask_worker)
    assert r["status"] == "clarify"


def test_planner_emits_task_list_with_fixed_args_in_b_and_c(run):
    for mode in ("B", "C"):
        _, events = run(mode, S1_MESSAGE, worker=repair_worker)
        tasks = next(e["payload"]["tasks"] for e in events if e["type"] == "plan.tasks")
        search = next(t for t in tasks if t["tool"] == "search_performances")
        assert search["fixed"] == ["date_from", "region", "genre"]
        assert next(t for t in tasks if t["tool"] == "search_places")["repairable"] == ["query"]


def test_normal_path_uses_no_worker_llm(run):
    """정상 경로(S1)에서는 구성 C도 Worker LLM 0회 — 결과·호출 수가 A와 같다."""
    def never(**_ctx):
        raise AssertionError("정상 경로에서 Worker LLM을 부르면 안 된다")

    ra, ea = run("A", S1_MESSAGE)
    rc, ec = run("C", S1_MESSAGE, worker=never)
    assert [x["title"] for x in ra["recommendations"]] == [x["title"] for x in rc["recommendations"]]
    assert _done(ea)["llm_calls"] == _done(ec)["llm_calls"]
    assert "worker.decision" not in _types(ec)


def test_trace_shows_worker_repair(run):
    r, _ = run("C", W1, worker=repair_worker)
    assert any(t["label"].startswith("Worker") for t in r["trace"])
