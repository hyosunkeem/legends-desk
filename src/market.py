"""오늘의 시황: 발송 직전 거래일 종가 기준 주요 지수·환율·금리."""
from __future__ import annotations

import yfinance as yf

INDICES = [
    ("KOSPI", "^KS11", "pct"),
    ("KOSDAQ", "^KQ11", "pct"),
    ("S&P 500", "^GSPC", "pct"),
    ("NASDAQ", "^IXIC", "pct"),
    ("원/달러", "KRW=X", "pct"),
    ("美 10년물", "^TNX", "bp"),
]


def snapshot() -> list[dict]:
    rows = []
    for name, sym, kind in INDICES:
        try:
            close = yf.Ticker(sym).history(period="10d")["Close"].dropna()
            last, prev = float(close.iloc[-1]), float(close.iloc[-2])
            chg = (last - prev) * 100 if kind == "bp" else (last / prev - 1) * 100
            rows.append({"name": name, "last": last, "change": chg, "kind": kind,
                         "as_of": close.index[-1].strftime("%m/%d")})
        except Exception as e:
            print(f"[warn] 시황 {name} 실패: {e}")
    return rows
