"""scripts/check_llm.py — LLM 연결 확인 스크립트 테스트 (실제 LLM 호출 없음)."""

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from app import llm as llm_module
from app.llm import LLMConfigError
from scripts import check_llm

SECRET = "fake-key-SHOULD-NOT-BE-PRINTED-1234"
_REQ = httpx.Request("POST", "https://gms.example.com/v1/chat/completions")


def _status_error(cls, status: int):
    # OpenAI 401 메시지에는 마스킹된 키 일부가 들어갈 수 있다 → 원문을 출력하면 안 된다.
    return cls(
        f"Incorrect API key provided: {SECRET}",
        response=httpx.Response(status, request=_REQ),
        body=None,
    )


class StubLLM:
    """invoke / bind_tools만 흉내 내는 대역. 호출 횟수를 센다."""

    def __init__(self, replies=None, error=None):
        self.replies = list(replies or [])
        self.error = error
        self.invocations = 0

    def invoke(self, _input):
        self.invocations += 1
        if self.error is not None:
            raise self.error
        return self.replies.pop(0)

    def bind_tools(self, _tools):
        return self


def _factory(stub):
    return lambda purpose: stub


TOOL_CALL = AIMessage(
    content="",
    tool_calls=[
        {"name": "search_performances", "args": {"date": "2026-11-21"}, "id": "c1"}
    ],
)


def _structured_ok(schema, purpose, method=None):
    class _Runnable:
        def invoke(self, _input):
            return schema(intent="chitchat", date=None)

    return _Runnable()


# ── 오류 코드 변환 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (_status_error(openai.AuthenticationError, 401), "AUTH_FAILED"),
        (_status_error(openai.PermissionDeniedError, 403), "PERMISSION_DENIED"),
        (_status_error(openai.NotFoundError, 404), "NOT_FOUND"),
        (_status_error(openai.BadRequestError, 400), "BAD_REQUEST"),
        (_status_error(openai.UnprocessableEntityError, 422), "BAD_REQUEST"),
        (_status_error(openai.RateLimitError, 429), "RATE_LIMITED"),
        (_status_error(openai.InternalServerError, 502), "UPSTREAM_ERROR"),
        (openai.APITimeoutError(request=_REQ), "TIMEOUT"),
        (openai.APIConnectionError(request=_REQ), "CONNECTION_ERROR"),
        (LLMConfigError("CONFIG_MISSING_KEY", "x"), "CONFIG_MISSING_KEY"),
        (RuntimeError(SECRET), "UNEXPECTED_RuntimeError"),
    ],
)
def test_error_code_mapping(exc, code):
    assert check_llm.error_code(exc) == code


# ── 설정 오류: 호출 0회 ────────────────────────────────────────────────────────


def test_missing_base_url_stops_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("GMS_KEY", SECRET)
    monkeypatch.setenv("LLM_BASE_URL", "")

    def _fail(*args, **kwargs):
        raise AssertionError("설정 오류인데 ChatOpenAI를 만들었다")

    monkeypatch.setattr(llm_module, "ChatOpenAI", _fail)

    exit_code = check_llm.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "CONFIG_MISSING_BASE_URL" in out
    assert "LLM 호출 0회" in out
    assert SECRET not in out


# ── 정상 경로 ─────────────────────────────────────────────────────────────────


def test_all_checks_pass_with_three_calls():
    stub = StubLLM(replies=[AIMessage(content="서울"), TOOL_CALL])

    report = check_llm.run_checks(_factory(stub), _structured_ok)

    assert [r.ok for r in report.results] == [True, True, True]
    assert report.calls == 3
    assert report.exit_code == 0


# ── (b) Tool 선택 ─────────────────────────────────────────────────────────────


def test_tool_check_fails_when_model_answers_without_tool_call():
    stub = StubLLM(replies=[AIMessage(content="연극 A를 추천해요")])

    result = check_llm.check_tool_choice(_factory(stub))

    assert result.ok is False
    assert result.code == "NO_TOOL_CALL"


def test_tool_check_fails_on_unexpected_tool_name():
    wrong = AIMessage(
        content="", tool_calls=[{"name": "get_weather", "args": {}, "id": "c1"}]
    )

    result = check_llm.check_tool_choice(_factory(StubLLM(replies=[wrong])))

    assert result.ok is False
    assert result.code == "WRONG_TOOL"


# ── (c) 구조화 출력: json_schema 거부 → function_calling ───────────────────────


def test_structured_falls_back_to_function_calling_on_bad_request():
    methods = []

    def factory(schema, purpose, method=None):
        methods.append(method)

        class _Runnable:
            def invoke(self, _input):
                if method == "json_schema":
                    raise _status_error(openai.BadRequestError, 400)
                return schema(intent="chitchat", date=None)

        return _Runnable()

    result = check_llm.check_structured(factory)

    assert methods == ["json_schema", "function_calling"]
    assert result.ok is True
    assert result.calls == 2
    assert "function_calling" in result.detail


def test_structured_does_not_fall_back_on_auth_failure():
    methods = []

    def factory(schema, purpose, method=None):
        methods.append(method)

        class _Runnable:
            def invoke(self, _input):
                raise _status_error(openai.AuthenticationError, 401)

        return _Runnable()

    result = check_llm.check_structured(factory)

    assert methods == ["json_schema"]  # 다시 해도 같은 실패 → 재시도하지 않음
    assert result.code == "AUTH_FAILED"


# ── 치명적 실패는 나머지 확인을 건너뜀 · 원문 미출력 ───────────────────────────


def test_fatal_failure_skips_remaining_checks_and_hides_message(capsys):
    stub = StubLLM(error=_status_error(openai.AuthenticationError, 401))

    report = check_llm.run_checks(_factory(stub), _structured_ok)
    check_llm.print_report(report)

    out = capsys.readouterr().out
    assert report.calls == 1
    assert [r.code for r in report.results] == ["AUTH_FAILED", "SKIPPED", "SKIPPED"]
    assert "HTTP 401" in out
    assert SECRET not in out
    assert "Incorrect API key" not in out
