"""app/tools/parsers.py — 러닝타임·회차·가격·날짜 파서 (규칙 기반, 실제 샘플 포함)."""

import pathlib
import xml.etree.ElementTree as ET

import pytest

from app.tools.parsers import parse_kopis_date, parse_price, parse_runtime, parse_schedule

SAMPLES = pathlib.Path(__file__).resolve().parents[1] / "samples" / "kopis"


# ── 러닝타임 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "minutes"),
    [
        ("1시간 40분", 100),
        ("100분", 100),
        ("2시간", 120),
        ("50분", 50),
        ("1 시간 30 분", 90),
        ("2시간 30분(인터미션 20분 포함)", 150),
        ("약 1시간 10분", 70),
    ],
)
def test_runtime_parses(raw, minutes):
    assert parse_runtime(raw) == minutes


@pytest.mark.parametrize("raw", ["", "   ", None, "미정", "회차별 상이"])
def test_runtime_unparsed_returns_none(raw):
    assert parse_runtime(raw) is None


# ── 회차 ─────────────────────────────────────────────────────────────────────


def test_schedule_range_and_multiple_times():
    result = parse_schedule("화요일 ~ 금요일(19:30), 토요일(15:00,19:00), 일요일(15:00)")
    assert result.complete
    assert result.schedule["tue"] == ["19:30"]
    assert result.schedule["fri"] == ["19:30"]
    assert result.schedule["sat"] == ["15:00", "19:00"]
    assert result.schedule["sun"] == ["15:00"]
    assert result.schedule["mon"] == []


def test_schedule_holiday_tokens():
    for token in ("HOL", "HOLIDAY"):
        result = parse_schedule(f"토요일(15:00), {token}(14:00,18:00)")
        assert result.complete
        assert result.schedule["holiday"] == ["14:00", "18:00"]


def test_schedule_merges_same_day_from_two_segments_sorted():
    result = parse_schedule("월요일 ~ 금요일(20:00), 금요일(17:00)")
    assert result.schedule["fri"] == ["17:00", "20:00"]


def test_schedule_wrapping_range():
    result = parse_schedule("금요일 ~ 월요일(19:00)")
    assert result.complete
    assert [d for d, t in result.schedule.items() if t] == ["mon", "fri", "sat", "sun"]


def test_schedule_normalizes_single_digit_hour():
    assert parse_schedule("토요일(9:30)").schedule["sat"] == ["09:30"]


@pytest.mark.parametrize("raw", ["", None, "예매처 참고", "토요일(오후 7시)", "토요일(19:00), 공연 일정은 예매처 참고"])
def test_schedule_incomplete_when_any_part_unparsed(raw):
    assert parse_schedule(raw).complete is False


def test_schedule_complete_but_day_missing_is_distinguishable():
    """완전히 해석했는데 그 요일이 없으면 → 탈락 / 해석 실패 → 판정 불가 (C2)."""
    result = parse_schedule("화요일 ~ 금요일(19:30)")
    assert result.complete and result.schedule["sat"] == []


# ── 가격 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "min_price"),
    [
        ("전석 30,000원", 30000),
        ("R석 70,000원, S석 55,000원", 55000),
        ("전석 30,000 원", 30000),
        ("시야방해석  30,000원, 관찰일지석  10,000원", 10000),
        ("Royal Club 129,000원, Elite Club  69,000원", 69000),
        ("무료", 0),
        ("전석무료", 0),
    ],
)
def test_price_min(raw, min_price):
    assert parse_price(raw).min_price == min_price


def test_price_items_keep_seat_names():
    result = parse_price("R석 70,000원, S석 55,000원")
    assert result.prices == [{"seat": "R석", "price": 70000}, {"seat": "S석", "price": 55000}]


@pytest.mark.parametrize("raw", ["", None, "가격 미정", "R석 70,000원, 학생 할인 문의"])
def test_price_unparsed_returns_none(raw):
    """일부라도 해석 못 하면 더 싼 좌석을 놓칠 수 있으므로 최저가를 내지 않는다."""
    assert parse_price(raw).min_price is None


# ── 날짜 ─────────────────────────────────────────────────────────────────────


def test_kopis_date():
    assert parse_kopis_date("2026.11.21") == "2026-11-21"
    assert parse_kopis_date("2026.13.01") is None
    assert parse_kopis_date("") is None


# ── 실제 샘플 30건 ────────────────────────────────────────────────────────────


def _details():
    for path in sorted(SAMPLES.glob("detail_*.xml")):
        yield path.stem, ET.parse(path).getroot().find("db")


def test_all_real_samples_parse():
    details = list(_details())
    assert len(details) >= 20
    for name, db in details:
        assert parse_runtime(db.findtext("prfruntime")) is not None, name
        assert parse_schedule(db.findtext("dtguidance")).complete, name
        assert parse_price(db.findtext("pcseguidance")).min_price is not None, name
        assert parse_kopis_date(db.findtext("prfpdfrom")), name
