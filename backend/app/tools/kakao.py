"""카카오맵 Tool: search_places (F3004 보조 정보), get_transit_time (귀가 제약).

- 인증: Authorization: KakaoAK {REST 키} (로컬·대중교통 같은 키)
- 대중교통은 하루 1,000건 → 경로를 좌표 기준으로 캐시하고, 판정 2단계에서 1차 통과 후보만 조회한다.
- 대중교통 API에는 출발 시각 파라미터가 없다 → 시간대·막차 미반영(meta.estimated=true)으로 표시한다.
"""

from __future__ import annotations

import json
import math
from typing import Literal

from pydantic import BaseModel, Field

from app import config
from app.tools import base
from app.tools.base import REGISTRY, ToolError

SOURCE = "KAKAO"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
TRANSIT_URL = "https://dapi.kakao.com/v2/routing/publictraffic"
CATEGORY = {"restaurant": ("FD6", "맛집"), "cafe": ("CE7", "카페"), "subway": ("SW8", "지하철역")}
WALK_KMH = 4.0
TOO_CLOSE_KM = 1.0


def _headers() -> dict:
    key = config.get_str("KAKAO_REST_API_KEY")
    if not key:
        raise ToolError(base.MISSING_API_KEY, "카카오 REST API 키가 설정되지 않았어요.")
    return {"Authorization": f"KakaoAK {key}"}


