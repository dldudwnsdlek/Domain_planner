"""KOPIS Tool: search_performances (F3002), get_performance_detail (F3003).

- KOPIS는 오류도 HTTP 200으로 준다 → 본문의 returncode를 검사한다(02 = 키 오류).
- 공연장은 여러 공연이 공유하므로 시설 조회는 캐시한다.
"""

from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import config
from app.tools import base
from app.tools.base import REGISTRY, ToolError
from app.tools.parsers import parse_kopis_date, parse_price, parse_runtime, parse_schedule
from app.tools.region_alias import resolve_region

SOURCE = "KOPIS"
BASE_URL = "http://www.kopis.or.kr/openApi/restful"
GENRE_CODES = {"연극": "AAAA", "뮤지컬": "GGGA", "클래식": "CCCA"}  # 공통코드 문서로 확인한 3개만
MAX_RANGE_DAYS = 31
BLOCK_RETRY_DELAY_SEC = 1.0


def _today() -> date:
    return datetime.now().date()


def _key() -> str:
    key = config.get_str("KOPIS_API_KEY")
    if not key:
        raise ToolError(base.MISSING_API_KEY, "KOPIS API 키가 설정되지 않았어요.")
    return key


class Throttle:
    """KOPIS 요청 조절: 동시 요청 수와 요청 시작 간격을 제한한다.

    실측(2026-11-20): 상세 조회를 동시에 5개씩 보내면 KOPIS 방화벽이 일부를 HTTP 400 'Request Blocked'로
    약 20ms 만에 거절했다(실행 로그 detail=HTTP_400_BLOCKED로 확인). 작업 스레드 수(병렬 5)와 별개로
    실제 KOPIS 요청은 이 조절기를 거친다.
    """

    def __init__(self, max_concurrent: int = 4, min_interval: float = 0.15) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._lock = threading.Lock()
        self._next_start = 0.0
        self.min_interval = min_interval

    @contextmanager
    def slot(self):
        with self._slots:
            with self._lock:
                wait = self._next_start - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self._next_start = time.monotonic() + self.min_interval
            yield


THROTTLE = Throttle()


def _is_blocked(resp: base.HttpResponse) -> bool:
    return resp.status == 400 and "Request Blocked" in resp.text


def _http(url: str, query: dict) -> base.HttpResponse:
    with THROTTLE.slot():
        return base.http_get(url, query)


def _get(path: str, params: dict | None = None) -> ET.Element:
    url, query = f"{BASE_URL}/{path}", {"service": _key(), **(params or {})}
    resp = _http(url, query)
    if _is_blocked(resp):
        # 방화벽 순간 차단 → 잠시 기다렸다가 1회만 재시도한다(명세: Tool 안에서 1회 재시도).
        time.sleep(BLOCK_RETRY_DELAY_SEC)
        resp = _http(url, query)
    if _is_blocked(resp):
        raise ToolError(base.UPSTREAM_ERROR, "KOPIS가 요청을 차단했어요.", "HTTP_400_BLOCKED")
    if resp.status != 200:
        raise ToolError(base.UPSTREAM_ERROR, "KOPIS 응답이 올바르지 않아요.", f"HTTP_{resp.status}")
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        raise ToolError(base.UPSTREAM_ERROR, "KOPIS 응답을 해석하지 못했어요.", "XML_PARSE") from exc
    code = root.findtext("db/returncode")
    if code and code != "00":
        if code == "02":
            raise ToolError(base.MISSING_API_KEY, "KOPIS API 키가 올바르지 않아요.", "KOPIS_RC_02")
        raise ToolError(base.UPSTREAM_ERROR, "KOPIS가 오류를 돌려줬어요.", f"KOPIS_RC_{code}")
    return root


def _text(el: ET.Element, tag: str) -> str:
    return (el.findtext(tag) or "").strip()


