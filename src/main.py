"""Legends Desk 데일리 실행.

    python -m src.main                  # queue.txt → rotation.txt 순서로 종목을 골라 발송
    python -m src.main --ticker NVDA    # 종목 지정
    python -m src.main --dry-run        # 텔레그램에 안 올리고 out/ 에만 저장
    python -m src.main --test-telegram  # 텔레그램 연결만 확인
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "tickers" / "queue.txt"
ROTATION = ROOT / "tickers" / "rotation.txt"
HISTORY = ROOT / "data" / "history.csv"
OUT = ROOT / "out"
KST = timezone(timedelta(hours=9))
SHORT = {"Warren Buffett": "버핏", "Charlie Munger": "멍거", "Benjamin Graham": "그레이엄",
         "Peter Lynch": "린치", "Stanley Druckenmiller": "드러켄밀러"}
WEEKDAY = "월화수목금토일"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """로컬 테스트용 .env (깃헙에서는 Secrets가 대신함)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── 종목 고르기 ────────────────────────────────────────────
def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.split("#", 1)[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()]


def peek_queue() -> str | None:
    return next((ln for ln in _lines(QUEUE) if ln), None)


def consume_queue(ticker: str) -> None:
    raw = QUEUE.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(raw):
        if ln.split("#", 1)[0].strip() == ticker:
            del raw[i]
            break
    QUEUE.write_text("\n".join(raw) + "\n", encoding="utf-8")


def next_rotation() -> str:
    rot = [ln for ln in _lines(ROTATION) if ln]
    if not rot:
        raise SystemExit("tickers/rotation.txt 가 비어 있어요.")
    last = None
    if HISTORY.exists():
        rows = list(csv.DictReader(HISTORY.open(encoding="utf-8")))
        for r in reversed(rows):
            if r.get("ticker") in rot:
                last = r["ticker"]
                break
    return rot[(rot.index(last) + 1) % len(rot)] if last else rot[0]


def append_history(company: dict, result: dict, run_date: str) -> None:
    HISTORY.parent.mkdir(exist_ok=True)
    new = not HISTORY.exists()
    with HISTORY.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "ticker", "name", "signal", "confidence"])
        w.writerow([run_date, company["input"], company["name"],
                    result["committee"]["signal"], result["committee"]["confidence"]])


# ── 메시지 ────────────────────────────────────────────────
def build_messages(company: dict, market: list[dict], result: dict) -> tuple[str, str]:
    from .tg import esc
    c = result["committee"]
    votes = " · ".join(f"{SHORT[a['name']]} {a['signal']} {a['confidence']}" for a in result["agents"])
    last_q = company["quarters"][-1]["label"] if company["quarters"] else "-"
    mkt_date = market[0]["as_of"] if market else company["price"]["as_of"]
    caption = (
        f"📌 <b>오늘의 종목 · {esc(company['name'])} ({esc(company['code'])})</b>\n\n"
        f"🏛 위원회 결론: <b>{c['signal']}</b> (확신도 {c['confidence']}%)\n"
        f"{esc(c['headline'])}\n\n"
        f"🗳 {votes}\n\n"
        f"📈 {esc(result['market_comment'])}\n\n"
        f"💬 의견과 다음 종목 신청은 댓글로!\n"
        f"<i>참고용 정보이며 투자 권유가 아닙니다.</i>"
    )
    parts = [f"🧾 <b>{esc(company['name'])} — 위원별 판단 근거</b>"]
    for a in result["agents"]:
        parts.append(f"<b>{SHORT[a['name']]} ({a['name']}) · {a['signal']} {a['confidence']}</b>\n"
                     f"{esc(a['reasoning'])}")
    parts.append(f"🏛 <b>위원회 정리</b>\n{esc(c['summary'])}")
    parts.append(f"<i>재무: 최근 공시({last_q}, {company['fin_source']}) · 시황: {mkt_date} 종가 기준\n"
                 f"실제 투자자 본인의 의견이 아니라, 그들의 원칙을 AI가 공개 데이터에 적용한 결과예요. "
                 f"투자 판단과 책임은 본인에게 있습니다.</i>\n\n— Legends Desk")
    return caption, "\n\n".join(parts)


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-telegram", action="store_true")
    args = ap.parse_args()

    from . import tg
    if args.test_telegram:
        tg.test_message()
        print("텔레그램 테스트 메시지 전송 완료")
        return 0

    from . import committee, dashboard, data, market

    now = datetime.now(KST)
    run_date = f"{now:%Y.%m.%d} ({WEEKDAY[now.weekday()]})"

    ticker, from_queue = args.ticker.strip(), False
    if not ticker:
        ticker = peek_queue()
        from_queue = bool(ticker)
    if not ticker:
        ticker = next_rotation()
    print(f"▶ 오늘의 종목: {ticker} ({'queue' if from_queue else 'rotation' if not args.ticker else '직접 지정'})")

    company = data.load_company(ticker)
    company["input"] = ticker
    print(f"  {company['name']} · 분기 {len(company['quarters'])}개 ({company['fin_source']})")
    mkt = market.snapshot()
    result = committee.run(company, mkt)
    print(f"  위원회: {result['committee']['signal']} {result['committee']['confidence']}")

    OUT.mkdir(exist_ok=True)
    stamp = f"{now:%Y%m%d}_{company['code']}"
    png = dashboard.render(company, mkt, result, OUT / f"{stamp}.png", run_date)
    caption, details = build_messages(company, mkt, result)
    (OUT / f"{stamp}.json").write_text(json.dumps({"company": company, "market": mkt, "result": result},
                                                  ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (OUT / f"{stamp}_caption.txt").write_text(caption + "\n\n-----\n\n" + details, encoding="utf-8")

    if args.dry_run:
        print(f"  [dry-run] 텔레그램 발송 생략 → {png}")
        return 0

    tg.send_photo(png, caption)
    tg.send_text(details)
    print("  텔레그램 발송 완료")
    append_history(company, result, f"{now:%Y-%m-%d}")
    if from_queue:
        consume_queue(ticker)
    return 0


SECRET_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "CLAUDE_CODE_OAUTH_TOKEN",
              "ANTHROPIC_API_KEY", "DART_API_KEY")


def redact(text: str) -> str:
    """오류 메시지에 키가 섞여 나오지 않도록 가린다 (공개 저장소의 Actions 로그 대비)."""
    import re
    for k in SECRET_ENV:
        v = os.getenv(k, "").strip()
        if len(v) >= 6:
            text = text.replace(v, f"***{k}***")
    text = re.sub(r"bot\d{6,}:[A-Za-z0-9_-]{30,}", "bot***", text)
    text = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "sk-ant-***", text)
    text = re.sub(r"(crtfc_key=)[^&\s]+", r"\1***", text)
    return text


if __name__ == "__main__":
    import traceback
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        print(redact(traceback.format_exc()), file=sys.stderr)
        sys.exit(1)
