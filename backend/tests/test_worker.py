"""F3021 Planner·Worker — 작업 목록(fixed 인자), 고정 인자 보호, Worker 복구 정책 (네트워크·LLM 없음)."""

from datetime import date

import pytest
from pydantic import BaseModel, Field

from app.agent.deps import Deps
from app.agent.state import ArgChange, WorkerDecision
from app.agent.worker import MAX_LLM_RETRIES, apply_changes, build_tasks, worker_call
from app.events.bus import EventBus, RunEmitter
from app.tools.base import Registry, ToolError

HOME = {"date": "2026-11-21", "start_after": "18:00", "region": "대학로", "genre": "연극", "home_by": "23:30",
        "home_location": "망원동 성미산로 근처", "budget_max": 50000}
FULL_PLAN = ["search_performances", "get_performance_detail", "search_places", "get_transit_time", "get_weather"]
QUERY = {"region": "대학로", "genre": "연극", "page": 1}


def _task(tasks, tool):
    return next(t for t in tasks if t["tool"] == tool)


# ── 작업 목록 (Planner → Worker) ─────────────────────────────────────────────


def test_plan_request_tasks_mark_fixed_and_repairable_args():
    tasks = build_tasks("plan_request", "performance", HOME, FULL_PLAN, QUERY, today=date(2026, 11, 20))
    assert [t["id"] for t in tasks] == ["t1", "t2", "t3", "t4", "t5"]
    search = _task(tasks, "search_performances")
    assert search["args"] == {"date_from": "2026-11-21", "region": "대학로", "genre": "연극"}
    assert search["fixed"] == ["date_from", "region", "genre"] and search["repairable"] == []
    places = _task(tasks, "search_places")
    assert places["args"] == {"mode": "geocode", "query": "망원동 성미산로 근처"}
    assert places["fixed"] == ["mode"] and places["repairable"] == ["query"]
    transit = _task(tasks, "get_transit_time")
    assert transit["depends_on"] == ["t2", "t3"] and transit["args_from"]
    assert _task(tasks, "get_weather")["fixed"] == ["date"]


def test_tasks_follow_the_plan_without_home_condition():
    cond = {k: v for k, v in HOME.items() if k not in ("home_by", "home_location")}
    plan = ["search_performances", "get_performance_detail", "get_weather"]
    tasks = build_tasks("plan_request", "performance", cond, plan, QUERY, today=date(2026, 11, 20))
    assert [t["tool"] for t in tasks] == plan


def test_fact_query_keyword_is_repairable_but_dates_are_fixed():
    tasks = build_tasks("fact_query", "performance", {"keyword": "아일랜드"}, [], QUERY, today=date(2026, 11, 20))
    search = tasks[0]
    assert search["args"]["keyword"] == "아일랜드" and search["repairable"] == ["keyword"]
    assert search["fixed"] == ["date_from", "date_to"] and search["args"]["date_from"] == "2026-11-20"


def test_weather_only_tasks():
    tasks = build_tasks("fact_query", "weather", {"date": "2026-11-21", "region": "대학로"}, [], QUERY,
                        today=date(2026, 11, 20), weather_query="서울 종로구 대학로")
    assert [t["tool"] for t in tasks] == ["search_places", "get_weather"]
    assert tasks[0]["args"]["query"] == "서울 종로구 대학로" and tasks[1]["fixed"] == ["date"]


# ── 고정 인자 보호 (코드가 거부) ─────────────────────────────────────────────

PLACES_TASK = {"id": "t3", "tool": "search_places", "args": {"mode": "geocode", "query": "망원동 성미산로 근처"},
               "fixed": ["mode"], "repairable": ["query"]}


def test_normalizing_free_text_is_accepted():
    new, why = apply_changes(PLACES_TASK, PLACES_TASK["args"], [ArgChange(name="query", value="망원동 성미산로")],
                             PLACES_TASK["args"])
    assert why is None and new == {"mode": "geocode", "query": "망원동 성미산로"}


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (ArgChange(name="mode", value="nearby"), "고정 인자"),
        (ArgChange(name="radius_m", value="2000"), "바꿀 수 없는 인자"),
        (ArgChange(name="query", value="강남역"), "원문과 겹치지"),  # 전혀 다른 장소 → 지어내기 의심
    ],
)
def test_guard_rejects_unsafe_changes(change, why):
    new, reason = apply_changes(PLACES_TASK, PLACES_TASK["args"], [change], PLACES_TASK["args"])
    assert new is None and why in reason


def test_guard_rejects_empty_change():
    new, reason = apply_changes(PLACES_TASK, PLACES_TASK["args"], [], PLACES_TASK["args"])
    assert new is None and "바꾼 인자가 없음" in reason


# ── Worker 복구 정책 ─────────────────────────────────────────────────────────


class PlacesArgs(BaseModel):
    mode: str
    query: str = Field(default="")


def _registry(found_queries: set[str], code: str = "NO_RESULT"):
    reg = Registry()

    @reg.register(name="search_places", description="장소를 찾을 때 사용한다.", args_model=PlacesArgs, source="TEST")
    def search_places(args):
        if args.query in found_queries:
            return {"items": [{"name": args.query, "address": "서울 마포구 망원동", "lat": 37.55, "lng": 126.9}]}
        raise ToolError(code, "검색 결과가 없어요.")

    return reg


