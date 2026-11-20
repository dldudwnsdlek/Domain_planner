"""API 요청·응답 Pydantic 모델 (F3017)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DATE = r"^\d{4}-\d{2}-\d{2}$"
TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


# ── 대화 ────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64, description="없으면 서버가 발급")
    message: str = Field(min_length=1, max_length=500)


class Showtime(BaseModel):
    start: str
    end: str | None
    home_arrival: str | None
    verdict: str


class Venue(BaseModel):
    name: str | None
    address: str | None = None
    map_url: str | None = None


class Transit(BaseModel):
    total_min: int
    summary: str | None
    map_url: str | None


class Weather(BaseModel):
    status: Literal["ok", "out_of_range", "unavailable"]
    summary: str | None
    hours: list[dict] | None = None


class Recommendation(BaseModel):
    performance_id: str
    title: str
    genre: str | None = None
    poster_url: str | None = None
    venue: Venue
    date: str
    showtimes: list[Showtime]
    min_price: int | None
    price_raw: str | None = None
    age_rating: str | None = None
    ticket_links: list[dict] = []
    transit: Transit | None = None
    weather: Weather
    evidence: list[str] = []


class Excluded(BaseModel):
    performance_id: str
    title: str
    reason_code: str | None
    reason: str


class Suggestion(BaseModel):
    field: str
    value: int | str
    count: int
    text: str


class TraceStep(BaseModel):
    seq: int
    label: str
    elapsed_ms: int | None
    is_replan: bool
    ok: bool


class WarningItem(BaseModel):
    code: str
    service: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    run_id: str
    status: Literal["ok", "clarify", "limit_reached", "error"]
    reply: str
    understood: dict[str, Any] = {}
    defaults_applied: list[str] = []
    recommendations: list[Recommendation] = []
    excluded: list[Excluded] = []
    suggestions: list[Suggestion] = []
    facts: dict[str, Any] | None = None
    assumptions: list[str] = []
    sources: list[str] = []
    trace: list[TraceStep] = []
    replan_count: int = 0
    warnings: list[WarningItem] = []
    saved_plan: dict[str, Any] | None = None
    overlaps: list[dict[str, Any]] = []
    elapsed_ms: int | None = Field(default=None, description="요청 1건 전체 처리 시간")


# ── 계획 ────────────────────────────────────────────────────────────────────


class PlanCreate(BaseModel):
    performance_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    venue_name: str | None = None
    venue_address: str | None = None
    date: str = Field(pattern=DATE)
    start_time: str = Field(pattern=TIME)
    end_time: str | None = Field(default=None, pattern=TIME)
    price: int | None = Field(default=None, ge=0)
    ticket_url: str | None = None
    memo: str | None = Field(default=None, max_length=200)
    session_id: str | None = None


class PlanUpdate(BaseModel):
    date: str | None = Field(default=None, pattern=DATE)
    start_time: str | None = Field(default=None, pattern=TIME)
    end_time: str | None = Field(default=None, pattern=TIME)
    memo: str | None = Field(default=None, max_length=200)


class Plan(BaseModel):
    id: int
    performance_id: str
    title: str
    venue_name: str | None
    venue_address: str | None
    date: str
    start_time: str
    end_time: str | None
    price: int | None
    ticket_url: str | None
    memo: str | None
    session_id: str | None
    created_at: str
    updated_at: str
    overlaps: list[int] = []


class PlanResult(BaseModel):
    plan: Plan
    overlaps: list[Plan]


class PlanList(BaseModel):
    plans: list[Plan]


class Deleted(BaseModel):
    deleted: bool | int


# ── 로그 · 상태 ──────────────────────────────────────────────────────────────


class SessionSummary(BaseModel):
    session_id: str
    runs: int
    events: int
    first_ts: str
    last_ts: str


class SessionList(BaseModel):
    sessions: list[SessionSummary]


class LogEvent(BaseModel):
    event_id: str
    session_id: str
    run_id: str
    seq: int
    ts: str
    type: str
    node: str | None
    payload: dict[str, Any]


class EventList(BaseModel):
    events: list[LogEvent]


class Health(BaseModel):
    status: str
    services: dict[str, bool]
