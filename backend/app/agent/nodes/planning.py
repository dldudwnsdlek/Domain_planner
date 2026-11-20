"""plan(첫 계획만 LLM + 규칙 검증) · replan(규칙 사다리) 노드."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.agent.deps import Deps
from app.agent.nodes.common import DETAIL, PLACES, SEARCH, TRANSIT, WEATHER  # noqa: F401 (다른 모듈·테스트도 여기서 씀)
from app.agent.nodes.execution import fetch_round, weather_place_query
from app.agent.relax import next_relaxation
from app.agent.worker import build_tasks
from app.events.types import LLM_DECISION, PLAN_FALLBACK, REPLAN_TRIGGERED, TASKS_PLANNED


@dataclass(frozen=True)
class PlanRules:
    template: list[str]  # 의존 순서대로 완성한 실행 계획 (규칙)
    required_any: list[set[str]]  # 각 묶음에서 하나 이상은 LLM이 골라야 함
    allowed: set[str]  # LLM이 골라도 되는 Tool


def plan_rules(intent: str, topic: str | None, cond: dict) -> PlanRules:
    """요청 종류와 조건으로 '필요한 Tool'의 규칙을 만든다.

    - 날씨만 묻는 요청: 장소 검색 → 날씨 (공연 Tool 제외)
    - 사실 조회: 검색 → 상세 (판정·이동시간·날씨 없음)
    - 관람 계획: 검색 → 상세 (+ 귀가 조건이 있으면 집 위치 → 이동시간) → 날씨(최종 추천에만)
    """
    if intent == "fact_query" and topic == "weather":
        return PlanRules([PLACES, WEATHER], [{PLACES, WEATHER}], {PLACES, WEATHER})
    if intent == "fact_query":
        return PlanRules([SEARCH, DETAIL], [{SEARCH}], {SEARCH, DETAIL})
    template, required_any = [SEARCH, DETAIL], [{SEARCH}]
    if cond.get("home_by"):
        template += [PLACES, TRANSIT]
        required_any.append({PLACES, TRANSIT})
    template.append(WEATHER)
    return PlanRules(template, required_any, set(template))


def check_llm_selection(selected: list[str], rules: PlanRules) -> str | None:
    """LLM이 고른 Tool이 규칙에 맞으면 None, 아니면 이유. 첫 단계만 골라도 필요한 판단이 맞으면 통과."""
    chosen = set(selected)
    if not chosen:
        return "LLM이 Tool을 고르지 않음"
    extra = chosen - rules.allowed
    if extra:
        return f"이번 요청에 필요 없는 Tool을 고름: {', '.join(sorted(extra))}"
    for group in rules.required_any:
        if not chosen & group:
            if group == {PLACES, TRANSIT}:
                return "귀가 조건이 있는데 집 위치·이동시간 Tool을 고르지 않음"
            return f"필수 시작 Tool이 빠짐: {' 또는 '.join(sorted(group))}"
    return None


def _decide_plan(state: dict, deps: Deps, rules: PlanRules, cond: dict) -> dict:
    """첫 계획: LLM이 필요한 Tool을 고르고, 코드가 검증·보완한다. 실패하면 규칙 템플릿."""
    reason, selected = None, []
    if deps.planner is not None:
        try:
            deps.count_llm(state)
            tools, llm_reason = deps.planner(state["message"], conditions=cond,
                                             tool_specs=deps.registry.openai_specs())
            selected = list(dict.fromkeys(tools))
            reason = check_llm_selection(selected, rules)
            if reason is None:
                completed = [t for t in rules.template if t not in selected]
                deps.emit(state, LLM_DECISION, "plan", kind="plan", value=rules.template,
                          llm_selected=selected, completed_by_rule=completed, reason=llm_reason)
                return {"plan": [{"tool": t, "reason": llm_reason if t in selected else "의존 순서 보완(규칙)"}
                                 for t in rules.template],
                        "_summary": f"LLM 선택 {', '.join(selected)}" + (" + 규칙 보완" if completed else "")}
        except Exception:  # noqa: BLE001 — LLM 실패는 규칙 템플릿으로 대체
            reason = "LLM 계획 호출 실패"
    deps.emit(state, PLAN_FALLBACK, "plan", reason=reason or "LLM 계획기 없음", llm_selected=selected,
              value=rules.template)
    return {"plan": [{"tool": t, "reason": "규칙 템플릿"} for t in rules.template], "_summary": "규칙 템플릿"}


def _tasks_for(state: dict, deps: Deps, tools: list[str], query: dict) -> list[dict]:
    """(F3021 구성 B·C) Planner의 작업 목록. 구성 A(단일 Agent)는 만들지 않는다."""
    if deps.mode == "A":
        return []
    cond = state["conditions"]
    weather_query = weather_place_query(cond)[0] if state.get("topic") == "weather" else None
    return build_tasks(state["intent"], state.get("topic"), cond, tools, query, today=deps.now().date(),
                       weather_query=weather_query)


def _with_tasks(state: dict, deps: Deps, decided: dict, query: dict, reason: str) -> dict:
    tasks = _tasks_for(state, deps, [p["tool"] for p in decided["plan"]], query)
    if not tasks:
        return decided
    deps.emit(state, TASKS_PLANNED, "plan", tasks=tasks, reason=reason)
    fixed = sorted({f for t in tasks for f in t.get("fixed", [])})
    return {**decided, "tasks": tasks, "_summary": f"{decided['_summary']} · 작업 {len(tasks)}개(고정: {', '.join(fixed)})"}


def plan(state: dict, deps: Deps) -> dict:
    cond = state["conditions"]
    rules = plan_rules(state["intent"], state.get("topic"), cond)
    if state.get("replan_count", 0) > 0:
        # 재계획은 Tool 구성이 같고 인자만 바뀐다 → 규칙 템플릿 (LLM 0회, 선반입 없음)
        decided = {"plan": state["plan"] or [{"tool": t, "reason": "재계획 규칙"} for t in rules.template],
                   "_summary": "규칙 템플릿(재계획)"}
        return _with_tasks(state, deps, decided, state["query"], "재계획: 넓힌 선호 조건을 작업 인자에 반영")

    query = {"region": cond.get("region"), "genre": cond.get("genre"), "page": 1,
             "has_more": False, "region_relaxed": False, "genre_relaxed": False}
    if state["intent"] != "plan_request":
        return {"query": query, **_with_tasks(state, deps, _decide_plan(state, deps, rules, cond), query, "첫 계획")}

    # 관람 계획은 어떤 계획이든 '목록 → 상세'가 반드시 들어간다(규칙 검증의 필수 Tool).
    # 그래서 LLM이 계획하는 동안 첫 라운드 후보를 미리 조회한다 — LLM 결정 권한은 그대로, 순서만 겹친다.
    first_tasks = _tasks_for(state, deps, rules.template, query)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fetch_round, {**state, "query": query, "tasks": first_tasks}, deps, query, "plan")
        decided = _with_tasks(state, deps, _decide_plan(state, deps, rules, cond), query, "첫 계획")
        prefetched = future.result()
    return {"query": query, **prefetched, **decided, "prefetched": not prefetched.get("fatal")}


def replan(state: dict, deps: Deps) -> dict:
    step = next_relaxation(state["query"], state["conditions"], len(state.get("pending_ids") or []))
    count = state.get("replan_count", 0) + 1
    deps.emit(state, REPLAN_TRIGGERED, "replan", count=count, step=step["step"], relaxed=step["relaxed"],
              reason=f"통과 0건 · {step['reason']}")
    log = state.get("replan_log", []) + [{"step": step["step"], "relaxed": step["relaxed"], "reason": step["reason"]}]
    return {"replan_count": count, "query": step["query"], "replan_log": log,
            "_summary": f"{count}회 {step['step']} {', '.join(f'{v}' for v in step['relaxed'].values())}"}
