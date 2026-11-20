"""Phase 1 스크립트 공통: HTTP 호출, 오류 분류, 키 제거 후 저장.

- 모든 호출에 User-Agent를 넣는다. KOPIS 방화벽이 requests 기본 UA를 400으로 막는다(실측).
- 키는 출력하지 않는다. 저장 전에 redact → assert_no_secrets 순서로 확인한다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

import requests  # noqa: E402

from app import config  # noqa: E402
from app.tools.redact import assert_no_secrets, configured_secrets, redact  # noqa: E402

USER_AGENT = "CurtainCallPlanner/0.1"
TIMEOUT_SEC = 10
SAMPLES_DIR = ROOT_DIR / "backend" / "samples"

KOPIS_BASE = "http://www.kopis.or.kr/openApi/restful"
KAKAO_KEYWORD = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_TRANSIT = "https://dapi.kakao.com/v2/routing/publictraffic"
KMA_VILAGE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
KMA_BASE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)

# 대표 좌표 (카카오 경도 x, 위도 y)
HYEHWA = (127.001699, 37.582299)
MANGWON = (126.910182, 37.555996)


@dataclass
class Response:
    status: int | None  # None이면 네트워크 오류
    text: str
    url: str  # 키를 지운 URL
    elapsed_ms: int
    error: str | None = None  # TIMEOUT / CONNECTION_ERROR


def http_get(url: str, params: dict, headers: dict | None = None) -> Response:
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    started = time.monotonic()
    prepared = requests.Request("GET", url, params=params).prepare().url or url
    safe_url = redact(prepared, configured_secrets())
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SEC)
        resp.encoding = resp.encoding or "utf-8"
        return Response(resp.status_code, resp.text, safe_url, _ms(started))
    except requests.Timeout:
        return Response(None, "", safe_url, _ms(started), "TIMEOUT")
    except requests.RequestException:
        return Response(None, "", safe_url, _ms(started), "CONNECTION_ERROR")


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ── 오류 분류 (출력용 코드만) ──────────────────────────────────────────────────


def classify_kopis(r: Response) -> str:
    if r.error:
        return r.error
    if r.status == 400 and "Request Blocked" in r.text:
        return "BLOCKED_BY_FIREWALL"
    if r.status != 200:
        return f"HTTP_{r.status}"
    m = re.search(r"<returncode>(\d+)</returncode>", r.text)
    if m and m.group(1) != "00":
        return "MISSING_API_KEY" if m.group(1) == "02" else f"KOPIS_{m.group(1)}"
    return "OK" if "<dbs" in r.text else "UNEXPECTED_BODY"


def classify_kakao(r: Response) -> str:
    if r.error:
        return r.error
    if r.status in (401, 403) or "AccessDeniedError" in r.text:
        return "MISSING_API_KEY"
    if r.status == 400 and '"code":-10' in r.text.replace(" ", ""):
        return "RATE_LIMITED"
    if r.status != 200:
        return f"HTTP_{r.status}"
    return "OK"


def classify_kakao_transit(r: Response) -> str:
    base = classify_kakao(r)
    if base != "OK":
        return base
    try:
        status = json.loads(r.text).get("status")
    except ValueError:
        return "UNEXPECTED_BODY"
    return "OK" if status == "OK" else f"STATUS_{status}"


def classify_kma(r: Response) -> str:
    if r.error:
        return r.error
    if "SERVICE_KEY_IS_NOT_REGISTERED" in r.text:
        return "MISSING_API_KEY"
    if r.status != 200:
        return f"HTTP_{r.status}"
    try:
        code = json.loads(r.text)["response"]["header"]["resultCode"]
    except (ValueError, KeyError, TypeError):
        return "UNEXPECTED_BODY"
    return "OK" if code == "00" else f"KMA_{code}"


# ── 요청 파라미터 ─────────────────────────────────────────────────────────────


def kakao_headers() -> dict:
    return {"Authorization": f"KakaoAK {config.get_str('KAKAO_REST_API_KEY')}"}


def kma_latest_base(now: datetime) -> tuple[str, str]:
    """발표 10분 뒤부터 쓸 수 있다고 보고 가장 최근 발표 시각을 고른다(스크립트용 단순판)."""
    ready = now - timedelta(minutes=10)
    for day_offset in (0, 1):
        day = ready - timedelta(days=day_offset)
        hours = [h for h in KMA_BASE_HOURS if day_offset or h <= ready.hour]
        if hours:
            return day.strftime("%Y%m%d"), f"{max(hours):02d}00"
    raise AssertionError("unreachable")


# ── 저장 ─────────────────────────────────────────────────────────────────────


def save_sample(rel_path: str, text: str) -> Path:
    secrets = configured_secrets()
    clean = redact(text, secrets)
    assert_no_secrets(clean, secrets)
    path = SAMPLES_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean, encoding="utf-8")
    return path
