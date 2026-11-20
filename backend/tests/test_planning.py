"""plan 노드의 LLM 선택 검증 (순수 함수).

LLM(Claude)은 bind_tools에서 '지금 바로 실행할 수 있는 첫 단계 Tool'만 고르는 경우가 많다(실측).
→ LLM은 '어떤 Tool이 필요한가'를 결정하고, 코드는 그 선택을 조건과 대조해 검증한 뒤
  의존 관계에 따른 뒤 단계(상세·이동시간·날씨)를 채운다.
"""

import pytest

from app.agent.nodes.planning import (
    DETAIL, PLACES, SEARCH, TRANSIT, WEATHER, check_llm_selection, plan_rules,
)

HOME = {"date": "2026-11-21", "home_by": "23:30", "home_location": "망원역"}
NO_HOME = {"date": "2026-11-21", "end_by": "21:00"}


@pytest.mark.parametrize(
    ("cond", "selected"),
    [
        (HOME, [SEARCH, PLACES]),  # 실측: Claude가 고른 첫 단계
        (HOME, [SEARCH, DETAIL, PLACES, TRANSIT, WEATHER]),  # 전체 계획을 한 번에 고른 경우
        (HOME, [SEARCH, TRANSIT]),
        (NO_HOME, [SEARCH]),
        (NO_HOME, [SEARCH, DETAIL]),
    ],
)
def test_valid_selections_for_plan_request(cond, selected):
    assert check_llm_selection(selected, plan_rules("plan_request", "performance", cond)) is None


@pytest.mark.parametrize(
    ("cond", "selected", "why"),
    [
        (HOME, [SEARCH], "귀가"),  # 귀가 조건이 있는데 이동시간 계산을 고르지 않음
        (NO_HOME, [SEARCH, PLACES], "필요 없는"),  # 귀가 조건이 없는데 집 위치·이동시간 Tool
        (NO_HOME, [SEARCH, TRANSIT], "필요 없는"),
        (HOME, [DETAIL, PLACES], "search_performances"),  # 공연 ID 없이 상세 조회
        (HOME, [], "고르지 않음"),
    ],
)
def test_invalid_selections_for_plan_request(cond, selected, why):
    reason = check_llm_selection(selected, plan_rules("plan_request", "performance", cond))
    assert reason and why in reason


def test_completed_plan_follows_dependency_order():
    assert plan_rules("plan_request", "performance", HOME).template == [SEARCH, DETAIL, PLACES, TRANSIT, WEATHER]
    assert plan_rules("plan_request", "performance", NO_HOME).template == [SEARCH, DETAIL, WEATHER]


def test_weather_only_request_excludes_performance_tools():
    rules = plan_rules("fact_query", "weather", {"date": "2026-11-21", "region": "대학로"})
    assert rules.template == [PLACES, WEATHER]
    assert check_llm_selection([PLACES], rules) is None
    assert check_llm_selection([SEARCH, PLACES], rules) is not None


def test_fact_query_needs_search_and_no_extra_tools():
    rules = plan_rules("fact_query", "performance", {"keyword": "아일랜드"})
    assert rules.template == [SEARCH, DETAIL]
    assert check_llm_selection([SEARCH], rules) is None
    assert check_llm_selection([SEARCH, WEATHER], rules) is not None
