"""Agent 그래프 — 저장된 실제 샘플 + 고정 분석 결과(LLM 대역)로 시나리오 S1·S3~S11 검증."""

from datetime import datetime

import pytest
from langchain_core.messages import AIMessage

from app.agent.deps import Deps
from app.offline import FixedAnalyzer, S1, S1_MESSAGE, SAVE_1, analysis, build_offline, offline_apis
from app.agent.service import AgentService
from app.events.bus import EventBus
from app.tools import REGISTRY

NOW = datetime(2026, 11, 20, 8, 41)

TABLE = {
    S1_MESSAGE: S1,
    "1번 저장해줘": SAVE_1,
    "S2": analysis("plan_request", "시작·종료·예산 제약", date="2026-11-21", start_after="19:00", end_by="21:00",
                   region="대학로", genre="연극", budget_max=30000),
    "S3": analysis("plan_request", "늦은 시각·저예산 뮤지컬", date="2026-11-21", start_after="22:00",
                   genre="뮤지컬", budget_max=20000),
    "S5": analysis("chitchat", "인사와 사용법 질문"),
    "S6": analysis("plan_request", "장르만 바꾸는 요청", genre="뮤지컬"),
    "S7": analysis("fact_query", "특정 작품의 사실 질문", topic="performance", keyword="아일랜드"),
    "S8": analysis("plan_request", "귀가 시각은 있으나 집 위치 없음", date="2026-11-21", genre="연극", home_by="23:30"),
    "S10": analysis("plan_request", "예보 범위 밖 날짜", date="2026-12-19", start_after="18:00", region="대학로",
                    genre="연극"),
    "S11": analysis("fact_query", "날씨만 묻는 요청", topic="weather", date="2026-11-21", region="대학로",
                    start_after="21:00"),
    "중구": analysis("plan_request", "지역이 모호함", date="2026-11-21", region="중구"),
}


@pytest.fixture
def offline(monkeypatch):
    for name in ("KOPIS_API_KEY", "KAKAO_REST_API_KEY", "KMA_SERVICE_KEY"):
        monkeypatch.setenv(name, "fake-key")
    with offline_apis(NOW):
        service, plans, logs = build_offline(NOW, FixedAnalyzer(TABLE))
        yield service, plans, logs


def _tools(logs, session="s"):
    return [e["payload"]["tool"] for e in logs.events(session) if e["type"] == "tool.requested"]


def test_s1_passes_without_replan(offline):
    service, _, logs = offline
    r = service.chat("s", S1_MESSAGE)
    assert r["status"] == "ok" and r["replan_count"] == 0
    assert 1 <= len(r["recommendations"]) <= 5
    top = r["recommendations"][0]["showtimes"][0]
    assert top["start"] >= "18:00" and top["home_arrival"] <= "23:30"
    assert all(rec["min_price"] <= 50000 for rec in r["recommendations"])
    assert r["recommendations"][0]["weather"]["status"] == "ok"
    types = [e["type"] for e in logs.events("s")]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    assert "constraint.evaluated" in types and "llm.decision" in types


def test_s1_two_stage_judgement_limits_transit_calls(offline):
    service, _, logs = offline
    service.chat("s", S1_MESSAGE)
    tools = _tools(logs)
    assert tools.count("get_transit_time") < tools.count("get_performance_detail")


def test_s3_stops_after_max_replans_with_stats(offline):
    service, _, logs = offline
    r = service.chat("s", "S3")
    assert r["status"] == "limit_reached" and r["replan_count"] == 3
    assert "탈락" in r["reply"]
    stopped = [e for e in logs.events("s") if e["type"] == "replan.stopped"]
    assert stopped and stopped[0]["payload"]["reason"] == "limit"
    assert any(t["is_replan"] for t in r["trace"])


def test_s3_does_not_change_user_constraints(offline):
    service, _, logs = offline
    service.chat("s", "S3")
    for e in logs.events("s"):
        if e["type"] == "tool.requested" and e["payload"]["tool"] == "search_performances":
            assert e["payload"]["args"]["date_from"] == "2026-11-21"


def test_s4_weather_failure_keeps_recommendations(offline, monkeypatch):
    monkeypatch.setenv("KMA_SERVICE_KEY", "")
    service, _, _ = offline
    r = service.chat("s", S1_MESSAGE)
    assert r["status"] == "ok" and r["recommendations"]
    assert all(rec["weather"]["status"] == "unavailable" for rec in r["recommendations"])
    assert any(w["code"] == "MISSING_API_KEY" and w["service"] == "기상청" for w in r["warnings"])


