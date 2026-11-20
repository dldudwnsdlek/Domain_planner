"""LLM 객체는 이 모듈의 get_llm()에서만 만든다.

- 모델: claude-haiku-5-5 (2026-11-20 강사 안내). SSAFY GMS의 Anthropic 중계 경로를
  langchain-openai의 ChatOpenAI(OpenAI 호환 호출)로 부른다. 기존 gpt-4.1-mini(OpenAI 경로)는
  GMS 상위 OpenAI 조직의 지출 한도(HTTP 429)로 쓸 수 없게 되어 바꿨다. 두 경로 모두 지원한다.
- 키·주소: GMS_KEY, LLM_BASE_URL을 코드에서 명시적으로 넘긴다.
  ChatOpenAI는 base_url을 안 넘기면 OpenAI 기본 주소(api.openai.com)로 보낸다.
  그러면 GMS 키가 제공사로 전송되므로, 주소가 비었거나 안전하지 않으면 객체를 만들지 않는다.
- Anthropic 경로 차이: x-api-key 헤더가 필요하고(HTTP 클라이언트에 붙임 — repr에 키가 안 보이게),
  temperature를 받지 않는다(HTTP 400) → 보내지 않는다.
- 용도(purpose)는 analyze · plan · respond 세 가지뿐이다. 판정·재계획·로깅은 코드가 한다.
"""

from typing import Literal
from urllib.parse import urlparse

import httpx
from langchain_openai import ChatOpenAI

from app import config

Purpose = Literal["analyze", "plan", "respond", "worker"]

# OpenAI 경로에서만 적용한다. Anthropic 경로(claude-haiku-5-5)는 temperature를 거부해 보내지 않는다.
TEMPERATURE: dict[str, float] = {
    "analyze": 0.0,  # 의도·조건 추출: 같은 입력이면 같은 결과
    "plan": 0.0,  # Tool 선택: 같은 입력이면 같은 결과
    "respond": 0.3,  # 요약 문장: 약간의 표현 다양성
    "worker": 0.0,  # (심화 F3021) 복구 가능한 실패에서만: 재시도·건너뜀·재계획 요청 판단
}

# 게이트웨이가 json_schema(response_format)를 거부하면 "function_calling"으로 바꾼다.
# 런타임 자동 폴백 대신 연결 확인 스크립트(scripts/check_llm.py)로 한 번 판정해 고정한다.
# 자동 폴백은 실패할 때마다 LLM 호출이 1회 늘어 "요청당 LLM 3회"가 흔들리기 때문이다.
STRUCTURED_OUTPUT_METHOD: Literal["json_schema", "function_calling"] = "json_schema"

REQUEST_TIMEOUT_SEC = 30
MAX_RETRIES = 1


class LLMConfigError(Exception):
    """LLM 설정 오류. 메시지에는 키·주소 값을 넣지 않는다."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"LLMConfigError(code={self.code!r})"


_PROVIDER_DOMAINS = ("openai.com", "anthropic.com")  # GMS 키를 제공사로 직접 보내지 않는다


def _is_openai_host(host: str) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in _PROVIDER_DOMAINS)


def _uses_anthropic_route(base_url: str) -> bool:
    """GMS의 Anthropic 중계 경로(.../gmsapi/api.anthropic.com/v1)인가. 이 경로는 x-api-key 헤더가 필요하다."""
    return "/api.anthropic.com" in urlparse(base_url).path


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise LLMConfigError(
            "CONFIG_INVALID_BASE_URL",
            "LLM_BASE_URL은 https://로 시작하는 GMS 접속 주소여야 해요.",
        )
    if _is_openai_host(host):
        raise LLMConfigError(
            "CONFIG_INVALID_BASE_URL",
            "LLM_BASE_URL이 제공사(OpenAI·Anthropic) 주소예요. GMS 키가 외부로 전송되지 않도록 호출하지 않았어요.",
        )


def get_llm(purpose: Purpose) -> ChatOpenAI:
    """용도별 temperature가 적용된 ChatOpenAI를 만든다. 설정이 잘못되면 LLMConfigError."""
    if purpose not in TEMPERATURE:
        raise ValueError(f"알 수 없는 LLM 용도: {purpose}")

    base_url = config.get_str("LLM_BASE_URL")
    if not base_url:
        raise LLMConfigError(
            "CONFIG_MISSING_BASE_URL",
            "LLM_BASE_URL(GMS 접속 주소)이 비어 있어 LLM을 호출하지 않았어요.",
        )
    _validate_base_url(base_url)

    api_key = config.get_str("GMS_KEY")
    if not api_key:
        raise LLMConfigError("CONFIG_MISSING_KEY", "GMS_KEY가 설정되지 않았어요.")

    anthropic = _uses_anthropic_route(base_url)
    return ChatOpenAI(
        model=config.llm_model(),
        api_key=api_key,
        base_url=base_url,
        # claude-haiku-5-5는 temperature를 받지 않는다(HTTP 400 "`temperature` is deprecated") → 보내지 않음
        temperature=None if anthropic else TEMPERATURE[purpose],
        timeout=REQUEST_TIMEOUT_SEC,
        max_retries=MAX_RETRIES,
        use_responses_api=False,
        # 강사 안내(2026-11-20): GMS Anthropic 경로는 OpenAI 호환 호출에 x-api-key 헤더를 함께 요구한다.
        # default_headers에 넣으면 객체 repr에 키가 그대로 찍히므로, 헤더는 HTTP 클라이언트에 둔다.
        http_client=_anthropic_http_client(api_key) if anthropic else None,
    )


def _anthropic_http_client(api_key: str) -> httpx.Client:
    return httpx.Client(headers={"x-api-key": api_key}, timeout=REQUEST_TIMEOUT_SEC)


def get_structured_llm(
    schema: type,
    purpose: Purpose,
    method: Literal["json_schema", "function_calling"] | None = None,
):
    """Pydantic 모델로 구조화 출력하는 Runnable을 만든다."""
    return get_llm(purpose).with_structured_output(
        schema, method=method or STRUCTURED_OUTPUT_METHOD
    )


def llm_error_code(exc: BaseException) -> str:
    """LLM 호출 예외를 출력해도 안전한 코드로 바꾼다. 메시지(키 일부가 섞일 수 있음)는 쓰지 않는다."""
    import openai
    from langchain_core.exceptions import OutputParserException
    from pydantic import ValidationError

    if isinstance(exc, LLMConfigError):
        return exc.code
    if isinstance(exc, openai.APITimeoutError):  # APIConnectionError의 하위 클래스라 먼저 검사
        return "TIMEOUT"
    if isinstance(exc, openai.APIConnectionError):
        return "CONNECTION_ERROR"
    if isinstance(exc, openai.AuthenticationError):
        return "AUTH_FAILED"
    if isinstance(exc, openai.PermissionDeniedError):
        return "PERMISSION_DENIED"
    if isinstance(exc, openai.NotFoundError):
        return "NOT_FOUND"
    if isinstance(exc, openai.RateLimitError):
        return "RATE_LIMITED"
    if isinstance(exc, (openai.BadRequestError, openai.UnprocessableEntityError)):
        return "BAD_REQUEST"
    if isinstance(exc, openai.InternalServerError):
        return "UPSTREAM_ERROR"
    if isinstance(exc, openai.APIStatusError):
        return f"HTTP_{exc.status_code}"
    if isinstance(exc, (ValidationError, OutputParserException)):
        return "PARSE_ERROR"
    return f"UNEXPECTED_{type(exc).__name__}"
