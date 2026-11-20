"""(심화 F3021) Planner·Worker — 작업 목록과 Worker 복구 정책.

Planner(plan 노드)는 LLM이 고른 Tool을 검증·보완한 뒤 **작업 목록(TaskList)** 으로 만든다.
  각 작업: id · tool · args · fixed(Worker가 바꿀 수 없는 인자) · repairable(Worker가 고칠 수 있는 인자)
          · depends_on · args_from(앞 작업 결과에서 채우는 인자)
  - fixed: 사용자 제약(날짜)과 선호(지역·장르). 선호를 넓히는 일은 Planner의 재계획만 할 수 있다.
  - repairable: 사용자가 자유롭게 쓴 글(집 위치 검색어, 작품명)뿐이다.

Worker(execute 노드)는 정상 경로에서 규칙대로 실행한다(LLM 0회).
  - NO_RESULT / INVALID_INPUT 이고 고칠 인자가 있을 때만(구성 C) LLM이 retry / skip / request_replan 을 고른다.
  - LLM이 고정 인자나 고칠 수 없는 인자를 바꾸거나, 원문과 겹치지 않는 값을 내면 코드가 거부 → request_replan.
  - 같은 작업에서 LLM 재시도는 최대 2회.
  - MISSING_API_KEY · AMBIGUOUS 등은 LLM 없이 기존 규칙대로(멈춤·되묻기).
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.agent.nodes.common import DETAIL, PLACES, SEARCH, TRANSIT, WEATHER
from app.agent.state import ArgChange
from app.events.types import LLM_DECISION, WORKER_DECISION, WORKER_REJECTED
from app.tools.base import INVALID_INPUT, NO_RESULT

REPAIRABLE_CODES = {NO_RESULT, INVALID_INPUT}
MAX_LLM_RETRIES = 2
FACT_SEARCH_DAYS = 30


# ── 작업 목록 ─────────────────────────────────────────────────────────────────


def build_tasks(intent: str, topic: str | None, cond: dict, plan_tools: list[str], query: dict, *,
                today: date, weather_query: str | None = None) -> list[dict]:
    """Planner가 Worker에게 넘길 작업 목록. 실행 순서는 depends_on을 따른다."""
    if intent == "fact_query" and topic == "weather":
        return [
            {"id": "t1", "tool": PLACES, "args": {"mode": "geocode", "query": weather_query or cond.get("region")},
             "fixed": ["mode"], "repairable": ["query"], "depends_on": []},
            {"id": "t2", "tool": WEATHER, "args": {"date": cond.get("date")}, "args_from": {"lat/lng": "t1.items[0]"},
             "fixed": ["date"], "repairable": [], "depends_on": ["t1"]},
        ]
    if intent == "fact_query":
        start = date.fromisoformat(cond["date"]) if cond.get("date") else today
        return [
            {"id": "t1", "tool": SEARCH,
             "args": {"keyword": cond.get("keyword"), "date_from": start.isoformat(),
                      "date_to": (start + timedelta(days=FACT_SEARCH_DAYS)).isoformat()},
             "fixed": ["date_from", "date_to"], "repairable": ["keyword"], "depends_on": []},
            {"id": "t2", "tool": DETAIL, "args_from": {"performance_id": "t1.items[0].performance_id"},
             "fixed": [], "repairable": [], "depends_on": ["t1"]},
        ]
    tasks = [
        {"id": "t1", "tool": SEARCH,
         "args": {"date_from": cond.get("date"), "region": query.get("region"), "genre": query.get("genre")},
         "fixed": ["date_from", "region", "genre"], "repairable": [], "depends_on": []},
        {"id": "t2", "tool": DETAIL, "args_from": {"performance_id": "t1.items[*].performance_id"},
         "fixed": [], "repairable": [], "depends_on": ["t1"]},
    ]
    if TRANSIT in plan_tools:
        tasks.append({"id": "t3", "tool": PLACES, "args": {"mode": "geocode", "query": cond.get("home_location")},
                      "fixed": ["mode"], "repairable": ["query"], "depends_on": []})
        tasks.append({"id": "t4", "tool": TRANSIT, "args_from": {"from": "t2.venue", "to": "t3.items[0]"},
                      "fixed": [], "repairable": [], "depends_on": ["t2", "t3"]})
    if WEATHER in plan_tools:
        tasks.append({"id": "t5", "tool": WEATHER, "args": {"date": cond.get("date")},
                      "args_from": {"lat/lng": "t2.venue"}, "fixed": ["date"], "repairable": [],
                      "depends_on": ["t2"]})
    return tasks


def find_task(state: dict, task_id: str) -> dict | None:
    return next((t for t in state.get("tasks") or [] if t["id"] == task_id), None)


def with_task_args(tasks: list[dict], task_id: str, args: dict) -> list[dict]:
    """Worker가 고친 인자를 작업 목록에 반영한 새 목록 (실행 기록용)."""
    return [{**t, "args": {**t.get("args", {}), **args}} if t["id"] == task_id else t for t in tasks]


# ── 고정 인자 보호 ────────────────────────────────────────────────────────────


def _grams(text: str) -> set[str]:
    s = re.sub(r"[\s·,./()\-~]", "", str(text))
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def apply_changes(task: dict, args: dict, changes: list[ArgChange], original: dict) -> tuple[dict | None, str | None]:
    """LLM이 제안한 인자 변경을 검증한다. 통과하면 (새 인자, None), 아니면 (None, 거부 이유)."""
    if not changes:
        return None, "바꾼 인자가 없음"
    new_args = dict(args)
    for change in changes:
        if change.name in task.get("fixed", []):
            return None, f"고정 인자 '{change.name}' 변경 시도"
        if change.name not in task.get("repairable", []):
            return None, f"바꿀 수 없는 인자 '{change.name}'"
        if not _grams(original.get(change.name, "")) & _grams(change.value):
            return None, f"원문과 겹치지 않는 값으로 바꾸려 함(지어내기 의심): '{change.name}'"
        new_args[change.name] = change.value
    if new_args == args:
        return None, "바꾼 인자가 없음"
    return new_args, None


# ── Worker 실행 ───────────────────────────────────────────────────────────────


def worker_call(state: dict, deps, node: str, task_id: str, tool: str, args: dict) -> tuple[dict, dict]:
    """작업 하나를 실행한다. 반환: (Tool 결과, 정보). 정보의 action:
    None(정책 없음·성공·복구 대상 아님) / retry_ok(고친 인자로 성공) / skip / request_replan.
    """
    result = deps.call_tool(state, node, tool, args)
    task = find_task(state, task_id)
    info: dict = {"action": None, "args": args}
    if deps.mode == "A" or task is None or result["ok"] or result["error"]["code"] not in REPAIRABLE_CODES:
        return result, info

    code = result["error"]["code"]

    def decide_by_rule(reason: str) -> tuple[dict, dict]:
        deps.emit(state, WORKER_DECISION, node, task=task_id, tool=tool, code=code, by="rule",
                  action="request_replan", reason=reason)
        return result, {**info, "action": "request_replan", "reason": reason}

    repairable = [k for k in task.get("repairable", []) if k in args]
    if not repairable:
        return decide_by_rule("고정 인자뿐이라 인자를 바꿔도 결과가 같음")
    if deps.worker is None:
        return decide_by_rule("Worker LLM 꺼짐(구성 B)")

    original, tried = dict(args), {json.dumps(args, sort_keys=True, ensure_ascii=False)}
    for _attempt in range(MAX_LLM_RETRIES):
        deps.count_llm(state)
        try:
            decision = deps.worker(tool=tool, args=args, error=result["error"], fixed=task.get("fixed", []),
                                   repairable=repairable, message=state.get("message", ""))
        except Exception:  # noqa: BLE001 — Worker LLM 실패는 규칙으로 처리
            return decide_by_rule("Worker LLM 호출 실패")
        changes = [c.model_dump() for c in decision.changes]
        deps.emit(state, LLM_DECISION, node, kind="worker_retry", value=decision.action, reason=decision.reason,
                  task=task_id, changes=changes)
        deps.emit(state, WORKER_DECISION, node, task=task_id, tool=tool, code=code, by="llm",
                  action=decision.action, reason=decision.reason, changes=changes)
        if decision.action != "retry":
            return result, {**info, "action": decision.action, "reason": decision.reason}

        new_args, rejected = apply_changes(task, args, decision.changes, original)
        key = json.dumps(new_args, sort_keys=True, ensure_ascii=False) if new_args else None
        if new_args is not None and key in tried:
            new_args, rejected = None, "이미 시도한 인자"
        if new_args is None:
            deps.emit(state, WORKER_REJECTED, node, task=task_id, tool=tool, changes=changes, reason=rejected)
            return result, {**info, "action": "request_replan", "reason": rejected}

        tried.add(key)
        args = new_args
        result = deps.call_tool(state, node, tool, args)
        if result["ok"]:
            return result, {"action": "retry_ok", "args": args, "repaired_from": original,
                            "reason": decision.reason}
        if result["error"]["code"] not in REPAIRABLE_CODES:
            return result, {"action": None, "args": args}
    return decide_by_rule(f"LLM 재시도 {MAX_LLM_RETRIES}회 후에도 실패")
