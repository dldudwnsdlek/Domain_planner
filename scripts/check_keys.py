"""외부 API 키 확인.

실행:
  .venv/bin/python scripts/check_keys.py          # 설정 여부만 (boolean, 호출 0회)
  .venv/bin/python scripts/check_keys.py --live   # 4개 API 1회씩 실제 호출 → OK / 오류 코드

키 값과 응답 본문은 출력하지 않는다.
"""

from __future__ import annotations

import sys
from datetime import datetime

from api_common import (
    HYEHWA,
    KAKAO_KEYWORD,
    KAKAO_TRANSIT,
    KMA_VILAGE,
    KOPIS_BASE,
    MANGWON,
    classify_kakao,
    classify_kakao_transit,
    classify_kma,
    classify_kopis,
    http_get,
    kakao_headers,
    kma_latest_base,
)

from app import config

KEYS = {
    "kopis": "KOPIS_API_KEY",
    "kakao": "KAKAO_REST_API_KEY",
    "kma": "KMA_SERVICE_KEY",
    "llm": "GMS_KEY",
    "llm_base_url": "LLM_BASE_URL",
}


def live_checks() -> list[tuple[str, str, int]]:
    today = datetime.now().strftime("%Y%m%d")
    base_date, base_time = kma_latest_base(datetime.now())
    calls = [
        (
            "KOPIS 공연목록",
            classify_kopis,
            lambda: http_get(
                f"{KOPIS_BASE}/pblprfr",
                {"service": config.get_str("KOPIS_API_KEY"), "stdate": today,
                 "eddate": today, "cpage": 1, "rows": 1},
            ),
        ),
        (
            "카카오 키워드 검색",
            classify_kakao,
            lambda: http_get(KAKAO_KEYWORD, {"query": "망원역", "size": 1}, kakao_headers()),
        ),
        (
            "카카오 대중교통",
            classify_kakao_transit,
            lambda: http_get(
                KAKAO_TRANSIT,
                {"start_x": HYEHWA[0], "start_y": HYEHWA[1], "end_x": MANGWON[0], "end_y": MANGWON[1]},
                kakao_headers(),
            ),
        ),
        (
            "기상청 단기예보",
            classify_kma,
            lambda: http_get(
                KMA_VILAGE,
                {"serviceKey": config.get_str("KMA_SERVICE_KEY"), "pageNo": 1, "numOfRows": 10,
                 "dataType": "JSON", "base_date": base_date, "base_time": base_time,
                 "nx": 60, "ny": 127},
            ),
        ),
    ]
    results = []
    for name, classify, call in calls:
        r = call()
        results.append((name, classify(r), r.elapsed_ms))
    return results


def main(argv: list[str]) -> int:
    for label, env in KEYS.items():
        print(f"{label}: {bool(config.get_str(env))}")
    if "--live" not in argv:
        return 0
    print("--- 실제 호출 (각 1회)")
    results = live_checks()
    for name, code, ms in results:
        print(f"{name}: {code} ({ms}ms)")
    return 0 if all(code == "OK" for _, code, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
