"""LLM 연결 확인 (Phase 1 · 명세 '도구 연결 확인').

실행:  .venv/bin/python scripts/check_llm.py

확인 항목
  (a) 짧은 질문 1회 호출                       — purpose=respond
  (b) Tool 1개를 bind_tools로 넘겼을 때 Tool 호출을 고르는지 — purpose=plan
  (c) 구조화 출력(with_structured_output)이 되는지      — purpose=analyze
      json_schema가 거부되면(BAD_REQUEST) function_calling으로 한 번 더 시도한다.

출력 원칙
  - 항목별 OK / FAIL과 오류 코드(+HTTP 상태)만 출력한다.
  - 키·주소 값, 오류 원문, 모델 응답 본문은 출력하지 않는다.
    (OpenAI 호환 401 메시지에는 마스킹된 키 일부가 들어갈 수 있기 때문)
  - 설정 오류면 LLM을 한 번도 부르지 않는다. 인증 실패처럼 다시 해도 같은 실패면 나머지를 건너뛴다.

LLM 호출: 보통 3회, json_schema가 거부되면 최대 4회.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

import openai  # noqa: E402
from langchain_core.exceptions import OutputParserException  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

from app import config  # noqa: E402
from app.llm import LLMConfigError, get_llm, get_structured_llm, llm_error_code  # noqa: E402

# 다시 시도해도 결과가 같은 실패 → 나머지 확인을 건너뛴다(호출 절약).
FATAL_CODES = {"AUTH_FAILED", "PERMISSION_DENIED", "NOT_FOUND", "CONNECTION_ERROR"}
# json_schema 방식 자체가 게이트웨이에서 안 될 때 나는 실패 → function_calling으로 재시도.
STRUCTURED_FALLBACK_CODES = {"BAD_REQUEST", "PARSE_ERROR"}


# ── 결과 형식 ─────────────────────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    ok: bool
    code: str | None = None
    http_status: int | None = None
    detail: str = ""  # 비밀이 아닌 짧은 정보만 (예: method=json_schema)
    calls: int = 0


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)
    config_code: str | None = None

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.results)

    @property
    def exit_code(self) -> int:
        return 0 if self.results and all(r.ok for r in self.results) else 1


error_code = llm_error_code  # 앱과 같은 분류 규칙을 쓴다


def _http_status(exc: BaseException) -> int | None:
    return exc.status_code if isinstance(exc, openai.APIStatusError) else None


def _failed(name: str, exc: BaseException, calls: int) -> CheckResult:
    return CheckResult(
        name, ok=False, code=error_code(exc), http_status=_http_status(exc), calls=calls
    )


def _skipped(name: str, reason: str) -> CheckResult:
    return CheckResult(name, ok=False, code="SKIPPED", detail=reason)


# ── 확인용 Tool · 스키마 ──────────────────────────────────────────────────────


@tool
def search_performances(date: str, region: str, genre: str) -> str:
    """날짜·지역·장르 조건으로 그날 볼 수 있는 공연 후보를 찾을 때 사용한다.

    Args:
        date: 관람 날짜 (YYYY-MM-DD)
        region: 지역 이름 (예: 대학로)
        genre: 장르 (예: 연극, 뮤지컬)
    """
    return "연결 확인용 — 실제로 실행하지 않음"


class IntentCheck(BaseModel):
    """요청 분석 결과(연결 확인용 축소판)."""

    intent: Literal["plan_request", "fact_query", "chitchat"] = Field(
        description="plan_request: 관람 계획 요청 / fact_query: 사실 조회 / chitchat: 그 밖의 대화"
    )
    date: str | None = Field(description="관람 날짜 YYYY-MM-DD. 언급이 없으면 null")


NAME_BASIC = "(a) 짧은 질문 1회 호출"
NAME_TOOL = "(b) bind_tools Tool 선택"
NAME_STRUCTURED = "(c) 구조화 출력"

LLMFactory = Callable[[str], object]
StructuredFactory = Callable[..., object]


# ── 확인 항목 ─────────────────────────────────────────────────────────────────


def check_basic(llm_factory: LLMFactory = get_llm) -> CheckResult:
    try:
        reply = llm_factory("respond").invoke("한 단어로 답해 주세요. 대한민국의 수도는?")
    except Exception as exc:  # noqa: BLE001 — 어떤 예외든 코드로만 보고
        return _failed(NAME_BASIC, exc, calls=1)
    content = getattr(reply, "content", "")
    if not (isinstance(content, str) and content.strip()):
        return CheckResult(NAME_BASIC, ok=False, code="EMPTY_RESPONSE", calls=1)
    return CheckResult(NAME_BASIC, ok=True, calls=1)


def check_tool_choice(llm_factory: LLMFactory = get_llm) -> CheckResult:
    try:
        bound = llm_factory("plan").bind_tools([search_performances])
        reply = bound.invoke("2026년 11월 21일 토요일에 대학로에서 볼 수 있는 연극을 찾아줘.")
    except Exception as exc:  # noqa: BLE001
        return _failed(NAME_TOOL, exc, calls=1)
    tool_calls = getattr(reply, "tool_calls", None) or []
    if not tool_calls:
        return CheckResult(NAME_TOOL, ok=False, code="NO_TOOL_CALL", calls=1)
    chosen = tool_calls[0].get("name")
    if chosen != search_performances.name:
        return CheckResult(NAME_TOOL, ok=False, code="WRONG_TOOL", calls=1)
    return CheckResult(NAME_TOOL, ok=True, detail=f"tool={chosen}", calls=1)


def check_structured(
    structured_factory: StructuredFactory = get_structured_llm,
) -> CheckResult:
    calls = 0
    rejected_code: str | None = None
    for method in ("json_schema", "function_calling"):
        try:
            runnable = structured_factory(IntentCheck, "analyze", method=method)
            calls += 1
            result = runnable.invoke("안녕! 이거 어떻게 써?")
            if not isinstance(result, IntentCheck):
                raise OutputParserException("구조화 결과가 스키마와 다름")
        except Exception as exc:  # noqa: BLE001
            code = error_code(exc)
            if method == "json_schema" and code in STRUCTURED_FALLBACK_CODES:
                rejected_code = code
                continue
            return _failed(NAME_STRUCTURED, exc, calls=calls)
        if rejected_code:
            detail = (
                f"json_schema 거부({rejected_code}) → function_calling 성공 · "
                "app/llm.py의 STRUCTURED_OUTPUT_METHOD를 'function_calling'으로 바꿔야 함"
            )
        else:
            detail = f"method={method}"
        return CheckResult(NAME_STRUCTURED, ok=True, detail=detail, calls=calls)
    return CheckResult(NAME_STRUCTURED, ok=False, code="UNREACHABLE", calls=calls)


def run_checks(
    llm_factory: LLMFactory = get_llm,
    structured_factory: StructuredFactory = get_structured_llm,
) -> Report:
    report = Report()
    names = (NAME_BASIC, NAME_TOOL, NAME_STRUCTURED)

    # 설정 사전 점검: 객체 생성만 하고 네트워크는 쓰지 않는다.
    try:
        llm_factory("respond")
    except LLMConfigError as exc:
        report.config_code = exc.code
        report.results = [_skipped(n, "설정 오류") for n in names]
        return report

    basic = check_basic(llm_factory)
    report.results.append(basic)
    if not basic.ok and basic.code in FATAL_CODES:
        report.results += [_skipped(n, "(a) 실패와 같은 원인") for n in names[1:]]
        return report

    report.results.append(check_tool_choice(llm_factory))
    report.results.append(check_structured(structured_factory))
    return report


# ── 출력 ─────────────────────────────────────────────────────────────────────


def _status_text(result: CheckResult) -> str:
    if result.ok:
        text = "OK"
    elif result.code == "SKIPPED":
        text = "SKIP"
    else:
        text = f"FAIL {result.code}"
        if result.http_status is not None:
            text += f" (HTTP {result.http_status})"
    if result.detail:
        text += f"  — {result.detail}"
    return text


def print_report(report: Report) -> None:
    if report.config_code:
        print(f"[설정] FAIL {report.config_code}")
    for result in report.results:
        print(f"{result.name} → {_status_text(result)}")
    passed = sum(r.ok for r in report.results)
    print(f"결과: {passed}/{len(report.results)} 성공 · LLM 호출 {report.calls}회")


def main() -> int:
    is_set = lambda name: "설정됨" if config.get_str(name) else "비어 있음"  # noqa: E731
    print(f"LLM 연결 확인 — 모델 {config.llm_model()} (GMS 경유)")
    print(f"GMS_KEY: {is_set('GMS_KEY')} · LLM_BASE_URL: {is_set('LLM_BASE_URL')}")
    report = run_checks()
    print_report(report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
