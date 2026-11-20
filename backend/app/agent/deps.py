"""Agent 노드가 쓰는 의존성 묶음. 그래프를 만들 때 한 번 주입한다.

LLM 단계(analyzer·planner·summarizer)는 바꿔 끼울 수 있다. 테스트와 오프라인 실행에서는 가짜를 넣는다.
Agent는 events 모듈(발행)만 알고 logging_agent(구독)는 모른다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.events.bus import EventBus, RunEmitter
from app.events.types import TOOL_REQUESTED, TOOL_RESPONDED
from app.tools.base import Registry


@dataclass
class Deps:
    registry: Registry
    bus: EventBus
    analyzer: Callable | None = None
    planner: Callable | None = None
    summarizer: Callable | None = None
    worker: Callable | None = None  # (F3021) 구성 C에서만: 복구 가능한 실패일 때 재시도·건너뜀·재계획 요청 결정
    mode: str = "A"  # A 단일 Agent / B Planner·Worker(Worker LLM 끔) / C Planner·Worker(Worker LLM 켬)
    plans_repo: object | None = None
    now: Callable[[], datetime] = datetime.now
    max_replan: int = 3
    detail_limit: int = 10
    exit_buffer: int = 10
    emitters: dict[str, RunEmitter] = field(default_factory=dict)

    def emitter(self, state: dict) -> RunEmitter:
        return self.emitters[state["run_id"]]

    def emit(self, state: dict, type_: str, node: str | None = None, **payload):
        return self.emitter(state).emit(type_, node, **payload)

    def count_llm(self, state: dict) -> None:
        em = self.emitter(state)
        em.llm_calls = getattr(em, "llm_calls", 0) + 1

    def call_tool(self, state: dict, node: str, name: str, args: dict) -> dict:
        """Tool 실행 + tool.requested / tool.responded(소요 시간 포함) 발행. 예외는 나오지 않는다."""
        em = self.emitter(state)
        em.api_calls = getattr(em, "api_calls", 0) + 1
        self.emit(state, TOOL_REQUESTED, node, tool=name, args=args)
        started = time.monotonic()
        result = self.registry.run(name, args)
        payload = {"tool": name, "ok": result["ok"], "code": None if result["ok"] else result["error"]["code"],
                   "elapsed_ms": int((time.monotonic() - started) * 1000), "args": args}
        if not result["ok"] and result["meta"].get("detail"):
            payload["detail"] = result["meta"]["detail"]  # 실패 원인 구분 (URL·키 없음)
        data = result.get("data") if result["ok"] else None
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            payload["count"] = len(data["items"])
        self.emit(state, TOOL_RESPONDED, node, **payload)
        return result
