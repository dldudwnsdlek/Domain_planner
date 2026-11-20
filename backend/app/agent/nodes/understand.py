"""analyze(LLM) · clarify · respond_simple · save_plan 노드."""

from __future__ import annotations

import re
import time
from datetime import date, timedelta

from app.agent.deps import Deps
from app.agent.nodes.common import basic_response, show_of
from app.events.types import LLM_DECISION
from app.llm import llm_error_code
from app.tools.base import ToolError
from app.tools.region_alias import resolve_region

MAX_DAYS_AHEAD = 90
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")

QUESTIONS = {
    "home_location": "귀가 시간을 계산하려면 집(또는 도착할 곳) 위치가 필요해요. 어디로 가시나요? (예: 망원역)",
    "region_ambiguous": "말씀하신 지역이 여러 곳에 있어요. 어느 시·도인지 알려 주세요. (예: 서울 중구)",
    "region_unknown": "지역을 찾지 못했어요. 서울의 구 이름이나 '대학로'처럼 알려 주세요.",
    "date_range": f"날짜는 오늘부터 {MAX_DAYS_AHEAD}일 안으로 알려 주세요.",
    "keyword": "어떤 작품을 찾으시나요? 작품명을 알려 주세요.",
    "selection": "저장할 추천 번호를 알려 주세요. (예: 1번 저장해줘)",
    "home_ambiguous": "집 위치가 여러 곳으로 검색돼요. 지역을 함께 알려 주세요. (예: 서울 망원역)",
    "home_unresolved": "집(도착할 곳) 위치를 지도에서 찾지 못했어요. 역 이름이나 동 이름으로 알려 주세요. (예: 망원역)",
}

HELP_TEXT = (
    "안녕하세요! 커튼콜 플래너는 시간·예산·귀가 조건에 맞는 공연과 회차를 찾아 드려요.\n"
    "이렇게 말해 보세요:\n"
    "· “11월 21일 토요일 저녁 6시 이후 대학로 연극, 밤 11시 반까지 망원역 도착, 5만원 이하”\n"
    "· “같은 날 뮤지컬로 바꿔줘” (나머지 조건은 그대로 유지돼요)\n"
    "· “1번 저장해줘” → [내 관람 계획]에서 확인·수정할 수 있어요"
)


def _clean(mentioned: dict, today: date) -> tuple[dict, list[str]]:
    """LLM이 뽑은 값을 코드로 검증한다. 형식이 틀린 값은 버리고, 범위 밖 날짜는 되묻는다."""
    cleaned, missing = {}, []
    for key, value in mentioned.items():
        if key == "date":
            try:
                d = date.fromisoformat(value)
            except ValueError:
                missing.append("date_range")
                continue
            if not (today <= d <= today + timedelta(days=MAX_DAYS_AHEAD)):
                missing.append("date_range")
                continue
            cleaned[key] = d.isoformat()
        elif key in ("start_after", "end_by", "home_by"):
            m = _TIME.match(str(value).strip())
            if m and int(m.group(1)) <= 24 and int(m.group(2)) < 60:
                cleaned[key] = f"{int(m.group(1)) % 24:02d}:{m.group(2)}"
        elif key == "budget_max":
            if isinstance(value, int) and value >= 0:
                cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned, missing