def _iso(raw: str | None, field: str) -> str:
    try:
        return datetime.strptime(raw or "", "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ToolError(base.INVALID_INPUT, f"{field}는 YYYY-MM-DD 형식이어야 해요.") from exc


# ── search_performances ──────────────────────────────────────────────────────


class SearchPerformancesArgs(BaseModel):
    date_from: str | None = Field(default=None, description="관람 시작 날짜 YYYY-MM-DD. 없으면 오늘")
    date_to: str | None = Field(default=None, description="관람 끝 날짜 YYYY-MM-DD. 없으면 date_from과 같음 (최대 31일)")
    region: str | None = Field(default=None, description="지역 이름 (예: 대학로, 강남구). 없으면 서울 전체")
    genre: Literal["연극", "뮤지컬", "클래식"] | None = Field(default=None, description="장르. 없으면 전체")
    keyword: str | None = Field(default=None, description="작품명 검색어")
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


@REGISTRY.register(
    name="search_performances",
    description=(
        "날짜·지역·장르 조건으로 그날 볼 수 있는 공연 후보를 찾을 때 사용한다. 사용자가 작품을 정하지 않았거나, "
        "작품명만 알고 공연 ID가 필요할 때 쓴다. 러닝타임·회차·가격은 주지 않으므로, 판단하려면 "
        "get_performance_detail을 이어서 호출해야 한다."
    ),
    args_model=SearchPerformancesArgs,
    source=SOURCE,
)
def search_performances(args: SearchPerformancesArgs):
    notes: list[str] = []
    if args.date_from:
        date_from = _iso(args.date_from, "date_from")
    else:
        date_from = _today().isoformat()
        notes.append(f"날짜를 말하지 않아 오늘({date_from}) 기준으로 찾았어요.")
    date_to = _iso(args.date_to, "date_to") if args.date_to else date_from
    span = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days
    if span < 0 or span > MAX_RANGE_DAYS:
        raise ToolError(base.INVALID_INPUT, "조회 기간은 31일 이내여야 해요.")

    if args.region:
        region = resolve_region(args.region)
        if region.label not in args.region:
            notes.append(f"'{args.region}'을(를) {region.label}(으)로 바꿔 조회했어요.")
    else:
        region = resolve_region("서울")

    params = {"stdate": date_from.replace("-", ""), "eddate": date_to.replace("-", ""),
              "cpage": args.page, "rows": args.size, "signgucode": region.sido_code}
    if region.gugun_code:
        params["signgucodesub"] = region.gugun_code
    genre_code = GENRE_CODES.get(args.genre) if args.genre else None
    if genre_code:
        params["shcate"] = genre_code
    if args.keyword:
        params["shprfnm"] = args.keyword

    root = _get("pblprfr", params)
    items = [
        {
            "performance_id": _text(db, "mt20id"),
            "title": _text(db, "prfnm"),
            "genre": _text(db, "genrenm"),
            "venue_name": _text(db, "fcltynm"),
            "period_from": parse_kopis_date(_text(db, "prfpdfrom")),
            "period_to": parse_kopis_date(_text(db, "prfpdto")),
            "state": _text(db, "prfstate"),
            "poster_url": _text(db, "poster"),
            "open_run": _text(db, "openrun") == "Y",
        }
        for db in root.findall("db")
        if _text(db, "mt20id")
    ]
    if not items:
        raise ToolError(base.NO_RESULT, "조건에 맞는 공연을 찾지 못했어요.")
    query_used = {"date_from": date_from, "date_to": date_to, "region_code": region.sido_code,
                  "district_code": region.gugun_code, "genre_code": genre_code,
                  "daehakro_only": region.daehakro_only, "keyword": args.keyword,
                  "page": args.page, "size": args.size}
    return {"query_used": query_used, "items": items, "has_more": len(items) == args.size}, {"notes": notes}


# ── get_performance_detail ───────────────────────────────────────────────────


class PerformanceDetailArgs(BaseModel):
    performance_id: str = Field(description="search_performances 결과의 공연 ID (예: PF123456)", min_length=3)
    include_venue: bool = Field(
        default=True,
        description="공연장 주소·좌표까지 필요하면 true. 판정 전에 여러 후보를 조회할 때는 false로 두어 호출을 줄인다")


def _venue(venue_id: str) -> dict:
    def fetch() -> dict:
        db = _get(f"prfplc/{venue_id}").find("db")
        if db is None:
            raise ToolError(base.NOT_FOUND, "공연시설 정보를 찾지 못했어요.")
        try:
            lat, lng = float(_text(db, "la")), float(_text(db, "lo"))
        except ValueError:
            lat = lng = None
        return {"venue_id": venue_id, "name": _text(db, "fcltynm"), "address": _text(db, "adres"),
                "lat": lat, "lng": lng}
    return base.cached(f"venue:{venue_id}", fetch)


@REGISTRY.register(
    name="get_performance_detail",
    description=(
        "후보 공연의 러닝타임·요일별 회차·가격·공연장 위치를 확인할 때 사용한다. 시간·예산 조건을 판단하기 전에 "
        "반드시 필요하다. 공연 ID는 search_performances 결과에서 얻는다."
    ),
    args_model=PerformanceDetailArgs,
    source=SOURCE,
)
def get_performance_detail(args: PerformanceDetailArgs):
    """공연 상세(캐시) + 필요할 때만 공연장 좌표(캐시).

    실측: KOPIS는 동시 처리량이 낮아(건당 약 1.3초, 동시 요청 시 방화벽 차단) 호출 수를 줄이는 것이 중요하다.
    상세마다 시설 조회를 붙이면 호출이 두 배가 되므로, 좌표는 이동시간·날씨가 필요한 공연에만 조회한다.
    """
    core = base.cached(f"detail:{args.performance_id}", lambda: _detail_core(args.performance_id))
    data = {**core, "venue": dict(core["venue"]), "issues": list(core["issues"]), "venue_checked": args.include_venue}
    notes: list[str] = []
    if args.include_venue:
        if data["venue"].get("venue_id"):
            try:
                data["venue"] = _venue(data["venue"]["venue_id"])
            except ToolError:
                notes.append("공연장 위치를 확인하지 못해 이동시간·날씨는 판정 불가로 둘 수 있어요.")
        if data["venue"].get("lat") is None:
            data["issues"].append("NO_VENUE_LOCATION")
    return data, {"notes": notes}


def _detail_core(performance_id: str) -> dict:
    db = _get(f"pblprfr/{performance_id}").find("db")
    if db is None or not _text(db, "mt20id"):
        raise ToolError(base.NOT_FOUND, "공연 정보를 찾지 못했어요.")

    issues: list[str] = []
    runtime_raw, schedule_raw, price_raw = _text(db, "prfruntime"), _text(db, "dtguidance"), _text(db, "pcseguidance")
    runtime = parse_runtime(runtime_raw)
    if runtime is None:
        issues.append(base.NO_RUNTIME)
    schedule = parse_schedule(schedule_raw)
    if not schedule.complete:
        issues.append(base.SCHEDULE_UNPARSED)
    price = parse_price(price_raw)
    if price.min_price is None:
        issues.append(base.PRICE_UNPARSED)

    links = [{"name": _text(r, "relatenm"), "url": _text(r, "relateurl")}
             for r in db.findall("relates/relate") if _text(r, "relateurl")]
    return {
        "performance_id": performance_id,
        "title": _text(db, "prfnm"),
        "genre": _text(db, "genrenm"),
        "age_rating": _text(db, "prfage"),
        "period_from": parse_kopis_date(_text(db, "prfpdfrom")),
        "period_to": parse_kopis_date(_text(db, "prfpdto")),
        "runtime_min": runtime, "runtime_raw": runtime_raw,
        "schedule": schedule.schedule, "schedule_raw": schedule_raw,
        "prices": price.prices, "min_price": price.min_price, "price_raw": price_raw,
        "venue": {"venue_id": _text(db, "mt10id"), "name": _text(db, "fcltynm"), "address": None,
                  "lat": None, "lng": None},
        "daehakro": _text(db, "daehakro") == "Y",
        "poster_url": _text(db, "poster"),
        "ticket_links": links,
        "issues": issues,
    }
