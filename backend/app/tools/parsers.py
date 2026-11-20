"""KOPIS 텍스트 필드 파서 (규칙 기반 순수 함수).

원칙: 확실히 해석한 값만 돌려준다. 일부라도 해석하지 못하면 None / complete=False로 두고
      판정 단계가 '판정 불가'로 처리한다. 값을 추정해서 채우지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SCHEDULE_KEYS = DAY_KEYS + ("holiday",)
_KOR_DAY = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# ── 러닝타임 ──────────────────────────────────────────────────────────────────

_PAREN = re.compile(r"\([^)]*\)")
_HOURS = re.compile(r"(\d+)\s*시간")
_MINUTES = re.compile(r"(\d+)\s*분")


def parse_runtime(raw: str | None) -> int | None:
    """'1시간 40분' → 100. 괄호 안 설명(인터미션 등)은 무시. 해석 불가 → None."""
    text = _PAREN.sub("", raw or "")
    hours, minutes = _HOURS.findall(text), _MINUTES.findall(text)
    if not hours and not minutes:
        return None
    if len(hours) > 1 or len(minutes) > 1:  # '1시간 ~ 2시간' 같은 범위는 확정할 수 없음
        return None
    total = int(hours[0]) * 60 if hours else 0
    total += int(minutes[0]) if minutes else 0
    return total or None


# ── 회차 ─────────────────────────────────────────────────────────────────────

_SEGMENT = re.compile(r"([^(),]+?)\s*\(([^()]*)\)")
_DAY_RANGE = re.compile(r"^([월화수목금토일])요일\s*~\s*([월화수목금토일])요일$")
_DAY_ONE = re.compile(r"^([월화수목금토일])요일$")
_HOLIDAY = re.compile(r"^(HOL|HOLIDAY)$", re.IGNORECASE)
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


@dataclass
class ScheduleParse:
    schedule: dict[str, list[str]] = field(default_factory=lambda: {k: [] for k in SCHEDULE_KEYS})
    complete: bool = False  # True일 때만 '그 요일 회차 없음'을 탈락 근거로 쓸 수 있다


def _days(spec: str) -> list[str] | None:
    spec = spec.strip()
    if _HOLIDAY.match(spec):
        return ["holiday"]
    if m := _DAY_RANGE.match(spec):
        start, end = _KOR_DAY[m.group(1)], _KOR_DAY[m.group(2)]
        span = (end - start) % 7
        return [DAY_KEYS[(start + i) % 7] for i in range(span + 1)]
    if m := _DAY_ONE.match(spec):
        return [DAY_KEYS[_KOR_DAY[m.group(1)]]]
    return None


def _times(spec: str) -> list[str] | None:
    times = []
    for part in spec.split(","):
        m = _TIME.match(part.strip())
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            return None
        times.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    return times


def parse_schedule(raw: str | None) -> ScheduleParse:
    """'화요일 ~ 금요일(19:30), 토요일(15:00,19:00), HOL(14:00)' → 요일별 회차."""
    result = ScheduleParse()
    text = (raw or "").strip()
    segments = list(_SEGMENT.finditer(text))
    if not segments:
        return result
    leftover = _SEGMENT.sub("", text).replace(",", "").strip()
    complete = not leftover
    for seg in segments:
        days, times = _days(seg.group(1)), _times(seg.group(2))
        if days is None or times is None:
            complete = False
            continue
        for day in days:
            result.schedule[day] = sorted(set(result.schedule[day]) | set(times))
    result.complete = complete
    return result


# ── 가격 ─────────────────────────────────────────────────────────────────────

_PRICE_ITEM = re.compile(r"([^,]*?)\s*(\d{1,3}(?:,\d{3})+|\d+)\s*원")


@dataclass
class PriceParse:
    prices: list[dict] = field(default_factory=list)
    min_price: int | None = None


def parse_price(raw: str | None) -> PriceParse:
    """'R석 70,000원, S석 55,000원' → 최저가 55000. 일부라도 해석 불가 → min_price None."""
    text = (raw or "").strip()
    if not text:
        return PriceParse()
    if "무료" in text and not re.search(r"\d", text):
        return PriceParse([{"seat": text.replace("무료", "").strip() or "전석", "price": 0}], 0)
    items = list(_PRICE_ITEM.finditer(text))
    leftover = _PRICE_ITEM.sub("", text).replace(",", "").strip()
    if not items or leftover:
        return PriceParse()
    prices = [{"seat": m.group(1).strip(), "price": int(m.group(2).replace(",", ""))} for m in items]
    return PriceParse(prices, min(p["price"] for p in prices))


# ── 날짜 ─────────────────────────────────────────────────────────────────────


def parse_kopis_date(raw: str | None) -> str | None:
    """'2026.11.21' → '2026-11-21'."""
    try:
        return datetime.strptime((raw or "").strip(), "%Y.%m.%d").strftime("%Y-%m-%d")
    except ValueError:
        return None
