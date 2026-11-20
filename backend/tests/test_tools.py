"""Tool 5개 — 실제 샘플로 정상 경로, 가짜 응답으로 실패 경로 (네트워크 없음)."""

import json
import pathlib
import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

from app.tools import REGISTRY, base, kma, kopis
from app.tools.region_alias import resolve_region

SAMPLES = pathlib.Path(__file__).resolve().parents[1] / "samples"
DETAIL_ID = "PF304585"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for name in ("KOPIS_API_KEY", "KAKAO_REST_API_KEY", "KMA_SERVICE_KEY"):
        monkeypatch.setenv(name, "fake-key")
    base.clear_cache()


def fake_http(monkeypatch, responder):
    calls = []

    def _get(url, params, headers=None):
        calls.append((url, params))
        status, text = responder(url, params)
        return base.HttpResponse(status, text)

    monkeypatch.setattr(base, "http_get", _get)
    return calls


def sample(rel):
    return (SAMPLES / rel).read_text(encoding="utf-8")


def kopis_samples(url, params):
    if url.endswith("/pblprfr"):
        return 200, sample("kopis/list_20261121_seoul-jongno_theater.xml")
    if "/pblprfr/" in url:
        return 200, sample(f"kopis/detail_{url.rsplit('/', 1)[1]}.xml")
    if "/prfplc/" in url:
        return 200, sample(f"kopis/venue_{url.rsplit('/', 1)[1]}.xml")
    raise AssertionError(url)


KOPIS_KEY_ERROR = (200, "<dbs><db><returncode>02</returncode><errmsg>SERVICE KEY IS NOT REGISTERED ERROR</errmsg></db></dbs>")


# ── 레지스트리 (F3001) ────────────────────────────────────────────────────────


def test_five_external_tools_registered_with_usage_descriptions():
    names = set(REGISTRY.names())
    assert names == {"search_performances", "get_performance_detail", "search_places",
                     "get_transit_time", "get_weather"}
    for spec in REGISTRY.openai_specs():
        assert "사용한다" in spec["function"]["description"]  # '언제 쓰는지'를 적는다
        assert REGISTRY.get(spec["function"]["name"]).kind == "external"


# ── 지역 별칭 ─────────────────────────────────────────────────────────────────


def test_region_alias_daehakro():
    r = resolve_region("대학로")
    assert (r.sido_code, r.gugun_code, r.daehakro_only) == ("11", "1111", True)


@pytest.mark.parametrize("text", ["서울 강남구", "강남구", "강남"])
def test_region_gu_variants(text):
    assert resolve_region(text).gugun_code == "1168"


def test_region_ambiguous_and_unknown():
    with pytest.raises(base.ToolError) as exc:
        resolve_region("중구")
    assert exc.value.code == "AMBIGUOUS"
    assert resolve_region("서울 중구").gugun_code == "1114"
    with pytest.raises(base.ToolError) as exc:
        resolve_region("아틀란티스")
    assert exc.value.code == "INVALID_INPUT"


# ── search_performances (F3002) ──────────────────────────────────────────────


def test_search_performances_from_sample(monkeypatch):
    calls = fake_http(monkeypatch, kopis_samples)
    r = REGISTRY.run("search_performances", {"date_from": "2026-11-21", "region": "대학로", "genre": "연극", "size": 30})
    assert r["ok"] is True
    assert r["data"]["query_used"] == {"date_from": "2026-11-21", "date_to": "2026-11-21", "region_code": "11",
                                       "district_code": "1111", "genre_code": "AAAA", "daehakro_only": True,
                                       "keyword": None, "page": 1, "size": 30}
    assert len(r["data"]["items"]) == 30 and r["data"]["has_more"] is True
    first = r["data"]["items"][0]
    assert first["performance_id"].startswith("PF") and first["period_from"].count("-") == 2
    assert any("종로구" in n for n in r["meta"]["notes"])
    assert calls[0][1]["stdate"] == "20261121" and calls[0][1]["signgucodesub"] == "1111"


def test_search_defaults_to_today_and_says_so(monkeypatch):
    fake_http(monkeypatch, kopis_samples)
    monkeypatch.setattr(kopis, "_today", lambda: datetime(2026, 11, 20).date())
    r = REGISTRY.run("search_performances", {})
    assert r["data"]["query_used"]["date_from"] == "2026-11-20"
    assert r["data"]["query_used"]["region_code"] == "11"  # 지역 없으면 서울 전체
    assert any("오늘" in n for n in r["meta"]["notes"])