def test_s5_chitchat_calls_no_tools(offline):
    service, _, logs = offline
    r = service.chat("s", "S5")
    assert r["status"] == "ok" and "커튼콜" in r["reply"]
    assert _tools(logs) == []


def test_s6_memory_changes_only_genre(offline):
    service, _, _ = offline
    service.chat("s", S1_MESSAGE)
    r = service.chat("s", "S6")
    u = r["understood"]
    assert u["genre"] == "뮤지컬"
    assert (u["date"], u["start_after"], u["budget_max"], u["home_by"]) == ("2026-11-21", "18:00", 50000, "23:30")


def test_s7_fact_query_without_judgement(offline):
    service, _, logs = offline
    r = service.chat("s", "S7")
    assert r["facts"]["found"] and r["facts"]["runtime_min"]
    assert _tools(logs) == ["search_performances", "get_performance_detail"]
    assert not [e for e in logs.events("s") if e["type"] == "constraint.evaluated"]


def test_s8_asks_home_before_any_tool(offline):
    service, _, logs = offline
    r = service.chat("s", "S8")
    assert r["status"] == "clarify" and "집" in r["reply"]
    assert _tools(logs) == []


def test_ambiguous_region_asks_before_any_tool(offline):
    service, _, logs = offline
    r = service.chat("s", "중구")
    assert r["status"] == "clarify" and _tools(logs) == []


def test_s9_save_reports_overlap(offline):
    service, plans, _ = offline
    service.chat("s", S1_MESSAGE)
    first = service.chat("s", "1번 저장해줘")
    assert first["saved_plan"]["id"] and first["overlaps"] == []
    second = service.chat("s", "1번 저장해줘")
    assert len(second["overlaps"]) == 1 and "겹쳐요" in second["reply"]
    assert len(plans.list()) == 2


def test_s10_out_of_range_weather_without_kma_call(offline):
    service, _, logs = offline
    r = service.chat("s", "S10")
    assert all(rec["weather"]["status"] == "out_of_range" for rec in r["recommendations"])
    weather = [e for e in logs.events("s") if e["type"] == "tool.responded" and e["payload"]["tool"] == "get_weather"]
    assert weather and all(e["payload"]["code"] == "OUT_OF_RANGE" for e in weather)


def test_s11_weather_only_skips_performance_tools(offline):
    service, _, logs = offline
    r = service.chat("s", "S11")
    assert r["facts"]["kind"] == "weather" and r["facts"]["found"]
    assert _tools(logs) == ["search_places", "get_weather"]
    assert r["assumptions"] == ["예보는 발표 시각 기준이며 바뀔 수 있어요"]  # 공연 가격 안내는 붙이지 않음


def test_llm_failure_returns_error_response(offline):
    service, _, _ = offline

    def broken(*_a, **_k):
        raise RuntimeError("gateway down")

    service.deps.analyzer = broken
    r = service.chat("s", S1_MESSAGE)
    assert r["status"] == "error" and any(w["code"] == "LLM_UNAVAILABLE" for w in r["warnings"])
    assert "gateway down" not in str(r)


def test_llm_plan_is_validated_and_falls_back(offline):
    service, _, logs = offline
    service.deps.planner = lambda *_a, **_k: (["get_weather"], "날씨만")  # 필수 Tool 누락 → 규칙 템플릿
    r = service.chat("s", S1_MESSAGE)
    assert r["status"] == "ok"
    assert any(e["type"] == "plan.fallback" for e in logs.events("s"))


def test_llm_plan_accepted_when_valid(offline):
    service, _, logs = offline
    plan = ["search_performances", "get_performance_detail", "search_places", "get_transit_time", "get_weather"]
    service.deps.planner = lambda *_a, **_k: (plan, "귀가 조건이 있어 이동시간 포함")
    service.chat("s", S1_MESSAGE)
    decisions = [e for e in logs.events("s") if e["type"] == "llm.decision" and e["payload"]["kind"] == "plan"]
    assert decisions[0]["payload"]["value"] == plan


def test_summary_with_invented_number_is_replaced_by_template(offline):
    service, _, _ = offline
    service.deps.summarizer = lambda facts: "19:45에 시작하는 공연을 99,000원에 찾았어요."
    r = service.chat("s", S1_MESSAGE)
    assert r["reply"].startswith("조건(")


