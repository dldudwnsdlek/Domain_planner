"""이벤트 형식. 모든 이벤트는 session_id·run_id·seq를 가진다."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

RUN_STARTED, RUN_COMPLETED, RUN_FAILED = "run.started", "run.completed", "run.failed"
NODE_ENTERED, NODE_EXITED = "node.entered", "node.exited"
TOOL_REQUESTED, TOOL_RESPONDED = "tool.requested", "tool.responded"
LLM_DECISION = "llm.decision"
PLAN_FALLBACK = "plan.fallback"
CONSTRAINT_EVALUATED = "constraint.evaluated"
REPLAN_TRIGGERED, REPLAN_STOPPED = "replan.triggered", "replan.stopped"
TASKS_PLANNED = "plan.tasks"  # (F3021) Planner가 만든 작업 목록
WORKER_DECISION, WORKER_REJECTED = "worker.decision", "worker.rejected"  # (F3021) Worker 복구 판단 · 고정 인자 변경 거부


@dataclass(frozen=True)
class Event:
    session_id: str
    run_id: str
    seq: int
    type: str
    node: str | None
    payload: dict
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(KST).isoformat(timespec="milliseconds"))

    def to_dict(self) -> dict:
        return asdict(self)
