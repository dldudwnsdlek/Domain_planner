"""기상청 단기예보 Tool: get_weather (보조 정보 — 판정에는 쓰지 않는다).

- 관람일이 예보 범위(발표일 기준 글피까지) 밖이면 API를 부르지 않고 OUT_OF_RANGE.
- 키 오류는 HTTP 403 + OpenAPI_ServiceResponse 구조로 온다(정상 응답과 구조가 다름).
- 한 번 호출하면 그 격자의 며칠 치가 오므로 (격자, 발표 시각) 단위로 캐시한다.
- 실측 totalCount가 1000을 넘을 수 있어(1016) numOfRows를 넉넉히 둔다.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from pydantic import BaseModel, Field

from app import config
from app.tools import base
from app.tools.base import REGISTRY, ToolError
from app.tools.kma_grid import in_forecast_range, latest_base_time, to_grid

SOURCE = "KMA"
URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
NUM_OF_ROWS = 1500
PTY = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
SKY = {"1": "맑음", "3": "구름많음", "4": "흐림"}
UMBRELLA_POP = 60
DEFAULT_HOURS = ["19:00", "21:00", "23:00"]


def _now() -> datetime:
    return datetime.now()


class WeatherArgs(BaseModel):
    lat: float = Field(ge=-90, le=90, description="공연장 위도")
    lng: float = Field(ge=-180, le=180, description="공연장 경도")
    date: str = Field(description="관람 날짜 YYYY-MM-DD")
    hours: list[str] = Field(default_factory=list, description="확인할 시각 HH:MM 목록 (시작·종료·귀가 시각)")


def _fetch(nx: int, ny: int, base_date: str, base_time: str) -> list[dict]:
    key = config.get_str("KMA_SERVICE_KEY")
    if not key:
        raise ToolError(base.MISSING_API_KEY, "기상청 서비스키가 설정되지 않았어요.")
    resp = base.http_get(URL, {"serviceKey": key, "pageNo": 1, "numOfRows": NUM_OF_ROWS, "dataType": "JSON",
                               "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny})
    if "SERVICE_KEY_IS_NOT_REGISTERED" in resp.text or resp.status in (401, 403):
        raise ToolError(base.MISSING_API_KEY, "기상청 서비스키가 올바르지 않아요(Decoding 키인지 확인해 주세요).")
    try:
        body = json.loads(resp.text)["response"]
        code = body["header"]["resultCode"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ToolError(base.UPSTREAM_ERROR, "기상청 응답을 해석하지 못했어요.") from exc
    if code == "03":
        raise ToolError(base.NO_RESULT, "기상청 예보 자료가 아직 없어요.")
    if code != "00":
        raise ToolError(base.UPSTREAM_ERROR, "기상청이 오류를 돌려줬어요.")
    return body["body"]["items"]["item"]


def _minutes(text: str) -> int:
    """'21:00' 또는 기상청 '2100' → 분."""
    digits = text.replace(":", "")
    return int(digits[:-2]) * 60 + int(digits[-2:])


def _normalize_hhmm(text: str) -> str:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text.strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(text)
    return f"{int(m.group(1)):02d}:{m.group(2)}"


@REGISTRY.register(
    name="get_weather",
    description=(
        "관람 날짜·시간대에 공연장 주변의 비 예보와 기온을 알려줄 때 사용한다. 추천 결과에 덧붙이는 보조 정보이며, "
        "공연을 고르는 판단에는 쓰지 않는다. 발표일 기준 글피까지만 예보가 있다."
    ),
    args_model=WeatherArgs,
    source=SOURCE,
)
def get_weather(args: WeatherArgs):
    try:
        target = date.fromisoformat(args.date).isoformat()
        wanted = [_normalize_hhmm(h) for h in (args.hours or DEFAULT_HOURS)]
    except ValueError as exc:
        raise ToolError(base.INVALID_INPUT, "날짜는 YYYY-MM-DD, 시각은 HH:MM 형식이어야 해요.") from exc

    base_date, base_time = latest_base_time(_now())
    if not in_forecast_range(base_date, target):
        raise ToolError(base.OUT_OF_RANGE, "관람일이 단기예보 범위(발표일 기준 글피까지) 밖이라 날씨를 확인할 수 없어요.")

    nx, ny = to_grid(args.lat, args.lng)
    items = base.cached(f"kma:{nx},{ny}:{base_date}{base_time}", lambda: _fetch(nx, ny, base_date, base_time))

    by_time: dict[str, dict[str, str]] = {}
    for it in items:
        if it.get("fcstDate") == target.replace("-", ""):
            by_time.setdefault(it["fcstTime"], {})[it["category"]] = it["fcstValue"]
    if not by_time:
        raise ToolError(base.NO_RESULT, "그날의 예보 자료가 없어요.")

    hours = []
    for hhmm in wanted:
        nearest = min(by_time, key=lambda t: abs(_minutes(t) - _minutes(hhmm)))
        v = by_time[nearest]
        hours.append({
            "time": hhmm,
            "forecast_time": f"{nearest[:2]}:{nearest[2:]}",
            "pop": int(v["POP"]) if "POP" in v else None,
            "pty": PTY.get(v.get("PTY", ""), None),
            "sky": SKY.get(v.get("SKY", ""), None),
            "tmp": int(float(v["TMP"])) if "TMP" in v else None,
        })

    worst = max(hours, key=lambda h: h["pop"] or 0)
    summary = f"{worst['time'][:2]}시 강수확률 {worst['pop']}% · 기온 {worst['tmp']}℃"
    if (worst["pop"] or 0) >= UMBRELLA_POP or any(h["pty"] not in (None, "없음") for h in hours):
        summary += " — 우산을 챙기세요"
    data = {"grid": {"nx": nx, "ny": ny},
            "base": f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:]} {base_time[:2]}:{base_time[2:]} 발표",
            "hours": hours, "summary": summary}
    return data, {"notes": ["출처: 기상청 단기예보 (공공누리 제1유형)"]}