def test_summary_with_known_numbers_is_kept(offline):
    service, _, _ = offline
    service.deps.summarizer = lambda facts: "조건에 맞는 공연을 찾았어요. 첫 번째 추천을 확인해 보세요."
    assert service.chat("s", S1_MESSAGE)["reply"].startswith("조건에 맞는")


def test_three_llm_calls_for_normal_request(offline):
    service, _, logs = offline
    service.deps.planner = lambda *_a, **_k: (
        ["search_performances", "get_performance_detail", "search_places", "get_transit_time"], "이유")
    service.deps.summarizer = lambda facts: "찾았어요."
    service.chat("s", S1_MESSAGE)
    done = [e for e in logs.events("s") if e["type"] == "run.completed"][0]
    assert done["payload"]["llm_calls"] == 3


def test_graph_mermaid_has_all_nodes():
    text = AgentService(Deps(REGISTRY, EventBus())).mermaid()
    for node in ("analyze", "plan", "execute", "judge", "replan", "enrich", "respond", "clarify", "save_plan"):
        assert node in text


def test_real_llm_steps_parse_tool_calls(monkeypatch):
    """LLMPlanner가 bind_tools 응답의 tool_calls에서 Tool 이름을 꺼내는지 (LLM은 가짜)."""
    from app.agent import llm_steps

    class FakeLLM:
        def bind_tools(self, specs):
            assert {s["function"]["name"] for s in specs} >= {"search_performances"}
            return self

        def invoke(self, _messages):
            return AIMessage(content="귀가 조건 없음", tool_calls=[
                {"name": "search_performances", "args": {}, "id": "1"},
                {"name": "get_performance_detail", "args": {}, "id": "2"}])

    monkeypatch.setattr(llm_steps, "get_llm", lambda purpose: FakeLLM())
    tools, reason = llm_steps.LLMPlanner()("요청", conditions={}, tool_specs=REGISTRY.openai_specs())
    assert tools == ["search_performances", "get_performance_detail"] and reason == "귀가 조건 없음"


def test_llm_first_step_selection_is_completed_by_rules(offline):
    """실측: Claude는 첫 단계(후보 검색 + 집 좌표)만 고른다 → 코드가 상세·이동시간·날씨를 의존 순서로 채운다."""
    service, _, logs = offline
    service.deps.planner = lambda *_a, **_k: (["search_performances", "search_places"], "후보와 집 좌표를 먼저")
    r = service.chat("s", S1_MESSAGE)
    decision = [e for e in logs.events("s") if e["type"] == "llm.decision" and e["payload"]["kind"] == "plan"][0]
    payload = decision["payload"]
    assert payload["llm_selected"] == ["search_performances", "search_places"]
    assert payload["value"] == ["search_performances", "get_performance_detail", "search_places",
                                "get_transit_time", "get_weather"]
    assert set(payload["completed_by_rule"]) == {"get_performance_detail", "get_transit_time", "get_weather"}
    assert r["status"] == "ok" and not [e for e in logs.events("s") if e["type"] == "plan.fallback"]


def test_llm_choosing_transit_without_home_condition_falls_back(offline):
    service, _, logs = offline
    service.deps.planner = lambda *_a, **_k: (["search_performances", "get_transit_time"], "이동시간도")
    service.chat("s", "S2")
    fallback = [e for e in logs.events("s") if e["type"] == "plan.fallback"]
    assert fallback and "필요 없는" in fallback[0]["payload"]["reason"]
    assert "get_transit_time" not in _tools(logs)


def test_trace_ends_with_respond_step_and_has_total_time(offline):
    service, _, _ = offline
    r = service.chat("s", S1_MESSAGE)
    assert r["trace"][-1]["label"].startswith("응답 생성")
    assert isinstance(r["elapsed_ms"], int)


def test_clarify_trace_shows_no_tool_step(offline):
    service, _, _ = offline
    r = service.chat("s", "S8")
    assert r["trace"][-1]["label"].startswith("되묻기")


# ── 날씨 위치: 지역 이름만으로 검색하면 다른 도시의 같은 이름 장소가 1위로 나올 수 있다 ──────────


