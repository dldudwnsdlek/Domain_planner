"""테스트 공통 설정: 실제 대기(재시도 간격·KOPIS 요청 간격)를 0으로 둬 테스트를 빠르게 한다."""

import pytest

from app.tools import base, kopis


@pytest.fixture(autouse=True)
def no_waits(monkeypatch):
    monkeypatch.setattr(base, "RETRY_DELAY_SEC", 0)
    monkeypatch.setattr(kopis, "BLOCK_RETRY_DELAY_SEC", 0)
    monkeypatch.setattr(kopis, "THROTTLE", kopis.Throttle(max_concurrent=5, min_interval=0))
