"""실제 API 응답 샘플 수집 → backend/samples/ (키 제거 후 저장).

실행: .venv/bin/python scripts/collect_samples.py
- 이미 저장된 파일은 다시 호출하지 않는다(호출 절약, 재실행 안전).
- 저장 전에 redact → assert_no_secrets. 키가 남아 있으면 저장을 중단한다.
- 출력은 파일 이름·상태 코드·건수만.
"""

from __future__ import annotations

import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from api_common import (
    HYEHWA,
    KAKAO_KEYWORD,
    KAKAO_TRANSIT,
    KMA_VILAGE,
    KOPIS_BASE,
    MANGWON,
    SAMPLES_DIR,
    classify_kakao,
    classify_kakao_transit,
    classify_kma,
    classify_kopis,
    http_get,
    kakao_headers,
    kma_latest_base,
    save_sample,
)

from app import config

VIEW_DATE = "20261121"  # S1: 11월 21일 토요일
LISTS = [
    # (파일 이름, 파라미터, 상세 조회 개수)
    ("kopis/list_20261121_seoul-jongno_theater.xml",
     {"signgucode": "11", "signgucodesub": "1111", "shcate": "AAAA", "rows": 30}, 20),
    ("kopis/list_20261121_seoul_musical.xml",
     {"signgucode": "11", "shcate": "GGGA", "rows": 20}, 10),
]
KOPIS_DELAY_SEC = 0.3

index: list[dict] = []
calls = 0


def fetch_once(rel_path: str, request, classify) -> str | None:
    """파일이 있으면 읽고, 없으면 호출해서 저장한다. 실패하면 None."""
    global calls
    path = SAMPLES_DIR / rel_path
    if path.exists():
        return path.read_text(encoding="utf-8")
    r = request()
    calls += 1
    code = classify(r)
    index.append({"file": rel_path, "url": r.url, "status": r.status, "code": code,
                  "elapsed_ms": r.elapsed_ms, "fetched_at": datetime.now().isoformat(timespec="seconds")})
    print(f"  {rel_path}: {code}")
    if code != "OK":
        return None
    save_sample(rel_path, r.text)
    return r.text


def kopis(path: str, params: dict | None = None):
    def _call():
        time.sleep(KOPIS_DELAY_SEC)
        return http_get(f"{KOPIS_BASE}/{path}", {"service": config.get_str("KOPIS_API_KEY"), **(params or {})})
    return _call


def collect_kopis() -> None:
    venue_ids: set[str] = set()
    for rel, params, detail_n in LISTS:
        text = fetch_once(rel, kopis("pblprfr", {"stdate": VIEW_DATE, "eddate": VIEW_DATE, "cpage": 1,
                                                 "prfstate": "02", **params}), classify_kopis)
        if not text:
            continue
        ids = [e.text for e in ET.fromstring(text).iter("mt20id") if e.text][:detail_n]
        print(f"  목록 {rel}: 상세 {len(ids)}건 대상")
        for pid in ids:
            detail = fetch_once(f"kopis/detail_{pid}.xml", kopis(f"pblprfr/{pid}"), classify_kopis)
            if detail:
                venue_ids.update(e.text for e in ET.fromstring(detail).iter("mt10id") if e.text)
    for vid in sorted(venue_ids):
        fetch_once(f"kopis/venue_{vid}.xml", kopis(f"prfplc/{vid}"), classify_kopis)


def collect_kakao() -> None:
    fetch_once("kakao/keyword_mangwon-station.json",
               lambda: http_get(KAKAO_KEYWORD, {"query": "망원역", "size": 5}, kakao_headers()),
               classify_kakao)
    fetch_once("kakao/keyword_daehakro-nearby-restaurant.json",
               lambda: http_get(KAKAO_KEYWORD, {"query": "맛집", "x": HYEHWA[0], "y": HYEHWA[1],
                                                "radius": 500, "category_group_code": "FD6", "size": 5},
                                kakao_headers()),
               classify_kakao)
    fetch_once("kakao/transit_hyehwa_to_mangwon.json",
               lambda: http_get(KAKAO_TRANSIT, {"start_x": HYEHWA[0], "start_y": HYEHWA[1],
                                                "end_x": MANGWON[0], "end_y": MANGWON[1]}, kakao_headers()),
               classify_kakao_transit)


def collect_kma() -> None:
    base_date, base_time = kma_latest_base(datetime.now())
    fetch_once(f"kma/vilage_{base_date}_{base_time}_60-127.json",
               lambda: http_get(KMA_VILAGE, {"serviceKey": config.get_str("KMA_SERVICE_KEY"), "pageNo": 1,
                                             "numOfRows": 1500, "dataType": "JSON", "base_date": base_date,
                                             "base_time": base_time, "nx": 60, "ny": 127}),
               classify_kma)


def main() -> int:
    print("KOPIS"); collect_kopis()
    print("카카오"); collect_kakao()
    print("기상청"); collect_kma()
    if index:
        index_path = SAMPLES_DIR / "index.json"
        old = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
        save_sample("index.json", json.dumps(old + index, ensure_ascii=False, indent=2))
    failed = [e for e in index if e["code"] != "OK"]
    print(f"새로 호출 {calls}회 · 실패 {len(failed)}건")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