def _get_json(url: str, params: dict) -> dict:
    resp = base.http_get(url, params, _headers())
    compact = resp.text.replace(" ", "")
    if resp.status in (401, 403) or "AccessDeniedError" in resp.text:
        raise ToolError(base.MISSING_API_KEY, "카카오 REST API 키가 올바르지 않거나 카카오맵 사용 설정이 꺼져 있어요.")
    if resp.status == 400 and '"code":-10' in compact:
        raise ToolError(base.RATE_LIMITED, "카카오 API 하루 호출 한도를 넘었어요.")
    if resp.status != 200:
        raise ToolError(base.INVALID_INPUT, "카카오 API가 요청을 거절했어요. 입력값을 확인해 주세요.")
    try:
        return json.loads(resp.text)
    except ValueError as exc:
        raise ToolError(base.UPSTREAM_ERROR, "카카오 응답을 해석하지 못했어요.") from exc


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """하버사인 직선거리(km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ── search_places ────────────────────────────────────────────────────────────


class SearchPlacesArgs(BaseModel):
    mode: Literal["geocode", "nearby"] = Field(description="geocode: 장소 이름 → 좌표 / nearby: 좌표 주변 장소")
    query: str | None = Field(default=None, description="geocode일 때 필수. 장소 이름이나 주소 (예: 망원역)")
    lat: float | None = Field(default=None, ge=-90, le=90, description="nearby일 때 필수. 위도")
    lng: float | None = Field(default=None, ge=-180, le=180, description="nearby일 때 필수. 경도")
    category: Literal["restaurant", "cafe", "subway"] | None = Field(default=None, description="nearby 전용")
    radius_m: int = Field(default=500, ge=1, le=2000)
    size: int = Field(default=5, ge=1, le=15)


def _place(doc: dict) -> dict:
    return {
        "name": doc.get("place_name", ""),
        "category": doc.get("category_group_name", ""),
        "address": doc.get("address_name", ""),
        "road_address": doc.get("road_address_name", ""),
        "lat": float(doc["y"]), "lng": float(doc["x"]),
        "distance_m": int(doc["distance"]) if doc.get("distance") else None,
        "place_url": doc.get("place_url", ""),
    }


@REGISTRY.register(
    name="search_places",
    description=(
        "장소 이름이나 주소를 좌표로 바꾸거나(집·출발지 위치), 공연장 주변 식당·카페·지하철역 같은 보조 정보를 "
        "찾을 때 사용한다. 그 장소에서 어떤 공연을 하는지는 알려주지 않는다."
    ),
    args_model=SearchPlacesArgs,
    source=SOURCE,
)
def search_places(args: SearchPlacesArgs):
    if args.mode == "geocode":
        if not args.query:
            raise ToolError(base.INVALID_INPUT, "geocode에는 장소 이름(query)이 필요해요.")
        params = {"query": args.query, "size": args.size}
    else:
        if args.lat is None or args.lng is None:
            raise ToolError(base.INVALID_INPUT, "nearby에는 기준 좌표(lat, lng)가 필요해요.")
        code, word = CATEGORY[args.category or "restaurant"]
        params = {"query": args.query or word, "x": args.lng, "y": args.lat, "radius": args.radius_m,
                  "category_group_code": code, "sort": "distance", "size": args.size}

    body = base.cached(f"places:{json.dumps(params, sort_keys=True, ensure_ascii=False)}",
                       lambda: _get_json(KEYWORD_URL, params))
    docs = body.get("documents") or []
    if not docs:
        raise ToolError(base.NO_RESULT, "검색 결과가 없어요.")
    if args.mode == "geocode":
        top_sido = {d.get("address_name", "").split(" ")[0] for d in docs[:3]}
        if len(top_sido) > 1 and not any(s and s in args.query for s in top_sido):
            raise ToolError(base.AMBIGUOUS, f"'{args.query}'이(가) 여러 지역에 있어요. 지역을 함께 알려 주세요.")
    return {"items": [_place(d) for d in docs]}


# ── get_transit_time ─────────────────────────────────────────────────────────


class TransitArgs(BaseModel):
    from_lat: float = Field(ge=-90, le=90, description="출발(공연장) 위도")
    from_lng: float = Field(ge=-180, le=180, description="출발(공연장) 경도")
    to_lat: float = Field(ge=-90, le=90, description="도착(집) 위도")
    to_lng: float = Field(ge=-180, le=180, description="도착(집) 경도")


def _walk_estimate(args: TransitArgs) -> tuple[dict, dict]:
    km = distance_km(args.from_lat, args.from_lng, args.to_lat, args.to_lng)
    minutes = max(1, math.ceil(km / WALK_KMH * 60))
    data = {"total_min": minutes, "transfers": 0, "fare": 0, "route_type": "WALK_ESTIMATE",
            "summary": f"도보 약 {minutes}분 (직선거리 {km * 1000:.0f}m 기준 추정)", "map_url": None,
            "note": "대중교통 경로가 없을 만큼 가까워 직선거리 ÷ 시속 4km로 추정", "issues": [base.TOO_CLOSE]}
    return data, {"estimated": True, "notes": ["직선거리 기준 도보 추정치예요."]}


@REGISTRY.register(
    name="get_transit_time",
    description=(
        "공연장에서 집(또는 목적지)까지 대중교통 소요시간을 구해 귀가 시각 조건을 판단할 때 사용한다. 사용자가 "
        "귀가·도착 시각을 말했을 때만 쓴다. 시간대별 배차와 막차는 반영하지 않는다."
    ),
    args_model=TransitArgs,
    source=SOURCE,
)
def get_transit_time(args: TransitArgs):
    params = {"start_x": args.from_lng, "start_y": args.from_lat, "end_x": args.to_lng, "end_y": args.to_lat}
    key = "route:" + ",".join(f"{v:.5f}" for v in params.values())
    body = base.cached(key, lambda: _get_json(TRANSIT_URL, params))
    status = body.get("status")

    if status == "EQUAL_POINTS":
        return _walk_estimate(args)
    if status == "NO_RESULTS":
        if distance_km(args.from_lat, args.from_lng, args.to_lat, args.to_lng) < TOO_CLOSE_KM:
            return _walk_estimate(args)
        raise ToolError(base.NO_RESULT, "대중교통 경로를 찾지 못했어요.")
    if status in ("STARTNODES_NULL", "ENDNODES_NULL"):
        raise ToolError(base.NO_RESULT, "주변에 정류장이 없어 대중교통 경로를 찾지 못했어요.")
    if status == "INVALID_REQUEST":
        raise ToolError(base.INVALID_INPUT, "좌표를 확인해 주세요.")
    routes = body.get("routes") or []
    if status != "OK" or not routes:
        raise ToolError(base.UPSTREAM_ERROR, "대중교통 응답을 해석하지 못했어요.")

    best = min(routes, key=lambda r: r["properties"]["totalTime"])
    props = best["properties"]
    lines = [(s["properties"].get("vehicles") or [{}])[0].get("name")
             for s in best.get("steps", []) if s["properties"].get("type") in ("SUBWAY", "BUS")]
    data = {
        "total_min": math.ceil(props["totalTime"] / 60),  # 초 → 분 올림
        "transfers": props.get("transfers"),
        "fare": (props.get("fare") or {}).get("value"),
        "route_type": props.get("type"),
        "summary": " → ".join(n for n in lines if n),
        "map_url": (body.get("properties") or {}).get("landingURL"),
        "note": "시간대·막차 미반영 소요시간",
        "issues": [],
    }
    return data, {"estimated": True}
