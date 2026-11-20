"""오프라인 실행 도구: 저장된 실제 API 샘플로 HTTP를 대신하고, LLM 자리에 고정 응답을 넣는다.

용도
  - LLM(GMS)을 쓸 수 없을 때 그래프 전체(execute·judge·replan·enrich·respond)를 실제 데이터로 검증
  - 예시 화면 데이터 생성 (scripts/make_demo_data.py)
  - 그래프 테스트 (backend/tests/test_graph.py)
외부 호출 0회. 서비스 코드 경로에서는 쓰지 않는다.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path

from app.agent.deps import Deps
from app.agent.service import AgentService
from app.agent.state import AnalyzeOutput, ExtractedConditions
from app.db.database import Database
from app.db.logs_repo import LogsRepo
from app.db.plans_repo import PlansRepo
from app.events.bus import EventBus
from app.logging_agent.subscriber import LoggingAgent
from app.tools import REGISTRY, base, kma, kopis

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
EMPTY_KOPIS = "<dbs></dbs>"


def sample_http(url: str, params: dict, headers: dict | None = None) -> base.HttpResponse:
    """URL을 저장된 샘플 파일로 바꿔 돌려준다. 샘플이 없으면 '결과 없음' 응답."""
    def read(rel: str) -> str | None:
        path = SAMPLES / rel
        return path.read_text(encoding="utf-8") if path.exists() else None

    if "kopis.or.kr" in url:
        tail = url.rsplit("/restful/", 1)[1]
        if tail == "pblprfr":
            genre = params.get("shcate")
            page = int(params.get("cpage", 1))
            rel = ("kopis/list_20261121_seoul_musical.xml" if genre == "GGGA"
                   else "kopis/list_20261121_seoul-jongno_theater.xml")
            text = read(rel) if page == 1 else None
            return base.HttpResponse(200, text or EMPTY_KOPIS)
        kind, _, ident = tail.partition("/")
        rel = f"kopis/detail_{ident}.xml" if kind == "pblprfr" else f"kopis/venue_{ident}.xml"
        return base.HttpResponse(200, read(rel) or EMPTY_KOPIS)
    if "local/search/keyword" in url:
        query = str(params.get("query", ""))
        if any(word in query for word in ("근처", "사이", "우리 아파트", "우리집")):  # 실측: 카카오 NO_RESULT
            return base.HttpResponse(200, json.dumps({"documents": [], "meta": {"total_count": 0}}))
        near_hyehwa = params.get("x") or "대학로" in query or "종로" in query  # 혜화 일대(종로구) 샘플
        rel = "kakao/keyword_daehakro-nearby-restaurant.json" if near_hyehwa else "kakao/keyword_mangwon-station.json"
        return base.HttpResponse(200, read(rel))
    if "routing/publictraffic" in url:
        return base.HttpResponse(200, read("kakao/transit_hyehwa_to_mangwon.json"))
    if "VilageFcstInfoService" in url:
        rel = next((SAMPLES / "kma").glob("vilage_*.json"))
        return base.HttpResponse(200, rel.read_text(encoding="utf-8"))
    raise AssertionError(f"샘플이 없는 URL: {url}")


@contextlib.contextmanager
def offline_apis(now: datetime):
    """base.http_get과 기상청 현재 시각을 샘플 기준으로 바꾼다(끝나면 원래대로)."""
    original_http, original_now, original_throttle = base.http_get, kma._now, kopis.THROTTLE
    base.http_get, kma._now = sample_http, (lambda: now)
    kopis.THROTTLE = kopis.Throttle(max_concurrent=5, min_interval=0)  # 샘플이라 KOPIS 요청 조절 불필요
    base.clear_cache()
    try:
        yield
    finally:
        base.http_get, kma._now, kopis.THROTTLE = original_http, original_now, original_throttle
        base.clear_cache()


class FixedAnalyzer:
    """메시지 → 미리 정한 분석 결과. LLM 자리에 끼운다."""

    def __init__(self, table: dict[str, AnalyzeOutput]) -> None:
        self.table = table

    def __call__(self, message: str, **_kwargs) -> AnalyzeOutput:
        return self.table[message]


def analysis(intent: str, reason: str, *, topic=None, selection=None, reset=None, **conditions) -> AnalyzeOutput:
    fields = {k: None for k in ExtractedConditions.model_fields}
    return AnalyzeOutput(intent=intent, topic=topic, reason=reason, reset=reset, selection=selection,
                         conditions=ExtractedConditions(**(fields | conditions)))


S1_MESSAGE = "11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로."
S1 = analysis("plan_request", "날짜·지역·장르와 시간·귀가·예산 제약이 있는 추천 요청", date="2026-11-21",
              start_after="18:00", region="대학로", genre="연극", home_by="23:30", home_location="망원역",
              budget_max=50000)
SAVE_1 = analysis("plan_save", "직전 추천 1번을 저장하라는 요청", selection=1)


def build_offline(now: datetime, analyzer, db: Database | None = None, *, mode: str = "A",
                  worker=None) -> tuple[AgentService, PlansRepo, LogsRepo]:
    db = db or Database(":memory:")
    bus = EventBus()
    logs, plans = LogsRepo(db), PlansRepo(db)
    LoggingAgent(logs).attach(bus)
    deps = Deps(registry=REGISTRY, bus=bus, analyzer=analyzer, planner=None, summarizer=None,
                plans_repo=plans, now=lambda: now, mode=mode, worker=worker)
    return AgentService(deps), plans, logs


def run_offline_s1(now: datetime) -> tuple[dict, list[dict], dict]:
    """S1 → '1번 저장' 순서로 실행해 화면 예시용 (대화 응답, 계획 목록, 로그)를 만든다."""
    analyzer = FixedAnalyzer({S1_MESSAGE: S1, "1번 저장해줘": SAVE_1})
    with offline_apis(now):
        service, plans, logs = build_offline(now, analyzer)
        chat = service.chat("s-demo", S1_MESSAGE)
        service.chat("s-demo", "1번 저장해줘")
    # 같은 날 겹치는 계획 하나를 수동으로 추가해 '겹침' 표시를 보여 준다
    first = plans.list()[0]
    plans.create({"performance_id": "MANUAL", "title": "저녁 식사 (직접 입력)", "venue_name": "혜화역 근처",
                  "date": first["date"], "start_time": "17:00", "end_time": first["start_time"][:2] + ":30",
                  "memo": "공연 전 식사"})
    chat = json.loads(json.dumps(chat, ensure_ascii=False))
    chat["request"] = S1_MESSAGE
    log_view = {"sessions": logs.list_sessions(), "events": logs.events("s-demo")}
    return chat, plans.list(), log_view
