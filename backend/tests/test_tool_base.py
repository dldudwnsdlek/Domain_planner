"""app/tools/base.py — 공통 응답 형식, 레지스트리, HTTP 재시도 (네트워크 없음)."""

import pytest
import requests
from pydantic import BaseModel, Field

from app.tools import base
from app.tools.base import Registry, ToolError


class EchoArgs(BaseModel):
    text: str = Field(description="돌려줄 문자열")
    times: int = Field(default=1, ge=1, le=3)


@pytest.fixture
def registry():
    reg = Registry()

    @reg.register(name="echo", description="문자열을 그대로 돌려줄 때 사용한다.", args_model=EchoArgs, source="TEST")
    def echo(args: EchoArgs):
        if args.text == "boom":
            raise RuntimeError("secret internal detail")
        if args.text == "missing":
            raise ToolError("NOT_FOUND", "없어요")
        return {"text": args.text * args.times}, {"notes": ["반복했어요"]}

    return reg


# ── 공통 응답 형식 · 예외 차단 ─────────────────────────────────────────────────


def test_success_shape(registry):
    result = registry.run("echo", {"text": "a", "times": 2})
    assert result["ok"] is True
    assert result["data"] == {"text": "aa"}
    assert result["meta"]["source"] == "TEST"
    assert isinstance(result["meta"]["elapsed_ms"], int)
    assert result["meta"]["notes"] == ["반복했어요"]
    assert result["meta"]["estimated"] is False


def test_tool_error_becomes_fail(registry):
    result = registry.run("echo", {"text": "missing"})
    assert result == {"ok": False, "error": {"code": "NOT_FOUND", "message": "없어요"},
                      "meta": result["meta"]}


def test_unexpected_exception_never_escapes_and_hides_detail(registry):
    result = registry.run("echo", {"text": "boom"})
    assert result["ok"] is False
    assert result["error"]["code"] == "UPSTREAM_ERROR"
    assert "secret internal detail" not in str(result)


def test_invalid_args_become_invalid_input(registry):
    result = registry.run("echo", {"times": 9})
    assert result["ok"] is False and result["error"]["code"] == "INVALID_INPUT"


def test_unknown_tool_is_invalid_input(registry):
    assert registry.run("nope", {})["error"]["code"] == "INVALID_INPUT"


def test_specs_expose_only_name_description_schema(registry):
    (spec,) = registry.openai_specs()
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "echo"
    assert spec["function"]["description"].startswith("문자열을")
    assert set(spec["function"]["parameters"]["properties"]) == {"text", "times"}


# ── HTTP: User-Agent, 1회 재시도, 상태 코드 분류 ─────────────────────────────────


class FakeResp:
    def __init__(self, status=200, text="ok"):
        self.status_code, self.text, self.encoding = status, text, "utf-8"


def _patch_get(monkeypatch, outcomes):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(headers)
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    monkeypatch.setattr(base.requests, "get", fake_get)
    return calls


def test_http_sets_user_agent(monkeypatch):
    calls = _patch_get(monkeypatch, [FakeResp()])
    base.http_get("http://x", {})
    assert calls[0]["User-Agent"] == base.USER_AGENT


def test_http_retries_once_on_timeout_then_succeeds(monkeypatch):
    calls = _patch_get(monkeypatch, [requests.Timeout(), FakeResp(text="hi")])
    assert base.http_get("http://x", {}).text == "hi"
    assert len(calls) == 2


def test_http_timeout_twice_raises_timeout(monkeypatch):
    _patch_get(monkeypatch, [requests.Timeout(), requests.Timeout()])
    with pytest.raises(ToolError) as exc:
        base.http_get("http://x", {})
    assert exc.value.code == "TIMEOUT"


def test_http_5xx_twice_is_upstream_error(monkeypatch):
    calls = _patch_get(monkeypatch, [FakeResp(502), FakeResp(503)])
    with pytest.raises(ToolError) as exc:
        base.http_get("http://x", {})
    assert exc.value.code == "UPSTREAM_ERROR" and len(calls) == 2


def test_http_429_is_rate_limited_without_retry(monkeypatch):
    calls = _patch_get(monkeypatch, [FakeResp(429)])
    with pytest.raises(ToolError) as exc:
        base.http_get("http://x", {})
    assert exc.value.code == "RATE_LIMITED" and len(calls) == 1


def test_cache_returns_stored_value_without_recomputing():
    base.clear_cache()
    hits = []
    assert base.cached("k", lambda: hits.append(1) or "v") == "v"
    assert base.cached("k", lambda: hits.append(1) or "other") == "v"
    assert hits == [1]


# ── 실패 상세(detail): 원인을 구분하되 URL·키는 넣지 않는다 ──────────────────────


def test_tool_error_detail_goes_to_meta(registry):
    @registry.register(name="blocked", description="차단을 흉내 낼 때 사용한다.", args_model=EchoArgs, source="TEST")
    def blocked(args):
        raise ToolError("UPSTREAM_ERROR", "막혔어요", detail="HTTP_400_BLOCKED")

    result = registry.run("blocked", {"text": "x"})
    assert result["error"]["code"] == "UPSTREAM_ERROR"
    assert result["meta"]["detail"] == "HTTP_400_BLOCKED"


def test_http_failure_details(monkeypatch):
    _patch_get(monkeypatch, [FakeResp(502), FakeResp(503)])
    with pytest.raises(ToolError) as exc:
        base.http_get("http://x", {})
    assert exc.value.detail == "HTTP_503"

    _patch_get(monkeypatch, [requests.ConnectionError(), requests.ConnectionError()])
    with pytest.raises(ToolError) as exc:
        base.http_get("http://x", {})
    assert exc.value.detail == "CONNECTION:ConnectionError"


def test_clear_cache_by_prefix():
    base.clear_cache()
    base.cached("kma:1", lambda: 1)
    base.cached("detail:1", lambda: 2)
    base.clear_cache("kma:")
    assert base.cached("kma:1", lambda: "new") == "new"
    assert base.cached("detail:1", lambda: "new") == 2
