"""깃헙에 올리기 전에, 폴더 안에 키·토큰이 섞여 있지 않은지 검사한다.

    python scripts/check_secrets.py

문제가 없으면 "OK", 있으면 파일 이름과 줄 번호를 보여 주고 종료 코드 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "텔레그램 봇 토큰": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "Claude 토큰/API 키": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "DART 키(40자리)": re.compile(r"\b[0-9a-f]{40}\b"),
    "값이 채워진 키 설정": re.compile(
        r"^\s*(TELEGRAM_BOT_TOKEN|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|DART_API_KEY)[ \t]*=[ \t]*[^\s#]+", re.M),
}
SKIP_DIRS = {".git", ".cache", "out", "__pycache__", ".venv"}
NEVER_UPLOAD = {".env"}


def main() -> int:
    problems = []
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.name in NEVER_UPLOAD:
            problems.append(f"{p.relative_to(ROOT)}: 이 파일은 올리면 안 돼요 (업로드할 때 빼세요)")
            continue
        if not p.is_file() or p.stat().st_size > 2_000_000 or p.name == "check_secrets.py":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pat in PATTERNS.items():
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{p.relative_to(ROOT)}:{line}: {label} 의심")
    if problems:
        print("⚠️ 올리기 전에 확인하세요:")
        print("\n".join("  - " + x for x in problems))
        return 1
    print("OK — 키·토큰으로 보이는 값이 없어요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
