"""메모리 안의 발행·구독 EventBus.

- 발행자(Agent)는 구독자(로깅 Agent)를 모른다. Agent 코드는 이 모듈만 import한다.
- 구독자 예외는 잡아서 무시한다 → 로깅 장애가 대화에 영향을 주지 않는다.
- 구독자가 없어도 정상 동작한다.
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections.abc import Callable

from app.events.types import Event

logger = logging.getLogger(__name__)
Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Handler] = []
        self._lock = threading.Lock()

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(handler)

        def unsubscribe() -> None:
            with self._lock:
                if handler in self._subscribers:
                    self._subscribers.remove(handler)
        return unsubscribe

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._subscribers)
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001
                logger.exception("event subscriber failed")


class RunEmitter:
    """실행 1건(run_id)의 이벤트를 순번(seq)을 붙여 발행한다. 병렬 Tool 호출에서도 seq가 겹치지 않는다."""

    def __init__(self, bus: EventBus, session_id: str, run_id: str) -> None:
        self.bus, self.session_id, self.run_id = bus, session_id, run_id
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self.events: list[Event] = []  # 이번 실행의 이벤트 사본 (응답의 trace 생성용)

    def emit(self, type_: str, node: str | None = None, **payload) -> Event:
        with self._lock:
            event = Event(self.session_id, self.run_id, next(self._seq), type_, node, payload)
            self.events.append(event)
        self.bus.publish(event)
        return event
