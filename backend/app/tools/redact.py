"""저장·출력 전에 키를 지운다.

1) 패턴 제거: URL의 service= / serviceKey= 값, Authorization 헤더 값
2) 값 대조 제거: 실제 키 문자열(원문·URL 인코딩)을 찾아 지운다
3) assert_no_secrets: 저장 직전 마지막 확인. 남아 있으면 저장을 막는다(값은 메시지에 넣지 않음)
"""

import re
from collections.abc import Iterable
from urllib.parse import quote, quote_plus

from app import config

MASK = "REDACTED"
SECRET_ENV_NAMES = ("KOPIS_API_KEY", "KAKAO_REST_API_KEY", "KMA_SERVICE_KEY", "GMS_KEY")

_PARAM = re.compile(r"(?i)\b(service|servicekey)=([^&\s\"'<>]+)")
_AUTH = re.compile(r"(?i)(authorization\"?\s*[:=]\s*\"?)[^\"\n,}]+")


class SecretLeakError(Exception):
    """저장하려는 내용에 키가 남아 있음."""


def configured_secrets() -> list[str]:
    return [v for v in (config.get_str(n) for n in SECRET_ENV_NAMES) if v]


def _variants(secret: str) -> set[str]:
    return {secret, quote(secret, safe=""), quote_plus(secret)}


def redact(text: str, secrets: Iterable[str | None] | None = None) -> str:
    text = _PARAM.sub(lambda m: f"{m.group(1)}={MASK}", text)
    text = _AUTH.sub(lambda m: f"{m.group(1)}{MASK}", text)
    for secret in secrets or []:
        if not secret:
            continue
        for variant in sorted(_variants(secret), key=len, reverse=True):
            text = text.replace(variant, MASK)
    return text


def assert_no_secrets(text: str, secrets: Iterable[str | None]) -> None:
    for secret in secrets:
        if secret and any(v in text for v in _variants(secret)):
            raise SecretLeakError("저장하려는 내용에 키가 남아 있어 저장을 중단했어요.")
