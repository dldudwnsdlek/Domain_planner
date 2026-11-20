"""respond 노드: 숫자는 템플릿이 쓰고, LLM은 요약 1~2문장만 쓴다.

LLM 요약에 들어간 숫자가 구조화된 결과에 없는 값이면 요약을 버리고 템플릿 문장을 쓴다(지어내기 방지).
"""

from __future__ import annotations

import json
import re
import time

from app.agent.constraints import PASS, count_fail_reasons, suggest_adjustments
from app.agent.deps import Deps
from app.agent.nodes.common import ASSUMPTIONS, basic_response, eval_from_dict
from app.agent.constraints import weekday_key

DAY_KO = {"mon": "월", "tue": "화", "wed": "수", "thu": "목", "fri": "금", "sat": "토", "sun": "일"}
REASON_LABEL = {
    "OVER_BUDGET": "예산 초과", "END_TOO_LATE": "종료 시각 초과", "HOME_TOO_LATE": "귀가 시각 초과",
    "START_TOO_EARLY": "시작 시각 이전", "NO_SHOW_ON_DAY": "그 요일 공연 없음", "OUT_OF_PERIOD": "공연 기간 아님",
    "NO_RUNTIME": "러닝타임 정보 없음", "SCHEDULE_UNPARSED": "회차 해석 불가", "PRICE_UNPARSED": "가격 해석 불가",
    "NO_TRANSIT": "이동시간 확인 불가", "NO_PERIOD": "공연 기간 정보 없음",
}
SUGGESTION_TEXT = {
    "budget_max": lambda v, c: f"예산을 {v:,}원으로 올리면 {c}편이 가능해요.",
    "end_by": lambda v, c: f"종료 제한을 {v}로 늦추면 {c}편이 가능해요.",
    "home_by": lambda v, c: f"귀가 시각을 {v}로 늦추면 {c}편이 가능해요.",
    "start_after": lambda v, c: f"시작 시각을 {v} 이후로 당기면 {c}편이 가능해요.",
}


def _reason_text(ev, cond: dict) -> str:
    code = ev.reasons[0] if ev.reasons else ""
    texts = {
        "OUT_OF_PERIOD": "그날은 공연 기간이 아니에요",
        "NO_PERIOD": "공연 기간 정보가 없어요",
        "NO_SHOW_ON_DAY": "그 요일에는 공연이 없어요",
        "START_TOO_EARLY": f"{cond.get('start_after')} 이후에 시작하는 회차가 없어요",
        "END_TOO_LATE": f"{cond.get('end_by')}까지 끝나는 회차가 없어요",
        "HOME_TOO_LATE": f"{cond.get('home_by')}까지 {cond.get('home_location') or '집'}에 도착할 수 있는 회차가 없어요",
        "OVER_BUDGET": f"최저가 {ev.min_price:,}원이 예산({cond.get('budget_max', 0):,}원)을 넘어요" if ev.min_price else "예산을 넘어요",
        "NO_RUNTIME": "러닝타임 정보가 없어 종료 시각을 계산할 수 없어요",
        "NO_TRANSIT": "귀가 이동시간을 확인하지 못했어요",
        "PRICE_UNPARSED": "가격 정보를 해석하지 못했어요",
        "SCHEDULE_UNPARSED": "회차 정보를 해석하지 못했어요",
    }
    text = texts.get(code, "조건에 맞지 않아요")
    if code == "SCHEDULE_UNPARSED" and ev.latest_start:
        text += f". {ev.latest_start} 이전에 시작하는 회차라면 조건을 지킬 수 있어요"
    return text


def _recommendation(state: dict, pid: str, ev) -> dict:
    d, cond = state["details"][pid], state["conditions"]
    info = (state.get("enriched") or {}).get(pid, {})
    transit = (state.get("transit") or {}).get(d["venue"].get("venue_id"))
    shows = [s for s in ev.showtimes if s.verdict == PASS]
    evidence = []
    if d.get("runtime_min"):
        evidence.append(f"KOPIS 러닝타임 {d['runtime_min']}분")
    evidence.append(f"{DAY_KO[weekday_key(cond['date'])]} {shows[0].start} 회차")
    if d.get("min_price") is not None:
        evidence.append(f"최저가 {d['min_price']:,}원")
    if transit:
        evidence.append(f"카카오 대중교통 {transit['total_min']}분" + (" (도보 추정)" if transit.get("issues") else ""))
    if info.get("weather", {}).get("status") == "ok":
        evidence.append("기상청 단기예보")
    return {
        "performance_id": pid, "title": d["title"], "genre": d.get("genre"), "poster_url": d.get("poster_url"),
        "venue": {"name": d["venue"].get("name"), "address": d["venue"].get("address"), "map_url": info.get("map_url")},
        "date": cond["date"],
        "showtimes": [{"start": s.start, "end": s.end, "home_arrival": s.home_arrival, "verdict": s.verdict} for s in shows],
        "min_price": d.get("min_price"), "price_raw": d.get("price_raw"), "age_rating": d.get("age_rating"),
        "ticket_links": d.get("ticket_links", []),
        "transit": {"total_min": transit["total_min"], "summary": transit.get("summary"), "map_url": transit.get("map_url")}
        if transit else None,
        "weather": info.get("weather", {"status": "unavailable", "summary": None}),
        "evidence": evidence,
    }


def _cond_text(cond: dict) -> str:
    parts = [cond.get("date"), cond.get("start_after") and f"{cond['start_after']} 이후 시작", cond.get("region"),
             cond.get("genre"), cond.get("end_by") and f"{cond['end_by']}까지 종료",
             cond.get("home_by") and f"{cond['home_by']}까지 {cond.get('home_location') or '집'} 도착",
             cond.get("budget_max") is not None and f"{cond['budget_max']:,}원 이하"]
    return " · ".join(p for p in parts if p)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*", text)}


