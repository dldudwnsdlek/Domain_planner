"""로깅 서브 Agent.

- LLM을 import하지도 호출하지도 않는다. 요약·가공 없이 이벤트 원본을 발생 순서대로 추가만 한다.
- 저장이 실패해도 예외를 밖으로 내지 않는다(stderr 기록만) → 대화는 정상으로 진행된다.
"""

from __future__ import annotations

import sys

from app.db.logs_repo import LogsRepo
from app.events.bus import EventBus
from app.events.types import Event


class LoggingAgent:
    def __init__(self, repo: LogsRepo) -> None:
        self.repo = repo

    def handle(self, event: Event) -> None:
        try:
            self.repo.append(event.to_dict())
        except Exception as exc:  # noqa: BLE001
            print(f"[logging_agent] 로그 저장 실패: {type(exc).__name__}", file=sys.stderr)

    def attach(self, bus: EventBus):
        """구독을 등록하고, 해제 함수를 돌려준다."""
        return bus.subscribe(self.handle)
