"""Tool 5개 실제 호출 1회씩 (Phase 3 완료 기준). 출력은 ok/코드/핵심 숫자만, 키는 출력하지 않는다.

실행: .venv/bin/python scripts/check_tools_live.py      (외부 호출 약 6회)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.tools import REGISTRY  # noqa: E402


def show(name, result, pick):
    status = "OK" if result["ok"] else f"FAIL {result['error']['code']}"
    extra = pick(result["data"]) if result["ok"] else ""
    print(f"{name}: {status} ({result['meta']['elapsed_ms']}ms) {extra}")
    return result


search = show("search_performances",
              REGISTRY.run("search_performances", {"date_from": "2026-11-21", "region": "대학로", "genre": "연극", "size": 5}),
              lambda d: f"후보 {len(d['items'])}건 · has_more={d['has_more']}")
pid = search["data"]["items"][0]["performance_id"] if search["ok"] else "PF304585"
detail = show("get_performance_detail", REGISTRY.run("get_performance_detail", {"performance_id": pid}),
              lambda d: f"러닝타임 {d['runtime_min']}분 · 토 {d['schedule']['sat']} · 최저가 {d['min_price']} · issues={d['issues']}")
home = show("search_places", REGISTRY.run("search_places", {"mode": "geocode", "query": "망원역"}),
            lambda d: f"1위 {d['items'][0]['name']}")
venue = detail["data"]["venue"] if detail["ok"] else {"lat": 37.5823, "lng": 127.0017}
if home["ok"] and venue.get("lat"):
    top = home["data"]["items"][0]
    show("get_transit_time", REGISTRY.run("get_transit_time", {"from_lat": venue["lat"], "from_lng": venue["lng"],
                                                               "to_lat": top["lat"], "to_lng": top["lng"]}),
         lambda d: f"{d['total_min']}분 · 환승 {d['transfers']} · {d['summary']}")
show("get_weather", REGISTRY.run("get_weather", {"lat": venue.get("lat") or 37.58, "lng": venue.get("lng") or 127.0,
                                                 "date": "2026-11-21", "hours": ["18:00", "21:00"]}),
     lambda d: f"{d['base']} · {d['summary']}")
show("get_weather (S10 범위 밖)", REGISTRY.run("get_weather", {"lat": 37.58, "lng": 127.0, "date": "2026-12-20"}),
     lambda d: "")
