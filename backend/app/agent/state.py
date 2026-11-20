"""Agent State와 LLM 구조화 출력 스키마."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

Intent = Literal["plan_request", "fact_query", "plan_save", "calendar_register", "chitchat"]
CONDITION_FIELDS = ("date", "start_after", "end_by", "home_by", "home_location", "region", "genre",
                    "keyword", "budget_max", "region_strict", "genre_strict")


class AgentState(TypedDict, total=False):
    # 실행마다 새로 채우는 값
    session_id: str
    run_id: str
    message: str
    intent: str | None
    topic: str | None
    intent_reason: str | None
    selection: int | None
    defaults_applied: list[str]
    missing: list[str]
    plan: list[dict]
    tasks: list[dict]  # (F3021) Planner가 만든 작업 목록: tool·args·fixed·repairable·depends_on
    query: dict
    pending_ids: list[str]
    details: dict[str, dict]
    excluded_pre: list[dict]  # 판정 전에 빠진 후보 (대학로 아님, 상세 실패)
    transit: dict[str, dict]  # venue_id → 대중교통 결과
    evaluations: list[dict]
    replan_count: int
    replan_log: list[dict]
    warnings: list[dict]
    facts: dict | None
    route: str | None  # judge가 정한 다음 단계: enrich | replan | respond
    prefetched: bool  # plan 노드가 첫 라운드 후보를 이미 조회했는가
    round_ids: list[str]  # 이번 라운드에 상세를 조회한 후보
    candidate_titles: dict[str, str]
    enriched: dict[str, dict]
    ranked_ids: list[str]
    fatal: dict | None
    response: dict | None
    # 대화가 이어져도 남는 값 (Memory: MemorySaver, thread_id = session_id)
    conditions: dict[str, Any]
    home: dict | None
    last_recommendations: list[dict]
    history: list[dict]


def fresh_run_state(session_id: str, run_id: str, message: str) -> dict:
    """사용자 메시지 1건 = 실행 1건. Memory 필드(conditions 등)는 넣지 않아 이전 값이 유지된다."""
    return {
        "session_id": session_id, "run_id": run_id, "message": message,
        "intent": None, "topic": None, "intent_reason": None, "selection": None,
        "defaults_applied": [], "missing": [], "plan": [], "tasks": [], "query": {}, "pending_ids": [],
        "details": {}, "excluded_pre": [], "transit": {}, "evaluations": [], "replan_count": 0,
        "replan_log": [], "warnings": [], "facts": None, "fatal": None, "response": None,
        "route": None, "prefetched": False, "round_ids": [], "candidate_titles": {}, "enriched": {}, "ranked_ids": [],
    }


# ── LLM 구조화 출력 (analyze) ────────────────────────────────────────────────
# OpenAI strict json_schema 호환을 위해 모든 필드를 '필수 + null 허용'으로 둔다.


class ExtractedConditions(BaseModel):
    date: str | None = Field(description="관람 날짜 YYYY-MM-DD. 이번 메시지에 언급이 없으면 null")
    start_after: str | None = Field(description="이 시각 이후 시작 HH:MM(24시간). 언급 없으면 null")
    end_by: str | None = Field(description="이 시각까지 공연 종료 HH:MM. 언급 없으면 null")
    home_by: str | None = Field(description="이 시각까지 집/목적지 도착 HH:MM. 언급 없으면 null")
    home_location: str | None = Field(description="집/목적지 장소 이름 (예: 망원역). 언급 없으면 null")
    region: str | None = Field(description="공연 지역 (예: 대학로, 강남구). 언급 없으면 null")
    genre: Literal["연극", "뮤지컬", "클래식"] | None = Field(description="장르. 언급 없으면 null")
    keyword: str | None = Field(description="작품명. 언급 없으면 null")
    budget_max: int | None = Field(description="1인 예산 상한(원). 언급 없으면 null")
    region_strict: bool | None = Field(description="'대학로만'처럼 지역을 꼭 지켜야 하면 true, 아니면 null")
    genre_strict: bool | None = Field(description="'꼭 연극'처럼 장르를 꼭 지켜야 하면 true, 아니면 null")


class AnalyzeOutput(BaseModel):
    intent: Intent = Field(description="plan_request 관람 계획 / fact_query 사실 조회 / plan_save '1번 저장' / "
                                       "calendar_register 캘린더 등록 / chitchat 그 밖의 대화")
    topic: Literal["performance", "weather"] | None = Field(
        description="fact_query일 때 묻는 대상. 날씨만 물으면 weather, 그 밖에는 performance")
    reason: str = Field(description="이 의도로 판단한 이유 한 문장")
    reset: bool | None = Field(description="'처음부터 다시'처럼 이전 조건을 버리라고 하면 true")
    selection: int | None = Field(description="plan_save일 때 저장할 추천 번호 (예: '1번' → 1)")
    conditions: ExtractedConditions = Field(description="이번 메시지에서 언급된 조건만. 나머지는 null")


# ── LLM 구조화 출력 (F3021 Worker) ───────────────────────────────────────────


class ArgChange(BaseModel):
    name: str = Field(description="바꿀 인자 이름. repairable 목록에 있는 인자만 바꿀 수 있다")
    value: str = Field(description="새 값")


class WorkerDecision(BaseModel):
    action: Literal["retry", "skip", "request_replan"] = Field(
        description="retry: 인자를 고쳐 다시 호출 / skip: 이 작업을 건너뜀 / request_replan: Planner에게 넘김(사용자에게 되묻기 등)")
    changes: list[ArgChange] = Field(description="retry일 때 바꿀 인자. 그 밖에는 빈 목록")
    reason: str = Field(description="판단 이유 한 문장")
