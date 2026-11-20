"""app/tools/redact.py — 저장·출력 전 키 제거 테스트."""

import pytest

from app.tools.redact import SecretLeakError, assert_no_secrets, redact

KOPIS = "abcdef0123456789kopis"
KMA = "kma+key/with=special=="  # Decoding 키에는 + / = 이 들어갈 수 있다


def test_query_param_values_are_redacted():
    url = "http://www.kopis.or.kr/openApi/restful/pblprfr?service=XYZ123&stdate=20261121"
    assert redact(url) == "http://www.kopis.or.kr/openApi/restful/pblprfr?service=REDACTED&stdate=20261121"


def test_service_key_param_is_redacted_case_insensitive():
    url = "https://apis.data.go.kr/x?ServiceKey=ab%2Bcd&serviceKey=zz&pageNo=1"
    out = redact(url)
    assert "ab%2Bcd" not in out and "zz&" not in out
    assert "pageNo=1" in out


def test_authorization_header_value_is_redacted():
    assert redact("Authorization: KakaoAK fake-test-value") == "Authorization: REDACTED"


def test_known_secret_values_are_removed_including_url_encoded():
    from urllib.parse import quote

    text = f"echo {KOPIS} and {quote(KMA, safe='')} and {KMA}"
    out = redact(text, secrets=[KOPIS, KMA])
    assert KOPIS not in out
    assert KMA not in out
    assert quote(KMA, safe="") not in out


def test_empty_secrets_are_ignored():
    assert redact("hello", secrets=["", None]) == "hello"


def test_assert_no_secrets_raises_without_echoing_value():
    with pytest.raises(SecretLeakError) as exc:
        assert_no_secrets(f"body {KOPIS}", secrets=[KOPIS])
    assert KOPIS not in str(exc.value)


def test_assert_no_secrets_passes_on_clean_text():
    assert_no_secrets("clean", secrets=[KOPIS])
