"""app/llm.py — LLM 객체 생성 규칙 테스트 (네트워크 호출 없음)."""

import pytest
from pydantic import BaseModel

from app import llm as llm_module
from app.llm import LLMConfigError, get_llm, get_structured_llm

GATEWAY_URL = "https://gms.example.com/gmsapi/api.openai.com/v1"
FAKE_KEY = "fake-gms-key-for-test-0000"


@pytest.fixture(autouse=True)
def llm_env(monkeypatch):
    """테스트마다 LLM 관련 환경 변수를 알려진 값으로 고정한다."""
    monkeypatch.setenv("GMS_KEY", FAKE_KEY)
    monkeypatch.setenv("LLM_BASE_URL", GATEWAY_URL)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)


def _forbid_client_creation(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("설정 오류인데 ChatOpenAI를 만들었다")

    monkeypatch.setattr(llm_module, "ChatOpenAI", _fail)


# ── 설정 오류: LLM 객체를 만들기 전에 막아야 한다 ──────────────────────────────


def test_empty_base_url_raises_before_creating_client(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "")
    _forbid_client_creation(monkeypatch)

    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")

    assert exc.value.code == "CONFIG_MISSING_BASE_URL"


def test_whitespace_only_base_url_counts_as_empty(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "   ")
    _forbid_client_creation(monkeypatch)

    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")

    assert exc.value.code == "CONFIG_MISSING_BASE_URL"


def test_empty_key_raises_before_creating_client(monkeypatch):
    monkeypatch.setenv("GMS_KEY", "")
    _forbid_client_creation(monkeypatch)

    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")

    assert exc.value.code == "CONFIG_MISSING_KEY"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",  # OpenAI 기본 주소: GMS 키가 OpenAI로 전송됨
        "https://API.OPENAI.COM/v1",
        "https://eu.api.openai.com/v1",
        "http://gms.example.com/v1",  # 평문 http: 키가 암호화 없이 전송됨
        "gms.example.com/v1",  # scheme 없음
        "https:///v1",  # host 없음
    ],
)
def test_unsafe_base_url_is_rejected(monkeypatch, url):
    monkeypatch.setenv("LLM_BASE_URL", url)
    _forbid_client_creation(monkeypatch)

    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")

    assert exc.value.code == "CONFIG_INVALID_BASE_URL"


def test_config_error_message_never_echoes_url_or_key(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://gms.example.com/v1?token=SECRET-IN-URL")

    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")

    text = f"{exc.value} {exc.value!r}"
    assert "SECRET-IN-URL" not in text
    assert FAKE_KEY not in text


def test_unknown_purpose_is_rejected():
    with pytest.raises(ValueError):
        get_llm("judge")  # 판정은 코드(순수 함수)가 한다 — LLM 용도가 아님


# ── 정상 생성: GMS 주소·키·모델·temperature ─────────────────────────────────────


def test_gateway_url_with_openai_in_path_is_allowed():
    """GMS 주소는 경로에 api.openai.com이 들어갈 수 있다. host만 검사해야 한다."""
    llm = get_llm("analyze")

    assert llm.openai_api_base == GATEWAY_URL
    assert str(llm.root_client.base_url).rstrip("/") == GATEWAY_URL


def test_uses_gms_key_and_url_even_if_openai_env_vars_exist(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-env-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    llm = get_llm("analyze")

    assert llm.openai_api_key.get_secret_value() == FAKE_KEY
    assert str(llm.root_client.base_url).rstrip("/") == GATEWAY_URL


def test_key_is_masked_in_repr():
    llm = get_llm("analyze")

    assert FAKE_KEY not in repr(llm)
    assert FAKE_KEY not in str(llm)


@pytest.mark.parametrize(
    ("purpose", "temperature"),
    [("analyze", 0.0), ("plan", 0.0), ("respond", 0.3)],
)
def test_temperature_by_purpose(purpose, temperature):
    assert get_llm(purpose).temperature == temperature


def test_model_defaults_to_claude_haiku():
    assert get_llm("analyze").model_name == "claude-haiku-5-5"


def test_model_follows_llm_model_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")

    assert get_llm("analyze").model_name == "gpt-4.1-mini"


def test_chat_completions_api_is_pinned():
    """게이트웨이 호환성을 위해 Responses API로 자동 전환되지 않게 고정한다."""
    assert get_llm("analyze").use_responses_api is False


# ── 구조화 출력 ────────────────────────────────────────────────────────────────


class _Sample(BaseModel):
    intent: str


def test_structured_llm_defaults_to_json_schema():
    structured = get_structured_llm(_Sample, "analyze")

    assert llm_module.STRUCTURED_OUTPUT_METHOD == "json_schema"
    assert "response_format" in structured.first.kwargs


def test_structured_llm_can_switch_to_function_calling():
    structured = get_structured_llm(_Sample, "analyze", method="function_calling")

    assert "tools" in structured.first.kwargs
    assert "response_format" not in structured.first.kwargs


# ── GMS Anthropic 경로 (강사 안내: claude 모델을 ChatOpenAI로 호출) ─────────────

ANTHROPIC_GATEWAY = "https://gms.ssafy.io/gmsapi/api.anthropic.com/v1"


def test_anthropic_gateway_adds_x_api_key_header(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", ANTHROPIC_GATEWAY)
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")
    llm = get_llm("analyze")
    assert llm.model_name == "claude-haiku-5-5"
    assert llm.http_client.headers["x-api-key"] == FAKE_KEY
    assert llm.openai_api_key.get_secret_value() == FAKE_KEY
    assert FAKE_KEY not in repr(llm)


def test_openai_gateway_does_not_send_extra_header():
    assert get_llm("analyze").http_client is None


def test_direct_anthropic_host_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.anthropic.com/v1")
    _forbid_client_creation(monkeypatch)
    with pytest.raises(LLMConfigError) as exc:
        get_llm("analyze")
    assert exc.value.code == "CONFIG_INVALID_BASE_URL"


def test_anthropic_route_omits_temperature(monkeypatch):
    """claude-haiku-5-5는 temperature를 거부한다(실측 HTTP 400) → 요청에 넣지 않는다."""
    monkeypatch.setenv("LLM_BASE_URL", ANTHROPIC_GATEWAY)
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")
    llm = get_llm("respond")
    assert llm.temperature is None
    assert "temperature" not in llm._get_request_payload("ping")
