"""지역 이름 → KOPIS 지역 코드 (규칙 사전).

- 시·도 코드(signgucode)와 서울 구 코드(signgucodesub)는 행정구역 코드 앞자리다.
  KOPIS 공통코드 문서로 확인한 값: 서울 11, 종로구 1111, 강남구 1168 (실제 호출로 1111 조회 확인).
- 구 단위 코드는 지금은 서울만 지원한다. 다른 시·도는 시·도 단위로 조회한다.
- '대학로'는 종로구로 조회한 뒤 상세의 daehakro=Y로 한 번 더 거른다(daehakro_only).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.tools.base import AMBIGUOUS, INVALID_INPUT, ToolError

SIDO = {"서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29", "대전": "30", "울산": "31", "경기": "41"}
_SIDO_SUFFIXES = ("특별시", "광역시", "특별자치도", "특별자치시", "도", "시")

SEOUL_GU = {
    "종로구": "1111", "중구": "1114", "용산구": "1117", "성동구": "1120", "광진구": "1121",
    "동대문구": "1123", "중랑구": "1126", "성북구": "1129", "강북구": "1130", "도봉구": "1132",
    "노원구": "1135", "은평구": "1138", "서대문구": "1141", "마포구": "1144", "양천구": "1147",
    "강서구": "1150", "구로구": "1153", "금천구": "1154", "영등포구": "1156", "동작구": "1159",
    "관악구": "1162", "서초구": "1165", "강남구": "1168", "송파구": "1171", "강동구": "1174",
}

# 생활권 별칭 → (서울 구 이름, 대학로만 거르기)
ALIASES = {
    "대학로": ("종로구", True), "혜화": ("종로구", True), "광화문": ("종로구", False),
    "강남": ("강남구", False), "홍대": ("마포구", False), "합정": ("마포구", False),
    "신촌": ("서대문구", False), "잠실": ("송파구", False), "성수": ("성동구", False),
    "여의도": ("영등포구", False), "명동": ("중구", False), "충무로": ("중구", False),
}

# 여러 시·도에 같은 이름이 있는 구 → 시·도 없이 오면 되묻는다
AMBIGUOUS_GU = {"중구", "동구", "서구", "남구", "북구", "강서구"}


@dataclass(frozen=True)
class Region:
    sido_code: str
    gugun_code: str | None
    label: str
    daehakro_only: bool = False


def _sido(token: str) -> str | None:
    for suffix in _SIDO_SUFFIXES:
        if token.endswith(suffix) and token[: -len(suffix)] in SIDO:
            return token[: -len(suffix)]
    return token if token in SIDO else None


def _seoul_gu(token: str, label: str, daehakro: bool = False) -> Region | None:
    name = token if token.endswith("구") else f"{token}구"
    if name in SEOUL_GU:
        return Region("11", SEOUL_GU[name], label, daehakro)
    return None


def resolve_region(text: str) -> Region:
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ToolError(INVALID_INPUT, "지역 이름이 비어 있어요.")

    sido = _sido(tokens[0])
    rest = tokens[1:] if sido else tokens
    if sido and not rest:
        return Region(SIDO[sido], None, f"{sido} 전체")
    if sido and sido != "서울":
        return Region(SIDO[sido], None, f"{sido} 전체")  # 서울 외에는 시·도 단위만 지원

    token = rest[0]
    if token in ALIASES:
        gu, daehakro = ALIASES[token]
        return Region("11", SEOUL_GU[gu], f"서울 {gu}", daehakro)
    if sido is None and (token in AMBIGUOUS_GU or f"{token}구" in AMBIGUOUS_GU):
        raise ToolError(AMBIGUOUS, f"'{token}'은 여러 지역에 있어요. 어느 시·도인지 알려 주세요.")
    region = _seoul_gu(token, f"서울 {token if token.endswith('구') else token + '구'}")
    if region:
        return region
    raise ToolError(INVALID_INPUT, f"'{text}' 지역을 찾지 못했어요. 서울의 구 이름이나 '대학로'처럼 알려 주세요.")
