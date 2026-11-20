"""커밋 전 키 검사. 값은 출력하지 않고 '파일:줄 · 종류'만 보여 준다.

실행:
  .venv/bin/python scripts/scan_secrets.py         # git에 staged된 변경만 검사 (git add 후)
  .venv/bin/python scripts/scan_secrets.py --all   # git 대상 파일 전체 검사
검사: (1) .env에 설정된 실제 키 문자열(원문·URL 인코딩)  (2) 키처럼 보이는 패턴
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.tools.redact import configured_secrets, _variants  # noqa: E402

PATTERNS = {
    "KakaoAK 헤더 값": re.compile(r"KakaoAK\s+[A-Za-z0-9]{16,}"),
    "service/serviceKey 값": re.compile(r"(?i)\b(service|servicekey)=(?!REDACTED)[A-Za-z0-9%+/=]{16,}"),
    "OpenAI형 키": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "Bearer 토큰": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    "긴 base64/hex 문자열": re.compile(r"(?<![A-Za-z0-9/+=_\-])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9/+=_\-])"),
}
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".db")


def staged_lines() -> list[tuple[str, int, str]]:
    diff = subprocess.run(["git", "diff", "--cached", "-U0"], capture_output=True, text=True, cwd=ROOT).stdout
    out, current, line_no = [], None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            line_no = int(re.search(r"\+(\d+)", line).group(1)) - 1
        elif line.startswith("+") and current:
            line_no += 1
            out.append((current, line_no, line[1:]))
    return out


def all_lines() -> list[tuple[str, int, str]]:
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, text=True, cwd=ROOT).stdout.split()
    out = []
    for f in files:
        if f.endswith(SKIP_SUFFIX):
            continue
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        out += [(f, i, line) for i, line in enumerate(text.splitlines(), 1)]
    return out


def main(argv: list[str]) -> int:
    lines = all_lines() if "--all" in argv else staged_lines()
    secrets = [v for s in configured_secrets() for v in _variants(s)]
    findings = []
    for path, no, line in lines:
        if any(s in line for s in secrets):
            findings.append((path, no, "실제 키 값"))
        findings += [(path, no, name) for name, pat in PATTERNS.items() if pat.search(line)]
    for path, no, kind in findings:
        print(f"⚠ {path}:{no} · {kind}")
    print(f"검사한 줄 {len(lines)}개 · 의심 {len(findings)}건")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
