"""텔레그램 발송 (Bot API 직접 호출)."""
from __future__ import annotations

import html
import os
import time
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT, TEXT_LIMIT = 1024, 4096


def esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def _cfg() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 비어 있어요 (깃헙 Secrets 확인).")
    return token, chat


def _post(method: str, data: dict, files: dict | None = None) -> dict:
    token, _ = _cfg()
    for attempt in range(3):
        r = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=60)
        js = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if js.get("ok"):
            return js
        retry = js.get("parameters", {}).get("retry_after")
        if retry and attempt < 2:
            time.sleep(int(retry) + 1)
            continue
        raise RuntimeError(f"텔레그램 {method} 실패: {r.status_code} {js.get('description', r.text[:300])}")
    raise RuntimeError(f"텔레그램 {method} 실패")


def send_photo(path: Path, caption: str) -> dict:
    _, chat = _cfg()
    with open(path, "rb") as f:
        return _post("sendPhoto", {"chat_id": chat, "caption": caption[:CAPTION_LIMIT], "parse_mode": "HTML"},
                     files={"photo": f})


def send_text(text: str) -> None:
    _, chat = _cfg()
    for chunk in split(text):
        _post("sendMessage", {"chat_id": chat, "text": chunk, "parse_mode": "HTML",
                              "disable_web_page_preview": "true"})


def split(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """빈 줄(문단) 단위로 잘라 한도를 넘지 않게 나눈다."""
    out, cur = [], ""
    for para in text.split("\n\n"):
        cand = f"{cur}\n\n{para}" if cur else para
        if len(cand) <= limit:
            cur = cand
        else:
            if cur:
                out.append(cur)
            cur = para[:limit]
    if cur:
        out.append(cur)
    return out


def test_message() -> None:
    send_text("✅ Legends Desk 연결 테스트 — 깃헙에서 보낸 메시지가 잘 도착했어요.")
