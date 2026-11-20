"""FastAPI 앱: 라우터, 전역 예외 처리, 이벤트 구독 등록, 프론트엔드 정적 파일.

실행: .venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000  → http://127.0.0.1:8000
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.agent.deps import Deps
from app.agent.llm_steps import LLMAnalyzer, LLMPlanner, LLMSummarizer, LLMWorker
from app.agent.service import AgentService
from app.api import chat, health, logs, plans
from app.db.database import Database
from app.db.logs_repo import LogsRepo
from app.db.plans_repo import PlansRepo
from app.events.bus import EventBus
from app.logging_agent.subscriber import LoggingAgent
from app.tools import REGISTRY

logger = logging.getLogger(__name__)
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@dataclass
class Container:
    service: AgentService
    plans: PlansRepo
    logs: LogsRepo
    bus: EventBus


def build_container(db: Database | None = None, deps_overrides: dict | None = None) -> Container:
    db = db or Database(config.db_path())
    bus = EventBus()
    plans_repo, logs_repo = PlansRepo(db), LogsRepo(db)
    LoggingAgent(logs_repo).attach(bus)  # 발행자(Agent)는 이 구독을 모른다
    mode = config.agent_mode()
    deps = Deps(registry=REGISTRY, bus=bus, analyzer=LLMAnalyzer(), planner=LLMPlanner(),
                summarizer=LLMSummarizer(), worker=LLMWorker() if mode == "C" else None, mode=mode,
                plans_repo=plans_repo, max_replan=config.max_replan(),
                detail_limit=config.detail_fetch_limit(), exit_buffer=config.exit_buffer_min())
    for key, value in (deps_overrides or {}).items():
        setattr(deps, key, value)
    return Container(AgentService(deps), plans_repo, logs_repo, bus)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="커튼콜 플래너 API", version="0.1.0",
                  description="시간·예산·귀가 조건에 맞는 공연과 회차를 찾아 주는 Agent. "
                              "출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr) · 카카오맵 · 기상청")
    app.state.container = container or build_container()
    for router in (chat.router, plans.router, logs.router, health.router):
        app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors()})
        return _error(422, "INVALID_INPUT", f"입력값을 확인해 주세요: {', '.join(fields)}")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            return _error(exc.status_code, exc.detail.get("code", "ERROR"), exc.detail.get("message", ""))
        return _error(exc.status_code, f"HTTP_{exc.status_code}", "요청을 처리하지 못했어요.")

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _exc: Exception):
        logger.exception("unhandled error")  # 상세는 서버 로그에만, 응답에는 사용자용 문장만 (NF3002)
        return _error(500, "INTERNAL_ERROR", "서버에서 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")

    if FRONTEND.exists():
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


app = create_app()
