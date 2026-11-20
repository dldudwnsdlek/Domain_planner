"""설정 로딩.

- 저장소 루트의 `.env`를 환경 변수로 올린다(이미 있는 환경 변수는 덮어쓰지 않음).
- 값은 호출할 때마다 `os.getenv`로 읽는다. 테스트에서 환경 변수를 바꿔도 바로 반영된다.
- 이 모듈은 값을 출력하거나 로그에 남기지 않는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH, override=False)

DEFAULT_LLM_MODEL = "claude-haiku-5-5"  # 2026-11-20 강사 안내 (GMS Anthropic 경로)


def get_str(name: str, default: str = "") -> str:
    """환경 변수를 앞뒤 공백을 지워 읽는다. 비어 있으면 default."""
    return os.getenv(name, "").strip() or default


def llm_model() -> str:
    return get_str("LLM_MODEL", DEFAULT_LLM_MODEL)


def get_int(name: str, default: int) -> int:
    """정수 설정. 비었거나 숫자가 아니면 default."""
    try:
        return int(get_str(name)) if get_str(name) else default
    except ValueError:
        return default


def max_replan() -> int:
    return get_int("MAX_REPLAN", 3)


def detail_fetch_limit() -> int:
    return get_int("DETAIL_FETCH_LIMIT", 10)


def exit_buffer_min() -> int:
    return get_int("EXIT_BUFFER_MIN", 10)


def db_path() -> Path:
    raw = get_str("DB_PATH", "./data/app.db")
    path = Path(raw)
    return path if path.is_absolute() else ROOT_DIR / path


def service_status() -> dict[str, bool]:
    """서비스별 키 설정 여부 (boolean만 — 값은 절대 내보내지 않음)."""
    return {
        "kopis": bool(get_str("KOPIS_API_KEY")),
        "kakao": bool(get_str("KAKAO_REST_API_KEY")),
        "kma": bool(get_str("KMA_SERVICE_KEY")),
        "llm": bool(get_str("GMS_KEY")) and bool(get_str("LLM_BASE_URL")),
    }


AGENT_MODES = ("A", "B", "C")


def agent_mode() -> str:
    """(심화 F3021) A 단일 Agent / B Planner·Worker(Worker LLM 끔) / C Planner·Worker(Worker LLM 켬)."""
    # 기본값 C: 비교 실험(docs/experiment.md)에서 정상 경로 비용은 A와 같고 복구 경로에서 가장 좋았다
    mode = get_str("AGENT_MODE", "C").upper()
    return mode if mode in AGENT_MODES else "C"
