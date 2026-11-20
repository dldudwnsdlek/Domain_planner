"""execute(코드: 인자 채우기·반복 호출·2단계 판정의 1차) · judge(순수 함수) · enrich(날씨·지도) 노드."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import quote

from app.agent.constraints import FAIL, PASS, UNKNOWN, count_fail_reasons, evaluate_performance, rank_passed
from app.agent.deps import Deps
from app.agent.nodes.common import eval_from_dict, eval_to_dict, to_conditions
from app.agent.nodes.common import DETAIL, PLACES, SEARCH, TRANSIT, WEATHER
from app.agent.relax import next_relaxation
from app.agent.worker import with_task_args, worker_call
from app.events.types import CONSTRAINT_EVALUATED, REPLAN_STOPPED
from app.tools.base import ToolError
from app.tools.region_alias import SIDO, resolve_region

PARALLEL = 5
SEARCH_SIZE = 20
FATAL_CODES = {"MISSING_API_KEY", "RATE_LIMITED"}  # 다시 해도 결과가 같은 실패 → 재계획하지 않음
SIDO_BY_CODE = {code: name for name, code in SIDO.items()}
SERVICE = {SEARCH: "KOPIS", DETAIL: "KOPIS", PLACES: "카카오", TRANSIT: "카카오", WEATHER: "기상청"}


def _planned(state: dict) -> set[str]:
    return {p["tool"] for p in state.get("plan", [])}


def _warn(state: dict, tool: str, result: dict) -> dict:
    return {"code": result["error"]["code"], "service": SERVICE.get(tool, tool), "message": result["error"]["message"]}


def _venue_map_url(venue: dict) -> str | None:
    if venue.get("lat") is None:
        return None
    return f"https://map.kakao.com/link/map/{quote(venue.get('name') or '공연장')},{venue['lat']},{venue['lng']}"


# ── execute ─────────────────────────────────────────────────────────────────


def execute(state: dict, deps: Deps) -> dict:
    if state["intent"] == "fact_query":
        return _execute_weather(state, deps) if state.get("topic") == "weather" else _execute_fact(state, deps)
    return _execute_plan(state, deps)


def _execute_fact(state: dict, deps: Deps) -> dict:
    cond = state["conditions"]
    start = date.fromisoformat(cond["date"]) if cond.get("date") else deps.now().date()
    args = {"keyword": cond["keyword"], "date_from": start.isoformat(),
            "date_to": (start + timedelta(days=30)).isoformat(), "size": 5}
    if cond.get("region"):
        args["region"] = cond["region"]
    found, info = worker_call(state, deps, "execute", "t1", SEARCH, args)
    if not found["ok"]:
        code = found["error"]["code"]
        if code in FATAL_CODES:
            return {"fatal": {"code": code, "message": found["error"]["message"]}, "warnings": [_warn(state, SEARCH, found)]}
        return {"facts": {"found": False, "message": f"‘{cond['keyword']}’ 공연을 찾지 못했어요."}, "_summary": code}
    repaired = _repair_note(state, info, "t1", "keyword", "작품명")
    item = found["data"]["items"][0]
    detail = deps.call_tool(state, "execute", DETAIL, {"performance_id": item["performance_id"], "include_venue": False})
    if not detail["ok"]:
        return {"facts": {"found": False, "message": "공연 상세 정보를 가져오지 못했어요."}, "_summary": "상세 실패"}
    d = detail["data"]
    facts = {"found": True, "performance_id": d["performance_id"], "title": d["title"], "runtime_min": d["runtime_min"],
             "runtime_raw": d["runtime_raw"], "age_rating": d["age_rating"], "venue_name": d["venue"]["name"],
             "period": f"{d['period_from']} ~ {d['period_to']}", "schedule_raw": d["schedule_raw"],
             "price_raw": d["price_raw"], "issues": d["issues"]}
    return {"facts": facts, "_summary": d["title"], **repaired}


def _repair_note(state: dict, info: dict, task_id: str, arg: str, what: str) -> dict:
    """(F3021) Worker가 고친 인자로 성공했으면 사용자에게 알리고 작업 목록에도 반영한다(숨기지 않음)."""
    if info.get("action") != "retry_ok":
        return {}
    before, after = info["repaired_from"].get(arg), info["args"].get(arg)
    note = f"{what} ‘{before}’을(를) 찾지 못해 ‘{after}’(으)로 고쳐 찾았어요."
    return {"defaults_applied": (state.get("defaults_applied") or []) + [note],
            "tasks": with_task_args(state.get("tasks") or [], task_id, {arg: after})}


def weather_place_query(cond: dict) -> tuple[str, str | None]:
    """날씨 위치 검색어와, 결과 주소가 시작해야 할 지역 접두사(예: '서울 종로구').

    실측(2026-11-20): 카카오에 '대학로'만 검색하면 경북 구미의 '대학로'가, '서울 대학로'로 검색하면
    경기 시흥의 '서울대학로'(도로명)가 1위로 나왔다. → 지역 별칭으로 구까지 알아내
    '서울 종로구 대학로'처럼 검색하고, 결과도 그 구 안에서 고른다.
    """
    region = cond.get("region")
    if not region:
        return cond.get("home_location") or "서울시청", None
    try:
        resolved = resolve_region(region)
    except ToolError:
        return region, None
    sido = SIDO_BY_CODE.get(resolved.sido_code)
    prefix = resolved.label if resolved.gugun_code else sido  # 구 단위면 '서울 종로구', 아니면 '서울'
    if not prefix:
        return region, None
    query = region if region.startswith(prefix) else f"{prefix} {region}"
    if resolved.gugun_code and resolved.label.split(" ", 1)[1] in region:  # '강남구'처럼 구 이름 자체면 중복 제거
        query = resolved.label
    return query, prefix


def pick_in_city(items: list[dict], prefix: str | None) -> dict | None:
    """검색 결과 중 주소가 그 지역 접두사로 시작하는 첫 장소. 접두사를 모르면 1위."""
    if not prefix:
        return items[0] if items else None
    return next((it for it in items if (it.get("address") or "").startswith(prefix)), None)


def _execute_weather(state: dict, deps: Deps) -> dict:
    cond = state["conditions"]
    place, sido = weather_place_query(cond)
    geo, info = worker_call(state, deps, "execute", "t1", PLACES, {"mode": "geocode", "query": place})
    top = pick_in_city(geo["data"]["items"], sido) if geo["ok"] else None
    repaired = _repair_note(state, info, "t1", "query", "날씨 위치")
    if top is None:
        warnings = [_warn(state, PLACES, geo)] if not geo["ok"] else []
        where = f"{sido}에서 " if sido else ""
        return {"facts": {"found": False, "message": f"‘{place}’ 위치를 {where}찾지 못해 날씨를 확인할 수 없어요."},
                "warnings": warnings, "_summary": "위치 찾기 실패"}
    # 시각을 말하지 않은 날씨 질문("토요일 밤 비 와?")은 관람·귀가 시간대인 저녁·밤(get_weather 기본 19·21·23시)으로 본다
    hours = [cond["start_after"]] if cond.get("start_after") else []
    w = deps.call_tool(state, "execute", WEATHER, {"lat": top["lat"], "lng": top["lng"], "date": cond["date"], "hours": hours})
    if w["ok"]:
        facts = {"found": True, "kind": "weather", "place": cond.get("region") or top["name"],
                 "address": top.get("address"), "date": cond["date"], **w["data"]}
    else:
        status = "out_of_range" if w["error"]["code"] == "OUT_OF_RANGE" else "unavailable"
        facts = {"found": False, "kind": "weather", "status": status, "message": w["error"]["message"]}
    return {"facts": facts, "_summary": "날씨만 조회", **repaired}


def fetch_round(state: dict, deps: Deps, query: dict, node: str) -> dict:
    """후보 한 라운드: (필요하면) 공연 목록 → 상세(좌표 없이) 최대 DETAIL_FETCH_LIMIT건.

    execute가 쓰고, 첫 라운드에는 plan 노드가 LLM 계획을 기다리는 동안 미리 부른다(선반입).
    반환값은 State 업데이트 (치명적 실패면 fatal 포함).
    """
    cond, query = state["conditions"], dict(query)
    details = dict(state.get("details") or {})
    titles = dict(state.get("candidate_titles") or {})
    pending = list(state.get("pending_ids") or [])
    warnings = list(state.get("warnings") or [])
    excluded_pre = list(state.get("excluded_pre") or [])
    seen = set(details) | {x["performance_id"] for x in excluded_pre}

    if not pending:  # 새 조건(또는 다음 페이지)으로 후보 목록 조회
        args = {"date_from": cond["date"], "page": query["page"], "size": SEARCH_SIZE}
        if query.get("region"):
            args["region"] = query["region"]
        if query.get("genre"):
            args["genre"] = query["genre"]
        found, _info = worker_call(state, deps, node, "t1", SEARCH, args)
        if found["ok"]:
            data = found["data"]
            query["has_more"] = data["has_more"]
            query["daehakro_only"] = data["query_used"]["daehakro_only"]
            for it in data["items"]:
                titles[it["performance_id"]] = it["title"]
            pending = [it["performance_id"] for it in data["items"] if it["performance_id"] not in seen]
        else:
            code = found["error"]["code"]
            query["has_more"] = False
            if code in FATAL_CODES:
                return {"fatal": {"code": code, "message": found["error"]["message"]},
                        "warnings": warnings + [_warn(state, SEARCH, found)], "query": query}
            if code != "NO_RESULT":
                warnings.append(_warn(state, SEARCH, found))

    batch, pending = pending[: deps.detail_limit], pending[deps.detail_limit:]
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        # 좌표 없이 상세만 조회한다 — 좌표는 이동시간·날씨가 필요한 공연에만 나중에 조회 (KOPIS 호출 절감)
        results = list(pool.map(lambda pid: deps.call_tool(
            state, node, DETAIL, {"performance_id": pid, "include_venue": False}), batch))

    round_ids = []
    for pid, res in zip(batch, results):
        title = titles.get(pid, pid)
        if not res["ok"]:
            if res["error"]["code"] in FATAL_CODES:
                return {"fatal": {"code": res["error"]["code"], "message": res["error"]["message"]},
                        "warnings": warnings + [_warn(state, DETAIL, res)]}
            excluded_pre.append({"performance_id": pid, "title": title, "reason_code": "DETAIL_FAILED",
                                 "reason": "상세 정보를 가져오지 못했어요"})
            continue
        if query.get("daehakro_only") and not res["data"]["daehakro"]:
            excluded_pre.append({"performance_id": pid, "title": res["data"]["title"], "reason_code": "NOT_DAEHAKRO",
                                 "reason": "대학로 공연이 아니에요"})
            continue
        details[pid] = res["data"]
        round_ids.append(pid)

    return {"query": query, "pending_ids": pending, "details": details, "candidate_titles": titles,
            "excluded_pre": excluded_pre, "round_ids": round_ids, "warnings": warnings}


def _execute_plan(state: dict, deps: Deps) -> dict:
    if state.get("fatal"):  # 선반입 중 치명적 실패(키 없음 등)
        return {"_summary": "치명적 실패"}
    prefetched = bool(state.get("prefetched"))
    if prefetched:
        update: dict = {"prefetched": False}
        current = state
    else:
        update = fetch_round(state, deps, state["query"], "execute")
        if update.get("fatal"):
            return update
        current = {**state, **update}

    cond = current["conditions"]
    # 2단계 판정: 시간·예산(C1~C5, C7) 1차 통과 후보만 좌표·대중교통을 조회한다 (KOPIS·카카오 호출 절약)
    if cond.get("home_by") and TRANSIT in _planned(current):
        update.update(_transit_for_passers(current, deps, cond, dict(current["details"]), current["round_ids"],
                                           list(current.get("warnings") or [])))
    update["_summary"] = f"상세 {len(current['round_ids'])}건" + (" (계획 중 선반입)" if prefetched else "")
    return update


def ensure_venues(state: dict, deps: Deps, details: dict, pids: list[str], node: str) -> None:
    """공연장 좌표가 아직 없는 공연만 상세(+좌표)를 다시 조회한다. 상세는 캐시라 KOPIS는 시설 조회만 나간다."""
    todo = [pid for pid in pids if not details[pid].get("venue_checked") and details[pid]["venue"].get("lat") is None]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        results = list(pool.map(lambda pid: deps.call_tool(
            state, node, DETAIL, {"performance_id": pid, "include_venue": True}), todo))
    for pid, res in zip(todo, results):
        details[pid] = res["data"] if res["ok"] else {**details[pid], "venue_checked": True}


def _transit_for_passers(state, deps, cond, details, round_ids, warnings) -> dict:
    conditions = to_conditions(cond)
    passers = [pid for pid in round_ids
               if evaluate_performance(details[pid], conditions, skip_home=True,
                                       exit_buffer=deps.exit_buffer).verdict in (PASS, UNKNOWN)]
    ensure_venues(state, deps, details, passers, "execute")  # 1차 통과 후보만 좌표 조회
    home = state.get("home")
    repaired: dict = {}
    if passers and (not home or home.get("query") != cond["home_location"]):
        geo, info = worker_call(state, deps, "execute", "t3", PLACES,
                                {"mode": "geocode", "query": cond["home_location"]})
        if geo["ok"]:
            top = geo["data"]["items"][0]
            home = {"query": cond["home_location"], "name": top["name"], "lat": top["lat"], "lng": top["lng"]}
            repaired = _repair_note(state, info, "t3", "query", "집 위치")
        elif geo["error"]["code"] == "AMBIGUOUS":
            return {"missing": ["home_ambiguous"]}
        elif deps.mode != "A" and info.get("action") == "request_replan":
            # (F3021) Worker가 풀지 못한 실패 → Planner가 받아 사용자에게 되묻는다(헛된 재계획 대신)
            return {"missing": ["home_unresolved"]}
        else:
            warnings.append(_warn(state, PLACES, geo))
            home = None
    transit = dict(state.get("transit") or {})
    if home:
        venues: dict[str, dict] = {}  # 공연장 단위로 한 번만 (여러 공연이 같은 공연장을 쓴다)
        for pid in passers:
            venue = details[pid]["venue"]
            if venue.get("lat") is not None and venue.get("venue_id") not in transit:
                venues.setdefault(venue.get("venue_id"), venue)

        def route(venue: dict) -> dict:
            return deps.call_tool(state, "execute", TRANSIT, {"from_lat": venue["lat"], "from_lng": venue["lng"],
                                                              "to_lat": home["lat"], "to_lng": home["lng"]})

        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            results = list(pool.map(route, venues.values()))
        for vid, res in zip(venues, results):
            if res["ok"]:
                transit[vid] = res["data"]
        blocked = next((r for r in results if not r["ok"] and r["error"]["code"] in FATAL_CODES), None)
        if blocked:
            warnings.append(_warn(state, TRANSIT, blocked))
    return {"home": home, "transit": transit, "warnings": warnings, "details": details, **repaired}


def route_after_execute(state: dict) -> str:
    if state.get("missing"):
        return "clarify"
    if state.get("fatal") or state["intent"] == "fact_query":
        return "respond"
    return "judge"


# ── judge ───────────────────────────────────────────────────────────────────


def judge(state: dict, deps: Deps) -> dict:
    cond = state["conditions"]
    conditions = to_conditions(cond)
    evaluations = list(state.get("evaluations") or [])
    for pid in state.get("round_ids") or []:
        detail = state["details"][pid]
        transit = (state.get("transit") or {}).get(detail["venue"].get("venue_id"))
        ev = evaluate_performance(detail, conditions, transit["total_min"] if transit else None,
                                  exit_buffer=deps.exit_buffer)
        evaluations.append(eval_to_dict(ev))

    evs = [eval_from_dict(e) for e in evaluations]
    counts = {v: sum(1 for e in evs if e.verdict == v) for v in (PASS, FAIL, UNKNOWN)}
    deps.emit(state, CONSTRAINT_EVALUATED, "judge", **{k.lower(): n for k, n in counts.items()},
              top_reasons=count_fail_reasons(evs))
    summary = f"통과 {counts[PASS]} / 탈락 {counts[FAIL]} / 불가 {counts[UNKNOWN]}"

    if counts[PASS] > 0:
        return {"evaluations": evaluations, "route": "enrich", "_summary": summary}
    step = next_relaxation(state["query"], cond, len(state.get("pending_ids") or []))
    if step and state.get("replan_count", 0) < deps.max_replan:
        return {"evaluations": evaluations, "route": "replan", "_summary": summary}
    reason = "limit" if step else "exhausted"
    deps.emit(state, REPLAN_STOPPED, "judge", reason=reason, count=state.get("replan_count", 0))
    return {"evaluations": evaluations, "route": "respond", "_summary": f"{summary} · 재계획 중단({reason})"}


# ── enrich ──────────────────────────────────────────────────────────────────


def enrich(state: dict, deps: Deps) -> dict:
    """최종 추천 상위 5개에만 날씨·지도 링크를 붙인다. 실패해도 추천은 그대로 둔다(날씨는 판정에 안 씀)."""
    cond = state["conditions"]
    ranked = rank_passed([eval_from_dict(e) for e in state["evaluations"]], start_after=cond.get("start_after"))
    warnings = list(state.get("warnings") or [])
    details = dict(state["details"])
    ensure_venues(state, deps, details, [e.performance_id for e in ranked], "enrich")  # 최종 추천에만 좌표
    enriched: dict[str, dict] = {}
    weather_cache: dict[str, dict] = {}
    weather_off = None
    for ev in ranked:
        venue = details[ev.performance_id]["venue"]
        show = next(s for s in ev.showtimes if s.verdict == PASS)
        info = {"map_url": _venue_map_url(venue), "weather": {"status": "unavailable", "summary": None}}
        if WEATHER not in _planned(state):
            info["weather"]["summary"] = "계획에서 제외"
        elif weather_off:
            info["weather"] = weather_off
        elif venue.get("lat") is not None:
            key = f"{venue.get('venue_id')}:{show.start}"
            if key not in weather_cache:
                hours = [h for h in (show.start, show.end, show.home_arrival) if h]
                res = deps.call_tool(state, "enrich", WEATHER, {"lat": venue["lat"], "lng": venue["lng"],
                                                               "date": cond["date"], "hours": hours})
                if res["ok"]:
                    weather_cache[key] = {"status": "ok", "summary": res["data"]["summary"], "hours": res["data"]["hours"]}
                elif res["error"]["code"] == "OUT_OF_RANGE":
                    weather_off = weather_cache[key] = {"status": "out_of_range", "summary": None}
                else:
                    weather_off = weather_cache[key] = {"status": "unavailable", "summary": None}
                    warnings.append(_warn(state, WEATHER, res))
            info["weather"] = weather_cache[key]
        enriched[ev.performance_id] = info
    return {"ranked_ids": [e.performance_id for e in ranked], "enriched": enriched, "warnings": warnings,
            "details": details,
            "_summary": f"상위 {len(ranked)}편"}
