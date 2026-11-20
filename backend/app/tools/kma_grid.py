"""기상청 단기예보용 순수 함수: 위경도 → 격자(nx, ny), 발표 시각 선택, 예보 범위 확인.

격자 변환은 기상청 공개 람베르트 정각원추도법(LCC) 변환식이다.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

# 기상청 단기예보 격자 상수
RE = 6371.00877  # 지구 반경(km)
GRID = 5.0  # 격자 간격(km)
SLAT1, SLAT2 = 30.0, 60.0  # 표준 위도
OLON, OLAT = 126.0, 38.0  # 기준점 경도·위도
XO, YO = 43, 136  # 기준점 격자 좌표

BASE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)  # 하루 8회 발표
READY_DELAY_MIN = 10  # 발표 직후 자료가 아직 없을 수 있어 두는 여유
FORECAST_DAYS = 3  # 발표일 기준 글피까지 (실측: 글피는 3시간 간격, 그 다음 날은 00시뿐)


def to_grid(lat: float, lng: float) -> tuple[int, int]:
    degrad = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * degrad, SLAT2 * degrad
    olon, olat = OLON * degrad, OLAT * degrad

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn

    ra = re * sf / math.tan(math.pi * 0.25 + lat * degrad * 0.5) ** sn
    theta = lng * degrad - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = math.floor(ra * math.sin(theta) + XO + 0.5)
    ny = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def latest_base_time(now: datetime) -> tuple[str, str]:
    """지금 쓸 수 있는 가장 최근 발표 시각 (base_date YYYYMMDD, base_time HHMM)."""
    ready = now - timedelta(minutes=READY_DELAY_MIN)
    hours = [h for h in BASE_HOURS if h <= ready.hour]
    if hours:
        return ready.strftime("%Y%m%d"), f"{max(hours):02d}00"
    previous = ready - timedelta(days=1)
    return previous.strftime("%Y%m%d"), f"{BASE_HOURS[-1]:02d}00"


def in_forecast_range(base_date: str, target_iso: str) -> bool:
    """관람일이 발표일 ~ 발표일+3일(글피) 안인가. 밖이면 API를 부르지 않고 OUT_OF_RANGE."""
    base = datetime.strptime(base_date, "%Y%m%d").date()
    target = date.fromisoformat(target_iso)
    return 0 <= (target - base).days <= FORECAST_DAYS