def _setup(mode: str, worker=None, found=frozenset({"망원동 성미산로"}), code="NO_RESULT"):
    deps = Deps(registry=_registry(set(found), code), bus=EventBus(), mode=mode, worker=worker)
    deps.emitters["r"] = em = RunEmitter(deps.bus, "s", "r")
    em.llm_calls = em.api_calls = 0
    state = {"run_id": "r", "session_id": "s", "message": "집(망원동 성미산로 근처)", "tasks": [PLACES_TASK]}
    return deps, state, em


def _types(em):
    return [e.type for e in em.events]


def test_mode_a_has_no_recovery_policy():
    deps, state, em = _setup("A")
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert result["error"]["code"] == "NO_RESULT" and info["action"] is None
    assert "worker.decision" not in _types(em)


def test_mode_b_requests_replan_without_llm():
    deps, state, em = _setup("B")
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert info["action"] == "request_replan" and em.llm_calls == 0
    decision = next(e for e in em.events if e.type == "worker.decision")
    assert decision.payload["by"] == "rule"


def test_mode_c_repairs_free_text_with_one_llm_call():
    calls = []

    def worker(**ctx):
        calls.append(ctx)
        return WorkerDecision(action="retry", changes=[ArgChange(name="query", value="망원동 성미산로")],
                              reason="'근처'를 빼면 검색할 수 있음")

    deps, state, em = _setup("C", worker)
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert result["ok"] and info["action"] == "retry_ok"
    assert info["args"]["query"] == "망원동 성미산로" and info["repaired_from"]["query"] == "망원동 성미산로 근처"
    assert em.llm_calls == 1 and calls[0]["fixed"] == ["mode"] and calls[0]["repairable"] == ["query"]
    assert any(e.type == "llm.decision" and e.payload["kind"] == "worker_retry" for e in em.events)


def test_mode_c_rejects_fixed_arg_change_and_requests_replan():
    def worker(**_ctx):
        return WorkerDecision(action="retry", changes=[ArgChange(name="mode", value="nearby")], reason="주변 검색")

    deps, state, em = _setup("C", worker)
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert not result["ok"] and info["action"] == "request_replan"
    rejected = next(e for e in em.events if e.type == "worker.rejected")
    assert "고정 인자" in rejected.payload["reason"]
    assert _types(em).count("tool.requested") == 1  # 거부된 인자로는 호출하지 않음


def test_mode_c_stops_after_max_retries():
    values = iter(["망원동 성미산로 쪽", "망원동 성미산로 부근", "망원동 성미산로 인근"])

    def worker(**_ctx):
        return WorkerDecision(action="retry", changes=[ArgChange(name="query", value=next(values))], reason="다시")

    deps, state, em = _setup("C", worker, found=frozenset())
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert not result["ok"] and info["action"] == "request_replan"
    assert em.llm_calls == MAX_LLM_RETRIES == 2
    assert _types(em).count("tool.requested") == 1 + MAX_LLM_RETRIES


def test_mode_c_respects_llm_choice_to_ask_user():
    def worker(**_ctx):
        return WorkerDecision(action="request_replan", changes=[], reason="두 장소 중 어디인지 추측해야 함")

    deps, state, em = _setup("C", worker)
    _, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert info["action"] == "request_replan" and em.llm_calls == 1


def test_ambiguous_never_calls_worker_llm():
    def worker(**_ctx):
        raise AssertionError("AMBIGUOUS에서는 LLM을 부르지 않는다")

    deps, state, em = _setup("C", worker, found=frozenset(), code="AMBIGUOUS")
    result, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert result["error"]["code"] == "AMBIGUOUS" and info["action"] is None and em.llm_calls == 0


def test_task_with_only_fixed_args_requests_replan_by_rule():
    def worker(**_ctx):
        raise AssertionError("고칠 인자가 없으면 LLM을 부르지 않는다")

    deps, state, em = _setup("C", worker)
    state["tasks"] = [{**PLACES_TASK, "repairable": []}]
    _, info = worker_call(state, deps, "execute", "t3", "search_places", dict(PLACES_TASK["args"]))
    assert info["action"] == "request_replan" and em.llm_calls == 0


# ── 구성 선택 (AGENT_MODE) ───────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "mode"), [("", "C"), ("a", "A"), ("b", "B"), ("Z", "C")])
def test_agent_mode_from_env(monkeypatch, value, mode):
    from app import config

    monkeypatch.setenv("AGENT_MODE", value)
    assert config.agent_mode() == mode


def test_container_wires_worker_llm_only_in_mode_c(monkeypatch):
    from app.db.database import Database
    from app.main import build_container

    for mode, has_worker in (("A", False), ("B", False), ("C", True)):
        monkeypatch.setenv("AGENT_MODE", mode)
        deps = build_container(Database(":memory:")).service.deps
        assert deps.mode == mode and (deps.worker is not None) == has_worker
