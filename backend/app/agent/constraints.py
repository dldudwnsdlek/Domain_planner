"""제약 판정 순수 함수 (C1~C7, 역산, 정렬, 탈락 통계, 조정안, 겹침).

LLM을 쓰지 않는다. 같은 입력이면 항상 같은 결과가 나와야 재계획과 검증을 재현할 수 있다.

판정 규칙 (PLAN 5.4)
  C1 공연 기간  C2 회차 존재  C3 시작 하한  C4 러닝타임  C5 종료 제한  C6 귀가 제한  C7 예산
  회차 = FAIL 하나라도 → FAIL / 아니면 UNKNOWN 하나라도 → UNKNOWN / 아니면 PASS (경계값 같으면 통과)
  공연 = PASS 회차가 하나라도 있으면 PASS

설계 결정
  - C4(러닝타임)는 종료·귀가 조건이 있을 때만 필요하다. 필요 없는 검사로 후보를 '판정 불가'로 만들지 않는다.
  - 종료·귀가 기한이 05:00 이전이면 다음 날 새벽으로 본다("밤 12시 반까지" = 00:30).
  - 공휴일(HOL) 회차는 공휴일 달력이 없어 쓰지 않는다. 요일 회차만 본다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date as Date

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
NEXT_DAY_CUTOFF = 5 * 60
MAX_RECOMMENDATIONS = 5
DEFAULT_EXIT_BUFFER_MIN = 10

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

# 탈락 사유 코드 (통계 동점일 때 이 순서로 대표 사유를 고른다)
REASON_ORDER = (
    "OUT_OF_PERIOD", "NO_PERIOD", "NO_SHOW_ON_DAY", "SCHEDULE_UNPARSED", "START_TOO_EARLY",
    "END_TOO_LATE", "HOME_TOO_LATE", "OVER_BUDGET", "NO_RUNTIME", "NO_TRANSIT", "PRICE_UNPARSED",
)


@dataclass(frozen=True)
class Conditions:
    date: str  # YYYY-MM-DD
    start_after: str | None = None
    end_by: str | None = None
    home_by: str | None = None
    budget_max: int | None = None


@dataclass
class ShowtimeEval:
    start: str
    end: str | None
    home_arrival: str | None
    verdict: str
    fails: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    @property
    def reasons(self) -> list[str]:
        return self.fails + self.unknowns


@dataclass
class PerformanceEval:
    performance_id: str
    title: str
    verdict: str
    showtimes: list[ShowtimeEval]
    reasons: list[str]
    latest_start: str | None
    min_price: int | None


# ── 시각 계산 ─────────────────────────────────────────────────────────────────


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def deadline_minutes(hhmm: str) -> int:
    """기한 시각을 분으로. 05:00 이전이면 다음 날로 본다."""
    m = to_minutes(hhmm)
    return m + 24 * 60 if m < NEXT_DAY_CUTOFF else m


def weekday_key(iso_date: str) -> str:
    return DAY_KEYS[Date.fromisoformat(iso_date).weekday()]


def latest_start(cond: Conditions, runtime_min: int | None, transit_min: int | None,
                 exit_buffer: int = DEFAULT_EXIT_BUFFER_MIN) -> str | None:
    """회차를 모를 때 쓰는 역산 기준: 이 시각 이전에 시작해야 종료·귀가 조건을 지킨다."""
    if runtime_min is None:
        return None
    limits = []
    if cond.end_by:
        limits.append(deadline_minutes(cond.end_by) - runtime_min)
    if cond.home_by and transit_min is not None:
        limits.append(deadline_minutes(cond.home_by) - transit_min - exit_buffer - runtime_min)
    return to_hhmm(min(limits)) if limits else None


# ── 판정 ─────────────────────────────────────────────────────────────────────


def _combine(fails: list[str], unknowns: list[str]) -> str:
    return FAIL if fails else UNKNOWN if unknowns else PASS


def _evaluate_showtime(start: str, perf: dict, cond: Conditions, transit_min: int | None,
                       skip_home: bool, exit_buffer: int, price_fails: list[str],
                       price_unknowns: list[str]) -> ShowtimeEval:
    fails, unknowns = list(), list()
    t = to_minutes(start)
    runtime = perf.get("runtime_min")
    if cond.start_after and t < to_minutes(cond.start_after):  # C3
        fails.append("START_TOO_EARLY")

    end_m = t + runtime if runtime is not None else None
    needs_runtime = bool(cond.end_by) or (bool(cond.home_by) and not skip_home)
    if end_m is None and needs_runtime:  # C4
        unknowns.append("NO_RUNTIME")
    if cond.end_by and end_m is not None and end_m > deadline_minutes(cond.end_by):  # C5
        fails.append("END_TOO_LATE")

    arrival_m = end_m + exit_buffer + transit_min if end_m is not None and transit_min is not None else None
    if cond.home_by and not skip_home:  # C6
        if transit_min is None:
            unknowns.append("NO_TRANSIT")
        elif arrival_m is not None and arrival_m > deadline_minutes(cond.home_by):
            fails.append("HOME_TOO_LATE")

    fails += price_fails  # C7 (공연 단위 값이지만 회차마다 적용)
    unknowns += price_unknowns
    return ShowtimeEval(
        start=start,
        end=to_hhmm(end_m) if end_m is not None else None,
        home_arrival=to_hhmm(arrival_m) if arrival_m is not None else None,
        verdict=_combine(fails, unknowns),
        fails=fails,
        unknowns=unknowns,
    )


def evaluate_performance(perf: dict, cond: Conditions, transit_min: int | None = None, *,
                         skip_home: bool = False,
                         exit_buffer: int = DEFAULT_EXIT_BUFFER_MIN) -> PerformanceEval:
    """공연 하나를 관람일 기준으로 판정한다. skip_home=True는 2단계 판정의 1차(이동시간 조회 전)."""
    issues = set(perf.get("issues") or [])
    runtime = perf.get("runtime_min")

    def result(verdict: str, showtimes: list[ShowtimeEval], reasons: list[str]) -> PerformanceEval:
        return PerformanceEval(
            performance_id=perf["performance_id"], title=perf.get("title", ""), verdict=verdict,
            showtimes=showtimes, reasons=[] if verdict == PASS else reasons,
            latest_start=latest_start(cond, runtime, None if skip_home else transit_min, exit_buffer),
            min_price=perf.get("min_price"),
        )

    # C1 공연 기간
    start_d, end_d = perf.get("period_from"), perf.get("period_to")
    if not start_d or not end_d:
        period_unknown = ["NO_PERIOD"]
    elif not (start_d <= cond.date <= end_d):
        return result(FAIL, [], ["OUT_OF_PERIOD"])
    else:
        period_unknown = []

    # C7 예산 (공연 단위)
    price_fails, price_unknowns = [], []
    if cond.budget_max is not None:
        price = perf.get("min_price")
        if price is None:
            price_unknowns.append("PRICE_UNPARSED")
        elif price > cond.budget_max:
            price_fails.append("OVER_BUDGET")
    price_unknowns += period_unknown

    # C2 회차 존재
    if "SCHEDULE_UNPARSED" in issues:
        verdict = FAIL if price_fails else UNKNOWN
        return result(verdict, [], price_fails or ["SCHEDULE_UNPARSED"] + price_unknowns)
    times = (perf.get("schedule") or {}).get(weekday_key(cond.date), [])
    if not times:
        return result(FAIL, [], ["NO_SHOW_ON_DAY"])

    showtimes = [
        _evaluate_showtime(t, perf, cond, transit_min, skip_home, exit_buffer, price_fails, price_unknowns)
        for t in times
    ]
    verdicts = {s.verdict for s in showtimes}
    verdict = PASS if PASS in verdicts else UNKNOWN if UNKNOWN in verdicts else FAIL
    reasons = list(dict.fromkeys(r for s in showtimes for r in s.reasons))
    return result(verdict, showtimes, reasons)


# ── 정렬 · 통계 · 조정안 ──────────────────────────────────────────────────────


def rank_passed(evals: list[PerformanceEval], limit: int = MAX_RECOMMENDATIONS,
                start_after: str | None = None) -> list[PerformanceEval]:
    """PASS 공연을 (희망 시각에 가장 가까운 통과 회차, 최저가) 순으로 정렬해 상위 limit개.

    희망 시각이 없으면 가장 이른 통과 회차 순.
    """
    passed = [e for e in evals if e.verdict == PASS]
    if not passed:
        return []

    def passing(ev: PerformanceEval) -> list[int]:
        return [to_minutes(s.start) for s in ev.showtimes if s.verdict == PASS]

    base = to_minutes(start_after) if start_after else min(min(passing(e)) for e in passed)

    def key(ev: PerformanceEval):
        price = ev.min_price if ev.min_price is not None else float("inf")
        return (min(abs(t - base) for t in passing(ev)), price)

    return sorted(passed, key=key)[:limit]


def primary_reason(ev: PerformanceEval) -> str | None:
    if ev.verdict == PASS or not ev.reasons:
        return None
    counts = Counter(r for s in ev.showtimes for r in s.reasons) or Counter(ev.reasons)
    return min(counts, key=lambda r: (-counts[r], REASON_ORDER.index(r) if r in REASON_ORDER else 99))


def count_fail_reasons(evals: list[PerformanceEval]) -> dict[str, int]:
    """탈락·판정 불가 공연마다 대표 사유 1개씩 세어 통계를 낸다."""
    return dict(Counter(r for r in map(primary_reason, evals) if r))


_ADJUSTABLE = {
    # 탈락 사유 코드 → 바꾸면 해소되는 사용자 제약 필드
    "OVER_BUDGET": "budget_max",
    "END_TOO_LATE": "end_by",
    "HOME_TOO_LATE": "home_by",
    "START_TOO_EARLY": "start_after",
}


def suggest_adjustments(evals: list[PerformanceEval]) -> list[dict]:
    """사용자 제약 하나만 바꾸면 가능해지는 경우를 이미 조회한 값으로만 계산한다(지어낸 값 없음).

    반환: [{"field": "budget_max", "value": 55000, "count": 1}, ...]
    """
    needed: dict[str, list[int]] = {f: [] for f in _ADJUSTABLE.values()}
    for ev in evals:
        if ev.verdict == PASS:
            continue
        per_field: dict[str, int] = {}
        for s in ev.showtimes:
            if s.unknowns or len(s.fails) != 1:
                continue
            reason = s.fails[0]
            if reason == "OVER_BUDGET" and ev.min_price is not None:
                value = ev.min_price
            elif reason == "END_TOO_LATE" and s.end:
                value = to_minutes(s.end) if to_minutes(s.end) >= NEXT_DAY_CUTOFF else to_minutes(s.end) + 1440
            elif reason == "HOME_TOO_LATE" and s.home_arrival:
                m = to_minutes(s.home_arrival)
                value = m if m >= NEXT_DAY_CUTOFF else m + 1440
            elif reason == "START_TOO_EARLY":
                value = -to_minutes(s.start)  # 시작 하한은 '당길수록' 느슨 → 부호를 바꿔 최솟값 비교
            else:
                continue
            fld = _ADJUSTABLE[reason]
            per_field[fld] = min(per_field.get(fld, value), value)
        for fld, value in per_field.items():
            needed[fld].append(value)

    suggestions = []
    for fld, values in needed.items():
        if not values:
            continue
        best = min(values)
        count = sum(1 for v in values if v <= best)
        if fld == "budget_max":
            shown: int | str = best
        elif fld == "start_after":
            shown = to_hhmm(-best)
        else:
            shown = to_hhmm(best)
        suggestions.append({"field": fld, "value": shown, "count": count})
    return suggestions


# ── 계획 겹침 [start, end) ───────────────────────────────────────────────────


def _span(plan: dict) -> tuple[int, int | None]:
    start = to_minutes(plan["start_time"])
    if not plan.get("end_time"):
        return start, None
    end = to_minutes(plan["end_time"])
    return start, end + 1440 if end <= start else end


def plans_overlap(a: dict, b: dict) -> bool:
    """같은 날짜에서 [시작, 종료)가 겹치는가. 종료를 모르면 '시작 시각이 상대 구간 안에 있는가'로 본다."""
    if a["date"] != b["date"]:
        return False
    a_s, a_e = _span(a)
    b_s, b_e = _span(b)
    if a_e is not None and b_e is not None:
        return a_s < b_e and a_e > b_s
    if a_e is None and b_e is not None:
        return b_s <= a_s < b_e
    if b_e is None and a_e is not None:
        return a_s <= b_s < a_e
    return a_s == b_s
