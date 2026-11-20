"""LLM을 쓰는 세 단계(analyze · plan · respond)의 실제 구현.

Agent 노드는 이 클래스들을 '주입'받아 쓴다. 테스트·오프라인 실행에서는 같은 모양의 가짜 객체를 넣는다.
LLM 객체는 app.llm.get_llm()/get_structured_llm()에서만 만든다.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import ANALYZE_SYSTEM, PLAN_SYSTEM, RESPOND_SYSTEM, WORKER_SYSTEM
from app.agent.state import AnalyzeOutput, WorkerDecision
from app.llm import get_llm, get_structured_llm

WEEKDAYS = "월화수목금토일"


class LLMAnalyzer:
    def __call__(self, message: str, *, today, conditions: dict, last_count: int) -> AnalyzeOutput:
        system = ANALYZE_SYSTEM.format(today=today.isoformat(), weekday=WEEKDAYS[today.weekday()] + "요일",
                                       conditions=json.dumps(conditions, ensure_ascii=False), last_count=last_count)
        return get_structured_llm(AnalyzeOutput, "analyze").invoke(
            [SystemMessage(system), HumanMessage(message)])


class LLMPlanner:
    def __call__(self, message: str, *, conditions: dict, tool_specs: list[dict]) -> tuple[list[str], str]:
        llm = get_llm("plan").bind_tools(tool_specs)
        reply = llm.invoke([SystemMessage(PLAN_SYSTEM),
                            HumanMessage(f"요청: {message}\n조건: {json.dumps(conditions, ensure_ascii=False)}")])
        tools = [call["name"] for call in (reply.tool_calls or [])]
        reason = reply.content if isinstance(reply.content, str) else ""
        return tools, reason.strip()


class LLMSummarizer:
    def __call__(self, facts: dict) -> str:
        reply = get_llm("respond").invoke(
            [SystemMessage(RESPOND_SYSTEM), HumanMessage(json.dumps(facts, ensure_ascii=False))])
        return reply.content.strip() if isinstance(reply.content, str) else ""


class LLMWorker:
    """(심화 F3021) 복구 가능한 실패(NO_RESULT·INVALID_INPUT)에서만 호출된다. 정상 경로에서는 0회."""

    def __call__(self, *, tool: str, args: dict, error: dict, fixed: list[str], repairable: list[str],
                 message: str) -> WorkerDecision:
        context = {"tool": tool, "args": args, "error": {"code": error.get("code"), "message": error.get("message")},
                   "fixed": fixed, "repairable": repairable, "user_message": message}
        return get_structured_llm(WorkerDecision, "worker").invoke(
            [SystemMessage(WORKER_SYSTEM), HumanMessage(json.dumps(context, ensure_ascii=False))])