def test_search_rejects_range_over_31_days(monkeypatch):
    calls = fake_http(monkeypatch, kopis_samples)
    r = REGISTRY.run("search_performances", {"date_from": "2026-11-01", "date_to": "2026-12-15"})
    assert r["error"]["code"] == "INVALID_INPUT" and calls == []


def test_search_missing_key_does_not_call(monkeypatch):
    monkeypatch.setenv("KOPIS_API_KEY", "")
    calls = fake_http(monkeypatch, kopis_samples)
    r = REGISTRY.run("search_performances", {"date_from": "2026-11-21"})
    assert r["error"]["code"] == "MISSING_API_KEY" and calls == []


def test_search_kopis_key_error_body_is_missing_api_key(monkeypatch):
    fake_http(monkeypatch, lambda u, p: KOPIS_KEY_ERROR)
    assert REGISTRY.run("search_performances", {"date_from": "2026-11-21"})["error"]["code"] == "MISSING_API_KEY"


def test_search_empty_is_no_result(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (200, "<dbs></dbs>"))
    assert REGISTRY.run("search_performances", {"date_from": "2026-11-21"})["error"]["code"] == "NO_RESULT"


# ── get_performance_detail (F3003) ───────────────────────────────────────────


def test_detail_from_sample_with_venue(monkeypatch):
    calls = fake_http(monkeypatch, kopis_samples)
    r = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})
    d = r["data"]
    assert r["ok"] is True
    assert (d["runtime_min"], d["min_price"], d["issues"]) == (90, 30000, [])
    assert d["schedule"]["sat"] == ["14:00", "18:00"] and d["schedule"]["mon"] == []
    assert d["period_from"] == "2026-11-19" and d["daehakro"] is True
    assert d["venue"]["lat"] and d["venue"]["lng"] and d["venue"]["venue_id"].startswith("FC")
    assert d["ticket_links"][0]["url"].startswith("http")
    REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})
    assert len(calls) == 2  # 상세 1 + 시설 1, 두 번째 요청은 캐시


def test_detail_records_issues_instead_of_inventing(monkeypatch):
    root = ET.fromstring(sample(f"kopis/detail_{DETAIL_ID}.xml"))
    db = root.find("db")
    db.find("prfruntime").text = ""
    db.find("dtguidance").text = "예매처 참고"
    db.find("pcseguidance").text = "가격 미정"
    broken = ET.tostring(root, encoding="unicode")
    fake_http(monkeypatch, lambda u, p: (200, broken) if "/pblprfr/" in u else kopis_samples(u, p))
    d = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})["data"]
    assert d["runtime_min"] is None and d["min_price"] is None
    assert d["issues"] == ["NO_RUNTIME", "SCHEDULE_UNPARSED", "PRICE_UNPARSED"]


def test_detail_not_found(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (200, "<dbs></dbs>"))
    assert REGISTRY.run("get_performance_detail", {"performance_id": "PF000000"})["error"]["code"] == "NOT_FOUND"


def test_detail_venue_failure_keeps_detail(monkeypatch):
    def responder(u, p):
        if "/prfplc/" in u:
            raise base.ToolError("TIMEOUT", "늦어요")
        return kopis_samples(u, p)

    fake_http(monkeypatch, responder)
    r = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})
    assert r["ok"] is True and r["data"]["venue"]["lat"] is None and "NO_VENUE_LOCATION" in r["data"]["issues"]


# ── search_places (F3004) ────────────────────────────────────────────────────


def test_geocode_from_sample(monkeypatch):
    calls = fake_http(monkeypatch, lambda u, p: (200, sample("kakao/keyword_mangwon-station.json")))
    r = REGISTRY.run("search_places", {"mode": "geocode", "query": "망원역"})
    top = r["data"]["items"][0]
    assert r["ok"] and top["name"] == "망원역 6호선" and 37 < top["lat"] < 38 and 126 < top["lng"] < 127
    assert calls[0][1]["query"] == "망원역"


def test_nearby_requires_coordinates(monkeypatch):
    calls = fake_http(monkeypatch, lambda u, p: (200, "{}"))
    r = REGISTRY.run("search_places", {"mode": "nearby", "category": "restaurant"})
    assert r["error"]["code"] == "INVALID_INPUT" and calls == []


