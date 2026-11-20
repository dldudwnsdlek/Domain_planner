"""대화 1건 실행: run 이벤트 발행 + 그래프 실행 + 예외 격리."""

from __future__ import annotations

import logging
import time
import uuid

from app.agent.deps import Deps
from app.agent.graph import build_graph
from app.agent.state import fresh_run_state
from app.events.bus import RunEmitter
from app.events.types import RUN_COMPLETED, RUN_FAILED, RUN_STARTED

logger = logging.getLogger(__name__)
RECURSION_LIMIT = 60


class AgentService:
    def __init__(self, deps: Deps, graph=None) -> None:
        self.deps = deps
        self.graph = graph or build_graph(deps)

    def chat(self, session_id: str | None, message: str) -> dict:
        session_id = session_id or f"s-{uuid.uuid4().hex[:10]}"
        run_id = f"r-{uuid.uuid4().hex[:10]}"
        emitter = RunEmitter(self.deps.bus, session_id, run_id)
        emitter.llm_calls = emitter.api_calls = 0
        self.deps.emitters[run_id] = emitter
        emitter.emit(RUN_STARTED, None, message=message)
        started = time.monotonic()
        try:
            out = self.graph.invoke(fresh_run_state(session_id, run_id, message),
                                    config={"configurable": {"thread_id": session_id},
                                            "recursion_limit": RECURSION_LIMIT})
            response = out["response"]
            response["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            emitter.emit(RUN_COMPLETED, None, elapsed_ms=response["elapsed_ms"],
                         status=response["status"], replan_count=out.get("replan_count", 0),
                         llm_calls=emitter.llm_calls, api_calls=emitter.api_calls)
            return response
        except Exception:  # noqa: BLE001 — 사용자에게는 상세를 숨기고 로그에만 남긴다
            logger.exception("agent run failed")
            emitter.emit(RUN_FAILED, None, code="INTERNAL_ERROR")
            return {"session_id": session_id, "run_id": run_id, "status": "error",
                    "reply": "요청을 처리하는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
                    "understood": {}, "defaults_applied": [], "recommendations": [], "excluded": [],
                    "suggestions": [], "facts": None, "assumptions": [], "sources": [], "trace": [],
                    "replan_count": 0, "warnings": []}
        finally:
            self.deps.emitters.pop(run_id, None)

    def mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()
