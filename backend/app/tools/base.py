"""Tool 공통: 응답 형식, 실패 코드, 레지스트리, HTTP 호출, 캐시.

규칙
  - Tool은 예외를 밖으로 던지지 않는다. Registry.run이 모든 예외를 ok=false로 바꾼다.
    성공: {"ok": true,  "data": ..., "meta": {...}}
    실패: {"ok": false, "error": {"code", "message"}, "meta": {...}}
  - 필드 하나만 빈 경우(러닝타임 없음 등)는 실패가 아니라 ok=true + data.issues로 표시한다.
  - Agent(LLM)에는 이름·설명·입력 스키마(openai_specs)만 전달한다. 함수 자체는 코드가 실행한다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# ── 실패 코드 ─────────────────────────────────────────────────────────────────
MISSING_API_KEY = "MISSING_API_KEY"  # 재시도·재계획 없이 설정 안내
TIMEOUT = "TIMEOUT"  # Tool 안에서 1회 재시도 후
UPSTREAM_ERROR = "UPSTREAM_ERROR"  # Tool 안에서 1회 재시도 후
RATE_LIMITED = "RATE_LIMITED"
INVALID_INPUT = "INVALID_INPUT"
NOT_FOUND = "NOT_FOUND"
NO_RESULT = "NO_RESULT"  # 재계획 대상
AMBIGUOUS = "AMBIGUOUS"  # 사용자에게 되묻기
OUT_OF_RANGE = "OUT_OF_RANGE"  # 날씨 예보 범위 밖 (API 미호출)
# 필드 단위 누락 (data.issues)
NO_RUNTIME = "NO_RUNTIME"
SCHEDULE_UNPARSED = "SCHEDULE_UNPARSED"
PRICE_UNPARSED = "PRICE_UNPARSED"
TOO_CLOSE = "TOO_CLOSE"  # 대중교통 경로 없음 → 도보 추정치 (meta.estimated=true)

USER_AGENT = "CurtainCallPlanner/0.1"  # KOPIS 방화벽이 requests 기본 UA를 막는다(실측)
HTTP_TIMEOUT_SEC = 8
RETRY_DELAY_SEC = 0.3
CACHE_TTL_SEC = 24 * 60 * 60


class ToolError(Exception):
    """Tool 내부에서 실패를 알릴 때 쓴다. message는 사용자에게 보여도 되는 문장만."""

    def __init__(self, code: str, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail  # 원인 구분용 짧은 코드 (예: HTTP_400_BLOCKED). URL·키·본문은 넣지 않는다


# ── 레지스트리 ───────────────────────────────────────────────────────────────


@dataclass
class ToolSpec:
    name: str
    description: str  # 기능보다 '언제 쓰는지'
    args_model: type[BaseModel]
    func: Callable[[BaseModel], tuple[Any, dict] | Any]
    source: str
    kind: str  # "external"(외부 API 툴) | "local"(로컬 서버 툴)


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, *, name: str, description: str, args_model: type[BaseModel], source: str,
                 kind: str = "external"):
        def decorator(func):
            self._tools[name] = ToolSpec(name, description, args_model, func, source, kind)
            return func
        return decorator

    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def openai_specs(self, names: list[str] | None = None) -> list[dict]:
        specs = [self._tools[n] for n in (names or self._tools) if n in self._tools]
        return [
            {"type": "function",
             "function": {"name": s.name, "description": s.description,
                          "parameters": s.args_model.model_json_schema()}}
            for s in specs
        ]

    def run(self, name: str, args: dict | None) -> dict:
        started = time.monotonic()
        spec = self._tools.get(name)
        source = spec.source if spec else "UNKNOWN"
        if spec is None:
            return fail(INVALID_INPUT, f"등록되지 않은 Tool이에요: {name}", source, started)
        try:
            parsed = spec.args_model.model_validate(args or {})
        except ValidationError as exc:
            fields = sorted({".".join(map(str, e["loc"])) for e in exc.errors()})
            return fail(INVALID_INPUT, f"입력값을 확인해 주세요: {', '.join(fields)}", source, started)
        try:
            out = spec.func(parsed)
        except ToolError as exc:
            return fail(exc.code, exc.message, source, started, detail=exc.detail)
        except Exception:  # noqa: BLE001 — 어떤 예외도 밖으로 내보내지 않는다
            logger.exception("tool %s failed", name)  # 상세는 서버 로그에만
            return fail(UPSTREAM_ERROR, "외부 서비스 처리 중 문제가 생겼어요.", source, started)
        data, extra = out if isinstance(out, tuple) else (out, {})
        return success(data, source, started, **extra)


def _meta(source: str, started: float, **extra) -> dict:
    meta = {"source": source, "elapsed_ms": int((time.monotonic() - started) * 1000),
            "estimated": False, "notes": []}
    meta.update(extra)
    return meta


def success(data: Any, source: str, started: float, **extra) -> dict:
    return {"ok": True, "data": data, "meta": _meta(source, started, **extra)}


def fail(code: str, message: str, source: str, started: float, detail: str | None = None) -> dict:
    meta = _meta(source, started, detail=detail) if detail else _meta(source, started)
    return {"ok": False, "error": {"code": code, "message": message}, "meta": meta}


REGISTRY = Registry()


# ── HTTP ─────────────────────────────────────────────────────────────────────


@dataclass
class HttpResponse:
    status: int
    text: str


def http_get(url: str, params: dict, headers: dict | None = None) -> HttpResponse:
    """User-Agent를 넣어 GET. 시간 초과·연결 오류·5xx는 1회 재시도. 429는 RATE_LIMITED.

    4xx 본문 해석(키 오류 등)은 각 Tool이 한다. URL·키는 예외 메시지에 넣지 않는다.
    """
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_code, last_detail = UPSTREAM_ERROR, None
    for attempt in range(2):
        if attempt:
            time.sleep(RETRY_DELAY_SEC)
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT_SEC)
        except requests.Timeout:
            last_code, last_detail = TIMEOUT, "TIMEOUT"
            continue
        except requests.RequestException as exc:
            last_code, last_detail = UPSTREAM_ERROR, f"CONNECTION:{type(exc).__name__}"
            continue
        if resp.status_code >= 500:
            last_code, last_detail = UPSTREAM_ERROR, f"HTTP_{resp.status_code}"
            continue
        if resp.status_code == 429:
            raise ToolError(RATE_LIMITED, "외부 서비스 호출 한도를 넘었어요. 잠시 후 다시 시도해 주세요.", "HTTP_429")
        resp.encoding = resp.encoding or "utf-8"
        return HttpResponse(resp.status_code, resp.text)
    logger.warning("http_get failed after retry: %s", last_detail)  # URL에는 키가 있어 남기지 않는다
    if last_code == TIMEOUT:
        raise ToolError(TIMEOUT, "외부 서비스 응답이 늦어요.", last_detail)
    raise ToolError(UPSTREAM_ERROR, "외부 서비스에 연결하지 못했어요.", last_detail)


# ── 캐시 (프로세스 메모리, 하루) ──────────────────────────────────────────────

_cache: dict[str, tuple[float, Any]] = {}


def cached(key: str, compute: Callable[[], Any], ttl: int = CACHE_TTL_SEC) -> Any:
    """성공한 결과만 캐시한다(compute가 예외를 던지면 저장하지 않음)."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    value = compute()
    _cache[key] = (time.monotonic(), value)
    return value


def clear_cache(prefix: str | None = None) -> None:
    """캐시를 비운다. prefix를 주면 그 접두사(예: "kma:")로 시작하는 항목만 지운다."""
    if prefix is None:
        _cache.clear()
        return
    for key in [k for k in _cache if k.startswith(prefix)]:
        _cache.pop(key, None)