def test_nearby_uses_category_code(monkeypatch):
    calls = fake_http(monkeypatch, lambda u, p: (200, sample("kakao/keyword_daehakro-nearby-restaurant.json")))
    r = REGISTRY.run("search_places", {"mode": "nearby", "lat": 37.58, "lng": 127.0, "category": "restaurant"})
    assert r["ok"] and calls[0][1]["category_group_code"] == "FD6"


def test_places_no_result_and_auth_error(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (200, json.dumps({"documents": [], "meta": {"total_count": 0}})))
    assert REGISTRY.run("search_places", {"mode": "geocode", "query": "없는곳"})["error"]["code"] == "NO_RESULT"
    fake_http(monkeypatch, lambda u, p: (401, '{"errorType":"AccessDeniedError","message":"wrong appKey"}'))
    assert REGISTRY.run("search_places", {"mode": "geocode", "query": "망원역"})["error"]["code"] == "MISSING_API_KEY"


def test_geocode_ambiguous_when_top_results_in_different_sido(monkeypatch):
    docs = [{"place_name": "중앙시장", "address_name": f"{sido} 중구 어딘가", "road_address_name": "",
             "category_group_name": "", "x": "127.0", "y": "37.5", "place_url": "", "distance": ""}
            for sido in ("서울", "부산", "대구")]
    fake_http(monkeypatch, lambda u, p: (200, json.dumps({"documents": docs, "meta": {}})))
    assert REGISTRY.run("search_places", {"mode": "geocode", "query": "중앙시장"})["error"]["code"] == "AMBIGUOUS"


# ── get_transit_time ─────────────────────────────────────────────────────────

HYEHWA = {"from_lat": 37.582299, "from_lng": 127.001699, "to_lat": 37.555996, "to_lng": 126.910182}


def test_transit_from_sample_picks_fastest_route(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (200, sample("kakao/transit_hyehwa_to_mangwon.json")))
    r = REGISTRY.run("get_transit_time", HYEHWA)
    d = r["data"]
    assert (d["total_min"], d["transfers"], d["route_type"]) == (35, 2, "SUBWAY")  # 2080초 → 35분(올림)
    assert d["summary"] == "4호선 → 5호선 → 6호선"
    assert d["map_url"].startswith("https://map.kakao.com/")
    assert r["meta"]["estimated"] is True  # 시간대·막차 미반영


def test_transit_equal_points_gives_walking_estimate(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (200, '{"status":"EQUAL_POINTS"}'))
    r = REGISTRY.run("get_transit_time", {"from_lat": 37.58, "from_lng": 127.0, "to_lat": 37.581, "to_lng": 127.0})
    assert r["ok"] and r["data"]["issues"] == ["TOO_CLOSE"] and r["data"]["route_type"] == "WALK_ESTIMATE"
    assert r["data"]["total_min"] == 2  # 약 111m ÷ 시속 4km ≈ 1.7분 → 올림


@pytest.mark.parametrize(("status", "code"), [("STARTNODES_NULL", "NO_RESULT"), ("INVALID_REQUEST", "INVALID_INPUT")])
def test_transit_status_mapping(monkeypatch, status, code):
    fake_http(monkeypatch, lambda u, p: (200, json.dumps({"status": status})))
    assert REGISTRY.run("get_transit_time", HYEHWA)["error"]["code"] == code


def test_transit_rate_limited(monkeypatch):
    fake_http(monkeypatch, lambda u, p: (400, '{"code":-10,"msg":"limit"}'))
    assert REGISTRY.run("get_transit_time", HYEHWA)["error"]["code"] == "RATE_LIMITED"


# ── get_weather ──────────────────────────────────────────────────────────────

KMA_SAMPLE = "kma/vilage_20261120_0800_60-127.json"


@pytest.fixture
def kma_now(monkeypatch):
    monkeypatch.setattr(kma, "_now", lambda: datetime(2026, 11, 20, 8, 41))


def test_weather_from_sample(monkeypatch, kma_now):
    calls = fake_http(monkeypatch, lambda u, p: (200, sample(KMA_SAMPLE)))
    r = REGISTRY.run("get_weather", {"lat": 37.5822, "lng": 127.0017, "date": "2026-11-21", "hours": ["19:00", "21:00"]})
    d = r["data"]
    assert r["ok"] and d["grid"] == {"nx": 60, "ny": 127} and d["base"] == "2026-11-20 08:00 발표"
    assert [h["time"] for h in d["hours"]] == ["19:00", "21:00"]
    assert all(isinstance(h["pop"], int) and isinstance(h["tmp"], int) for h in d["hours"])
    assert d["hours"][0]["sky"] in {"맑음", "구름많음", "흐림"}
    assert calls[0][1]["numOfRows"] >= 1100  # 실측 totalCount가 1000을 넘을 수 있음
    assert d["summary"]


