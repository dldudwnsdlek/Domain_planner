"""재계획 완화 사다리 (순수 함수).

R1 후보 더 가져오기: 아직 상세를 안 본 후보가 있으면 그것부터, 없으면 직전 페이지가 꽉 찼을 때만 다음 페이지
R2 지역 넓히기   : 구 단위 → 시·도 전체 (예: 대학로/종로구 → 서울)
R3 장르 넓히기   : 연극 ↔ 뮤지컬
✖ 날짜·시작 시각·종료/귀가 시각·예산은 사용자 제약이므로 자동으로 바꾸지 않는다.
strict로 표시된 선호(“대학로만”, “꼭 연극”)는 건너뛴다.
"""

from __future__ import annotations

from app.tools.base import ToolError
from app.tools.region_alias import SIDO, resolve_region

ADJACENT_GENRE = {"연극": "뮤지컬", "뮤지컬": "연극"}
SIDO_BY_CODE = {code: name for name, code in SIDO.items()}


def _city_of(region: str | None) -> str | None:
    """구 단위 지역이면 그 시·도 이름, 이미 시·도 단위면 None."""
    if not region:
        return None
    try:
        resolved = resolve_region(region)
    except ToolError:
        return None
    return SIDO_BY_CODE.get(resolved.sido_code) if resolved.gugun_code else None


def next_relaxation(query: dict, conditions: dict, pending: int) -> dict | None:
    if pending > 0:
        return {"step": "R1", "relaxed": {"more_candidates": pending}, "query": dict(query),
                "reason": "아직 상세를 확인하지 않은 후보가 남아 있음"}
    if query.get("has_more"):
        page = query.get("page", 1) + 1
        return {"step": "R1", "relaxed": {"page": page}, "query": {**query, "page": page},
                "reason": "직전 페이지가 가득 차 다음 페이지 조회"}
    city = _city_of(query.get("region"))
    if city and not conditions.get("region_strict") and not query.get("region_relaxed"):
        return {"step": "R2", "relaxed": {"region": f"{query['region']} → {city}"},
                "query": {**query, "region": city, "page": 1, "has_more": False, "region_relaxed": True},
                "reason": "지역을 시·도 전체로 넓힘"}
    genre = query.get("genre")
    if genre in ADJACENT_GENRE and not conditions.get("genre_strict") and not query.get("genre_relaxed"):
        return {"step": "R3", "relaxed": {"genre": f"{genre} → {ADJACENT_GENRE[genre]}"},
                "query": {**query, "genre": ADJACENT_GENRE[genre], "page": 1, "has_more": False,
                          "genre_relaxed": True},
                "reason": "인접 장르로 넓힘"}
    return None