def _summary(state: dict, deps: Deps, facts: dict, template: str) -> tuple[str, str]:
    """(응답 문장, 만든 방법). LLM 요약에 결과에 없는 숫자가 있으면 버리고 템플릿을 쓴다."""
    if deps.summarizer is None:
        return template, "템플릿"
    facts = {k: v for k, v in facts.items() if v not in (None, "", [], {})}  # 빈 항목은 요약에 넘기지 않음
    try:
        deps.count_llm(state)
        text = deps.summarizer(facts)
    except Exception:  # noqa: BLE001 — 요약 실패는 템플릿으로 대체
        return template, "템플릿(LLM 실패)"
    allowed = _numbers(json.dumps(facts, ensure_ascii=False)) | _numbers(template)
    if not text or not _numbers(text) <= allowed:
        return template, "템플릿(요약 숫자 불일치)"
    return text, "LLM 요약"


def respond(state: dict, deps: Deps) -> dict:
    started = time.monotonic()
    cond = state.get("conditions") or {}
    if state.get("fatal"):
        fatal = state["fatal"]
        resp = basic_response(state, deps, status="error", reply=fatal["message"], final_step=("응답 생성 — 오류 안내", started))
        if fatal["code"] == "LLM_UNAVAILABLE":
            resp["warnings"] = resp["warnings"] + [{"code": "LLM_UNAVAILABLE", "service": "LLM(GMS)",
                                                    "message": "LLM(GMS) 연결을 확인해 주세요. 공연 검색·판정은 코드로 동작하지만 요청 분석에 LLM이 필요해요."}]
        return {"response": resp}

    if state["intent"] == "fact_query":
        facts = state.get("facts") or {}
        if facts.get("kind") == "weather":
            template = (f"{facts['place']} {facts['date']} 예보: {facts['summary']}" if facts.get("found")
                        else facts.get("message", "날씨를 확인하지 못했어요."))
        else:
            template = (f"‘{facts['title']}’ 정보를 찾았어요." if facts.get("found")
                        else facts.get("message", "정보를 찾지 못했어요."))
        reply, how = _summary(state, deps, facts, template)
        resp = basic_response(state, deps, status="ok", reply=reply, final_step=(f"응답 생성 — {how}", started))
        resp["assumptions"] = (["예보는 발표 시각 기준이며 바뀔 수 있어요"] if facts.get("kind") == "weather"
                               else ASSUMPTIONS)
        return {"response": resp}

    evs = {e["performance_id"]: eval_from_dict(e) for e in state.get("evaluations", [])}
    ranked = state.get("ranked_ids") or []
    recs = [_recommendation(state, pid, evs[pid]) for pid in ranked]
    excluded = [{"performance_id": pid, "title": ev.title, "reason_code": ev.reasons[0] if ev.reasons else None,
                 "reason": _reason_text(ev, cond)} for pid, ev in evs.items() if ev.verdict != PASS]
    excluded += state.get("excluded_pre", [])
    assumptions = list(ASSUMPTIONS)
    if cond.get("home_by"):
        assumptions = [f"퇴장 여유 {deps.exit_buffer}분 포함", "대중교통 시간은 시간대·막차 미반영"] + assumptions
    pass_overflow = sum(1 for e in evs.values() if e.verdict == PASS) - len(recs)

    if recs:
        status = "ok"
        template = f"조건({_cond_text(cond)})에 맞는 공연 {len(recs)}편을 찾았어요."
        if pass_overflow > 0:
            template += f" (조건을 통과한 공연 중 상위 {len(recs)}편)"
        suggestions = []
    else:
        status = "limit_reached"
        stats = count_fail_reasons(list(evs.values()))
        stat_text = " · ".join(f"{REASON_LABEL.get(k, k)} {v}" for k, v in sorted(stats.items(), key=lambda x: -x[1]))
        template = f"조건에 맞는 공연을 찾지 못했어요 (재계획 {state.get('replan_count', 0)}회)."
        if stats:
            template += f"\n탈락 {sum(stats.values())}편: {stat_text}"
        suggestions = [{"field": s["field"], "value": s["value"], "count": s["count"],
                        "text": SUGGESTION_TEXT[s["field"]](s["value"], s["count"])}
                       for s in suggest_adjustments(list(evs.values()))]
        if suggestions:
            template += "\n조건을 바꿔 볼까요?"

    facts = {"status": status, "조건": _cond_text(cond), "추천 수": len(recs), "제외 수": len(excluded),
             "재계획 횟수": state.get("replan_count", 0),
             "추천": [{"제목": r["title"], "시작": r["showtimes"][0]["start"], "종료": r["showtimes"][0]["end"],
                     "도착": r["showtimes"][0]["home_arrival"], "최저가": r["min_price"]} for r in recs],
             "조정안": [s["text"] for s in suggestions]}
    reply, how = (template, "템플릿") if status == "limit_reached" else _summary(state, deps, facts, template)
    resp = basic_response(state, deps, status=status, reply=reply, final_step=(f"응답 생성 — {how}", started))
    resp.update({"recommendations": recs, "excluded": excluded, "suggestions": suggestions, "assumptions": assumptions})
    history = (state.get("history") or [])[-5:] + [{"user": state["message"], "status": status,
                                                    "titles": [r["title"] for r in recs]}]
    return {"response": resp, "last_recommendations": recs, "history": history}