def test_weather_out_of_range_never_calls_api(monkeypatch, kma_now):
    calls = fake_http(monkeypatch, lambda u, p: (200, sample(KMA_SAMPLE)))
    r = REGISTRY.run("get_weather", {"lat": 37.58, "lng": 127.0, "date": "2026-12-20", "hours": ["19:00"]})
    assert r["error"]["code"] == "OUT_OF_RANGE" and calls == []


def test_weather_key_error_403(monkeypatch, kma_now):
    body = '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"errMsg":"SERVICE_KEY_IS_NOT_REGISTERED_ERROR","returnReasonCode":"30"}}}'
    fake_http(monkeypatch, lambda u, p: (403, body))
    r = REGISTRY.run("get_weather", {"lat": 37.58, "lng": 127.0, "date": "2026-11-21"})
    assert r["error"]["code"] == "MISSING_API_KEY"


def test_weather_missing_key_does_not_call(monkeypatch, kma_now):
    monkeypatch.setenv("KMA_SERVICE_KEY", "")
    calls = fake_http(monkeypatch, lambda u, p: (200, sample(KMA_SAMPLE)))
    r = REGISTRY.run("get_weather", {"lat": 37.58, "lng": 127.0, "date": "2026-11-21"})
    assert r["error"]["code"] == "MISSING_API_KEY" and calls == []


def test_kopis_firewall_block_is_reported_with_detail(monkeypatch):
    monkeypatch.setattr(kopis, "BLOCK_RETRY_DELAY_SEC", 0)
    calls = fake_http(monkeypatch, lambda u, p: (400, "<html>Request Blocked</html>"))
    r = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})
    assert r["error"]["code"] == "UPSTREAM_ERROR" and r["meta"]["detail"] == "HTTP_400_BLOCKED"
    assert len(calls) == 2  # 차단은 잠시 기다렸다가 1회만 재시도


def test_kopis_block_then_success_recovers(monkeypatch):
    """실측(2026-11-20): 병렬 상세 조회 중 일부가 약 20ms 만에 연속 실패 → 잠시 뒤 재시도로 회복."""
    monkeypatch.setattr(kopis, "BLOCK_RETRY_DELAY_SEC", 0)
    blocked_once = {"done": False}

    def responder(u, p):
        if "/pblprfr/" in u and not blocked_once["done"]:
            blocked_once["done"] = True
            return 400, "<html>Request Blocked</html>"
        return kopis_samples(u, p)

    fake_http(monkeypatch, responder)
    r = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})
    assert r["ok"] is True and r["data"]["runtime_min"] == 90


def test_kopis_throttle_limits_concurrency_and_spacing():
    """실측: 병렬 5에서 KOPIS 방화벽 400 'Request Blocked'가 간헐 발생 → 동시 3개·간격 제한."""
    import threading
    import time as _time

    throttle = kopis.Throttle(max_concurrent=2, min_interval=0.05)
    active, peak, starts = [0], [0], []
    lock = threading.Lock()

    def work():
        with throttle.slot():
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
                starts.append(_time.monotonic())
            _time.sleep(0.05)
            with lock:
                active[0] -= 1

    threads = [threading.Thread(target=work) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    starts.sort()
    assert peak[0] <= 2
    assert all(b - a >= 0.045 for a, b in zip(starts, starts[1:]))


def test_detail_without_venue_skips_facility_call(monkeypatch):
    """판정 전 대량 조회에서는 공연장 좌표를 건너뛰어 KOPIS 호출을 절반으로 줄인다."""
    calls = fake_http(monkeypatch, kopis_samples)
    r = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID, "include_venue": False})
    d = r["data"]
    assert r["ok"] and d["runtime_min"] == 90 and d["venue"]["venue_id"].startswith("FC")
    assert d["venue"]["lat"] is None and d["venue_checked"] is False and "NO_VENUE_LOCATION" not in d["issues"]
    assert [u for u, _ in calls if "/prfplc/" in u] == []
    full = REGISTRY.run("get_performance_detail", {"performance_id": DETAIL_ID})["data"]
    assert full["venue"]["lat"] and full["venue_checked"] is True
    assert len([u for u, _ in calls if "/pblprfr/" in u]) == 1  # 상세는 캐시, 시설만 추가 조회
