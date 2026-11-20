"""app/tools/kma_grid.py — 위경도 → 기상청 격자, 발표 시각 선택, 예보 범위."""

from datetime import datetime

import pytest

from app.tools.kma_grid import in_forecast_range, latest_base_time, to_grid


@pytest.mark.parametrize(
    ("lat", "lng", "grid"),
    [
        (37.5729, 126.9793, (60, 127)),  # 서울 종로구
        (37.5665, 126.9780, (60, 127)),  # 서울시청
        (35.1796, 129.0756, (98, 76)),   # 부산시청
        # TODO: 기상청 활용가이드 격자 엑셀 값으로 3곳 이상 추가 대조 (아직 엑셀 미확인)
    ],
)
def test_to_grid_known_points(lat, lng, grid):
    assert to_grid(lat, lng) == grid


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-11-20 08:41", ("20261120", "0800")),
        ("2026-11-20 08:05", ("20261120", "0500")),  # 발표 직후 10분은 자료가 없을 수 있음
        ("2026-11-20 08:10", ("20261120", "0800")),
        ("2026-11-20 02:09", ("20261119", "2300")),  # 02시 발표 전 → 전날 23시
        ("2026-11-20 00:30", ("20261119", "2300")),
        ("2026-11-20 23:59", ("20261120", "2300")),
    ],
)
def test_latest_base_time(now, expected):
    assert latest_base_time(datetime.strptime(now, "%Y-%m-%d %H:%M")) == expected


@pytest.mark.parametrize(
    ("target", "ok"),
    [("2026-11-20", True), ("2026-11-23", True), ("2026-11-24", False), ("2026-11-19", False),
     ("2026-12-20", False)],
)
def test_forecast_range_is_until_three_days_after_base(target, ok):
    assert in_forecast_range("20261120", target) is ok