def test_weather_query_is_qualified_with_city():
    from app.agent.nodes.execution import weather_place_query

    # '서울 대학로'는 경기 시흥의 '서울대학로'(도로명)에 걸린다(실측) → 구까지 붙인다
    assert weather_place_query({"region": "대학로"}) == ("서울 종로구 대학로", "서울 종로구")
    assert weather_place_query({"region": "강남구"}) == ("서울 강남구", "서울 강남구")
    assert weather_place_query({"region": "서울 강남구"}) == ("서울 강남구", "서울 강남구")
    assert weather_place_query({"region": "부산"}) == ("부산", "부산")
    assert weather_place_query({"home_location": "망원역"}) == ("망원역", None)


def test_weather_picks_place_inside_expected_city():
    """실측(2026-11-20): '대학로' 검색 1위가 경북 구미의 장소 → 서울 결과를 골라야 한다."""
    from app.agent.nodes.execution import pick_in_city

    items = [{"name": "국립금오공과대학교", "address": "경북 구미시 대학로 61"},
             {"name": "CGV 배곧", "address": "경기 시흥시 배곧동 204"},
             {"name": "다이소 대학로점", "address": "서울 종로구 혜화동 180"}]
    assert pick_in_city(items, "서울 종로구")["name"] == "다이소 대학로점"
    assert pick_in_city(items, None)["name"] == "국립금오공과대학교"
    assert pick_in_city(items[:2], "서울 종로구") is None


def _venue_lookups(logs, session="s"):
    return [e for e in logs.events(session) if e["type"] == "tool.requested"
            and e["payload"]["tool"] == "get_performance_detail" and e["payload"]["args"].get("include_venue")]


def test_no_venue_lookup_when_every_candidate_fails(offline):
    """S3처럼 모두 탈락하면 공연장 좌표 조회가 0회 (좌표는 이동시간·날씨가 필요한 공연만)."""
    service, _, logs = offline
    service.chat("s", "S3")
    assert _venue_lookups(logs) == []


def test_venue_lookup_only_for_candidates_that_need_location(offline):
    service, _, logs = offline
    r = service.chat("s", S1_MESSAGE)
    lookups = _venue_lookups(logs)
    details = [e for e in logs.events("s") if e["type"] == "tool.requested"
               and e["payload"]["tool"] == "get_performance_detail" and not e["payload"]["args"].get("include_venue")]
    assert 0 < len(lookups) < len(details)
    assert all(rec["venue"]["map_url"] for rec in r["recommendations"])


# ── 계획 중 선반입: 어떤 계획이든 반드시 포함되는 '목록 → 상세'를 LLM 계획 대기 시간에 미리 조회 ──────


def test_candidates_are_prefetched_while_llm_plans(offline):
    import time as _time

    service, _, logs = offline

    def slow_planner(*_a, **_k):
        _time.sleep(0.2)  # LLM 계획 대기 흉내
        return ["search_performances", "search_places"], "후보와 집 좌표 먼저"

    service.deps.planner = slow_planner
    r = service.chat("s", S1_MESSAGE)
    events = logs.events("s")
    prefetch = [e for e in events if e["type"] == "tool.requested" and e["node"] == "plan"]
    assert {e["payload"]["tool"] for e in prefetch} == {"search_performances", "get_performance_detail"}
    searches = [e for e in events if e["type"] == "tool.requested" and e["payload"]["tool"] == "search_performances"]
    assert len(searches) == 1  # execute에서 다시 조회하지 않음
    assert r["status"] == "ok" and r["recommendations"]
    assert any("선반입" in t["label"] for t in r["trace"])


def test_replan_rounds_do_not_prefetch(offline):
    service, _, logs = offline
    service.chat("s", "S3")
    plan_tool_events = [e for e in logs.events("s") if e["type"] == "tool.requested" and e["node"] == "plan"]
    first_round_ids = {e["payload"]["args"].get("performance_id") for e in plan_tool_events}
    assert len(plan_tool_events) <= 11  # 첫 라운드(목록 1 + 상세 10)만
    later = [e for e in logs.events("s") if e["type"] == "tool.requested" and e["node"] == "execute"
             and e["payload"]["tool"] == "get_performance_detail"]
    assert later and not ({e["payload"]["args"]["performance_id"] for e in later} & first_round_ids)


def test_prefetch_not_used_for_fact_query(offline):
    service, _, logs = offline
    service.chat("s", "S7")
    assert not [e for e in logs.events("s") if e["type"] == "tool.requested" and e["node"] == "plan"]
