"""노드 공통 도우미: 판정 결과 변환, 실행 과정(trace), 기본 응답 형식."""

from __future__ import annotations

import time
from dataclasses import asdict

from app.agent.constraints import Conditions, PerformanceEval, ShowtimeEval
from app.events.types import NODE_EXITED, TOOL_RESPONDED, WORKER_DECISION, WORKER_REJECTED

SEARCH, DETAIL, PLACES, TRANSIT, WEATHER = (
    "search_performances", "get_performance_detail", "search_places", "get_transit_time", "get_weather")

ASSUMPTIONS = ["가격·회차는 변동될 수 있으니 예매처에서 최종 확인하세요"]
SOURCES = ["출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)", "카카오맵", "기상청 단기예보(공공누리 제1유형)"]

NODE_LABELS = {
    "analyze": "요청 분석", "plan": "계획 수립", "execute": "Tool 실행", "judge": "판정", "replan": "재계획",
    "enrich": "날씨·지도 추가", "clarify": "되묻기", "respond_simple": "간단 응답", "save_plan": "계획 저장",
}
TOOL_LABELS = {
    "search_performances": "공연 목록 조회", "get_performance_detail": "공연 상세", "search_places": "장소 검색",
    "get_transit_time": "이동시간", "get_weather": "날씨 조회", "venue_lookup": "공연장 좌표",
}


def to_conditions(cond: dict) -> Conditions:
    return Conditions(date=cond["date"], start_after=cond.get("start_after"), end_by=cond.get("end_by"),
                      home_by=cond.get("home_by"), budget_max=cond.get("budget_max"))


def eval_to_dict(ev: PerformanceEval) -> dict:
    return asdict(ev)


def eval_from_dict(d: dict) -> PerformanceEval:
    return PerformanceEval(**{**d, "showtimes": [ShowtimeEval(**s) for s in d["showtimes"]]})


def show_of(rec: dict) -> dict:
    """추천 카드의 대표 회차: 통과한 첫 회차."""
    shows = rec.get("showtimes") or []
    return next((s for s in shows if s.get("verdict") == "PASS"), shows[0] if shows else {})


def build_trace(events) -> list[dict]:
    """이번 실행의 이벤트로 화면용 실행 과정을 만든다. Tool 호출은 단계별로 묶어 건수만 보여 준다."""
    trace, tool_counts, failures = [], {}, []
    actions = {"retry": "인자를 고쳐 재시도", "skip": "건너뜀", "request_replan": "Planner에게 넘김"}
    for ev in events:
        if ev.type == WORKER_DECISION:
            p = ev.payload
            changed = ", ".join(f"‘{c['value']}’" for c in p.get("changes") or [])
            label = (f"Worker — {TOOL_LABELS.get(p['tool'], p['tool'])} {p['code']} → {actions.get(p['action'], p['action'])}"
                     f"{' ' + changed if changed else ''} ({'LLM' if p['by'] == 'llm' else '규칙'}: {p['reason']})")
            trace.append({"seq": ev.seq, "label": label, "elapsed_ms": None, "is_replan": False, "ok": True})
            continue
        if ev.type == WORKER_REJECTED:
            trace.append({"seq": ev.seq, "label": f"Worker — 인자 변경 거부: {ev.payload['reason']}",
                          "elapsed_ms": None, "is_replan": False, "ok": False})
            continue
        if ev.type == TOOL_RESPONDED:
            tool = ev.payload["tool"]
            if tool == "get_performance_detail" and (ev.payload.get("args") or {}).get("include_venue"):
                tool = "venue_lookup"  # 같은 Tool이지만 '공연장 좌표' 조회로 따로 보여 준다
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
            if not ev.payload["ok"]:
                failures.append((ev.payload["tool"], ev.payload["code"]))
        elif ev.type == NODE_EXITED and ev.node in NODE_LABELS:
            label = NODE_LABELS[ev.node]
            summary = ev.payload.get("summary")
            counts = " · ".join(f"{TOOL_LABELS.get(t, t)} ×{n}" for t, n in tool_counts.items())
            if ev.node in ("execute", "enrich") and tool_counts:
                summary = counts if not summary or summary.startswith("상세") else f"{summary} · {counts}"
                if (ev.payload.get("summary") or "").endswith("(계획 중 선반입)"):
                    summary = f"{counts} (후보는 계획 중 선반입)" if counts else "후보는 계획 중 선반입"
            elif ev.node == "plan" and tool_counts:
                summary = f"{summary} · 동시에 후보 선반입: {counts}"
            trace.append({"seq": ev.seq, "label": f"{label} — {summary}" if summary else label,
                          "elapsed_ms": ev.payload.get("elapsed_ms"), "is_replan": ev.node == "replan",
                          "ok": ev.payload.get("ok", True)})
            for tool, code in failures:
                trace.append({"seq": ev.seq, "label": f"{TOOL_LABELS.get(tool, tool)} 실패 ({code})",
                              "elapsed_ms": None, "is_replan": False, "ok": False})
            tool_counts, failures = {}, []
    return trace


def understood(state: dict) -> dict:
    cond = state.get("conditions") or {}
    keys = ("date", "start_after", "region", "genre", "keyword", "end_by", "home_by", "home_location", "budget_max")
    return {k: cond[k] for k in keys if cond.get(k) is not None}


def basic_response(state: dict, deps, *, status: str, reply: str, final_step: tuple[str, float] | None = None) -> dict:
    """응답 기본 형식. final_step=(단계 이름, 시작 시각)이면 지금 단계(응답 생성 등)를 실행 과정 끝에 붙인다.

    지금 실행 중인 노드의 node.exited 이벤트는 응답을 만든 뒤에 발행되므로 여기서 직접 붙인다.
    """
    events = deps.emitter(state).events
    trace = build_trace(events)
    if final_step:
        label, started = final_step
        trace.append({"seq": (events[-1].seq if events else 0) + 1, "label": label,
                      "elapsed_ms": int((time.monotonic() - started) * 1000), "is_replan": False, "ok": True})
    return {
        "session_id": state["session_id"], "run_id": state["run_id"], "status": status, "reply": reply,
        "understood": understood(state), "defaults_applied": state.get("defaults_applied", []),
        "recommendations": [], "excluded": [], "suggestions": [], "facts": state.get("facts"),
        "assumptions": [], "sources": SOURCES, "trace": trace,
        "replan_count": state.get("replan_count", 0), "warnings": state.get("warnings", []),
    }
