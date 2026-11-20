"""LangGraph 그래프 조립.

START → analyze ─(chitchat)→ respond_simple → END
                ├(조건 부족·AMBIGUOUS)→ clarify → END
                ├(plan_save)→ save_plan → END
                └→ plan → execute ─(fact_query)→ respond → END
                              └→ judge ─(통과 ≥ 1)→ enrich → respond → END
                                       ├(통과 0 · 완화 가능 · 상한 미만)→ replan → plan
                                       └(상한·완화 불가·치명적 실패)→ respond(limit) → END
Memory: MemorySaver(thread_id = session_id) — 조건·직전 추천·최근 대화가 다음 메시지로 이어진다.
"""

from __future__ import annotations

import time

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.deps import Deps
from app.agent.nodes import execution, planning, respond, understand
from app.agent.state import AgentState
from app.events.types import NODE_ENTERED, NODE_EXITED


def _traced(deps: Deps, name: str, fn):
    """노드 진입·종료 이벤트(소요 시간, 요약)를 발행하는 감싸개."""
    def node(state: dict) -> dict:
        deps.emit(state, NODE_ENTERED, name)
        started = time.monotonic()
        update = fn(state, deps) or {}
        summary = update.pop("_summary", None)
        deps.emit(state, NODE_EXITED, name, elapsed_ms=int((time.monotonic() - started) * 1000), summary=summary,
                  ok=not update.get("fatal"))
        return update
    return node


def build_graph(deps: Deps, checkpointer=None):
    g = StateGraph(AgentState)
    nodes = {
        "analyze": understand.analyze, "clarify": understand.clarify, "respond_simple": understand.respond_simple,
        "save_plan": understand.save_plan, "plan": planning.plan, "replan": planning.replan,
        "execute": execution.execute, "judge": execution.judge, "enrich": execution.enrich,
        "respond": respond.respond,
    }
    for name, fn in nodes.items():
        g.add_node(name, _traced(deps, name, fn))

    g.add_edge(START, "analyze")
    g.add_conditional_edges("analyze", understand.route_after_analyze,
                            ["respond", "clarify", "respond_simple", "save_plan", "plan"])
    g.add_edge("plan", "execute")
    g.add_conditional_edges("execute", execution.route_after_execute, ["clarify", "respond", "judge"])
    g.add_conditional_edges("judge", lambda s: s["route"], ["enrich", "replan", "respond"])
    g.add_edge("replan", "plan")
    g.add_edge("enrich", "respond")
    for terminal in ("respond", "clarify", "respond_simple", "save_plan"):
        g.add_edge(terminal, END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