def analyze(state: dict, deps: Deps) -> dict:
    today = deps.now().date()
    previous = dict(state.get("conditions") or {})
    last = state.get("last_recommendations") or []
    if deps.analyzer is None:
        return {"fatal": {"code": "LLM_UNAVAILABLE", "message": "LLM이 설정되지 않아 요청을 분석할 수 없어요."},
                "_summary": "LLM 없음"}
    try:
        deps.count_llm(state)
        out = deps.analyzer(state["message"], today=today, conditions=previous, last_count=len(last))
    except Exception as exc:  # noqa: BLE001 — LLM 실패는 코드로만 기록
        code = llm_error_code(exc)
        return {"fatal": {"code": "LLM_UNAVAILABLE", "detail": code,
                          "message": f"LLM 연결에 실패해 요청을 분석하지 못했어요. ({code})"},
                "_summary": f"LLM 실패 {code}"}

    deps.emit(state, LLM_DECISION, "analyze", kind="intent", value=out.intent, reason=out.reason)
    mentioned = {k: v for k, v in out.conditions.model_dump().items() if v is not None}
    cleaned, missing = _clean(mentioned, today)
    conditions = ({} if out.reset else previous) | cleaned
    defaults: list[str] = []

    if out.intent in ("plan_request", "fact_query"):
        if out.intent == "plan_request" or out.topic == "weather":
            if not conditions.get("date"):
                conditions["date"] = today.isoformat()
                defaults.append(f"날짜를 말하지 않아 오늘({today.isoformat()}) 기준으로 찾았어요.")
        if out.intent == "plan_request" and conditions.get("home_by") and not conditions.get("home_location"):
            missing.append("home_location")
        if conditions.get("region"):
            try:
                resolve_region(conditions["region"])
            except ToolError as exc:
                missing.append("region_ambiguous" if exc.code == "AMBIGUOUS" else "region_unknown")
        if out.intent == "fact_query" and out.topic != "weather" and not conditions.get("keyword"):
            missing.append("keyword")
    if out.intent == "plan_save" and not (out.selection and 1 <= out.selection <= len(last)):
        missing.append("selection")

    keep = out.intent in ("plan_request", "fact_query")
    return {
        "intent": out.intent, "topic": out.topic or "performance", "intent_reason": out.reason,
        "selection": out.selection, "conditions": conditions if keep else previous,
        "defaults_applied": defaults, "missing": list(dict.fromkeys(missing)),
        "_summary": out.intent,
    }


def route_after_analyze(state: dict) -> str:
    if state.get("fatal"):
        return "respond"
    if state.get("missing"):
        return "clarify"
    if state["intent"] in ("chitchat", "calendar_register"):
        return "respond_simple"
    if state["intent"] == "plan_save":
        return "save_plan"
    return "plan"


def clarify(state: dict, deps: Deps) -> dict:
    started = time.monotonic()
    questions = [QUESTIONS.get(m, m) for m in state.get("missing", [])]
    resp = basic_response(state, deps, status="clarify", reply="\n".join(questions),
                          final_step=("되묻기 — Tool 호출 전", started))
    return {"response": resp, "_summary": ", ".join(state.get("missing", []))}


def respond_simple(state: dict, deps: Deps) -> dict:
    started = time.monotonic()
    if state.get("intent") == "calendar_register":
        reply = "캘린더 등록은 아직 지원하지 않아요. [내 관람 계획]에서 저장한 계획을 확인할 수 있어요."
    else:
        reply = HELP_TEXT
    resp = basic_response(state, deps, status="ok", reply=reply, final_step=("간단 응답 — Tool 0회", started))
    return {"response": resp, "_summary": "Tool 0회"}


def save_plan(state: dict, deps: Deps) -> dict:
    """직전 추천 중 선택한 항목을 저장한다. LLM이 아니라 코드가 저장소에서 값을 꺼내 쓴다(지어내기 방지)."""
    started = time.monotonic()
    rec = (state.get("last_recommendations") or [])[state["selection"] - 1]
    show = show_of(rec)
    plan = {
        "performance_id": rec["performance_id"], "title": rec["title"], "venue_name": rec["venue"]["name"],
        "venue_address": rec["venue"].get("address"), "date": rec["date"], "start_time": show["start"],
        "end_time": show.get("end"), "price": rec.get("min_price"),
        "ticket_url": (rec.get("ticket_links") or [{}])[0].get("url"), "session_id": state["session_id"],
    }
    saved, overlaps = deps.plans_repo.create(plan)
    reply = f"‘{saved['title']}’ {saved['date']} {saved['start_time']}~{saved['end_time'] or '?'} 계획을 저장했어요."
    if overlaps:
        listed = ", ".join(f"{o['start_time']}~{o['end_time'] or '?'} ‘{o['title']}’" for o in overlaps)
        reply += f"\n같은 날 {listed} 계획과 시간이 겹쳐요. (저장은 했어요)"
    resp = basic_response(state, deps, status="ok", reply=reply,
                          final_step=(f"계획 저장 — 겹침 {len(overlaps)}건", started))
    resp["saved_plan"], resp["overlaps"] = saved, overlaps
    return {"response": resp, "_summary": f"plan #{saved['id']} · 겹침 {len(overlaps)}"}
