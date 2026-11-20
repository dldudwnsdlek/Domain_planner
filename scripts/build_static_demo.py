"""정적 예시(데모) 배포본 만들기: frontend/ → dist/

- 백엔드·API 키 없이 동작한다. 화면은 저장된 실제 응답(frontend/demo-data.js)으로만 그린다.
- <html data-mode="demo">를 붙여 주소에 ?demo가 없어도 예시 모드로 열리게 한다.
- 보안 헤더(_headers, Netlify 형식)를 함께 만든다.
- 결과물에 키처럼 보이는 문자열이 있으면 배포본을 만들지 않고 실패한다.

실행: python3 scripts/build_static_demo.py   (외부 호출 0회, 표준 라이브러리만 사용)
Netlify: netlify.toml의 build.command로 같은 명령을 실행하고 dist/를 공개한다.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend"
OUT = ROOT / "dist"
FILES = ("index.html", "styles.css", "app.js", "demo-data.js")

# 키 노출 검사: 이름=값 형태의 긴 값, 카카오 인증 헤더, 흔한 토큰 형식
SECRET_PATTERNS = [
    re.compile(r"(?i)(service_?key|api_?key|gms_key|x-api-key)\s*[=:]\s*['\"]?[A-Za-z0-9%+/_-]{20,}"),
    re.compile(r"KakaoAK\s+[A-Za-z0-9]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
]

HEADERS = """/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
"""


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in FILES:
        shutil.copy2(SRC / name, OUT / name)

    index = OUT / "index.html"
    html = index.read_text(encoding="utf-8")
    if '<html lang="ko">' not in html:
        print("index.html에서 <html lang=\"ko\">를 찾지 못했어요", file=sys.stderr)
        return 1
    index.write_text(html.replace('<html lang="ko">', '<html lang="ko" data-mode="demo">', 1), encoding="utf-8")
    (OUT / "_headers").write_text(HEADERS, encoding="utf-8")

    for path in OUT.iterdir():
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                print(f"키처럼 보이는 문자열이 있어 배포본을 만들지 않았어요: {path.name}", file=sys.stderr)
                shutil.rmtree(OUT)
                return 1

    print(f"dist/ 생성 완료: {', '.join(sorted(p.name for p in OUT.iterdir()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
