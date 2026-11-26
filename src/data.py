"""종목 데이터 수집: 주가·밸류에이션(yfinance) + 분기 재무(DART 우선, 없으면 yfinance)."""
from __future__ import annotations

import io
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

import requests
import yfinance as yf

CACHE_DIR = Path(".cache")
DART_BASE = "https://opendart.fss.or.kr/api"


# ---------------------------------------------------------------------------
# 종목 코드 해석
# ---------------------------------------------------------------------------
def _has_price(symbol: str) -> bool:
    try:
        return not yf.Ticker(symbol).history(period="5d").empty
    except Exception:
        return False


def _dart_corp_list(api_key: str) -> list[dict]:
    """DART 고유번호 목록(상장사만). 하루 한 번만 내려받도록 캐시."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / f"corpcode_{date.today():%Y%m%d}.xml"
    if not cache.exists():
        r = requests.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": api_key}, timeout=60)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            cache.write_bytes(z.read(z.namelist()[0]))
    corps = []
    for el in ET.parse(cache).getroot().iter("list"):
        code = (el.findtext("stock_code") or "").strip()
        if code:
            corps.append({
                "corp_code": el.findtext("corp_code").strip(),
                "corp_name": el.findtext("corp_name").strip(),
                "stock_code": code,
            })
    return corps


def resolve_ticker(raw: str) -> dict:
    """'005930', '삼성전자', 'NVDA' 같은 입력을 시장/심볼로 바꿔 준다."""
    raw = raw.strip()
    dart_key = os.getenv("DART_API_KEY", "").strip()

    # 한글 종목명 → DART 목록에서 종목코드 찾기
    if re.search(r"[가-힣]", raw):
        if not dart_key:
            raise ValueError(f"'{raw}' 처럼 한글 이름으로 쓰려면 DART_API_KEY가 필요해요. 6자리 종목코드로 적어 주세요.")
        corps = _dart_corp_list(dart_key)
        match = [c for c in corps if c["corp_name"] == raw] or [c for c in corps if raw in c["corp_name"]]
        if not match:
            raise ValueError(f"DART 상장사 목록에서 '{raw}'를 찾지 못했어요.")
        raw = match[0]["stock_code"]

    if re.fullmatch(r"\d{6}", raw):
        for suffix in (".KS", ".KQ"):
            if _has_price(raw + suffix):
                return {"market": "KR", "code": raw, "symbol": raw + suffix, "currency": "KRW"}
        raise ValueError(f"{raw}: 코스피·코스닥 시세를 찾지 못했어요.")

    symbol = raw.upper()
    if not _has_price(symbol):
        raise ValueError(f"{symbol}: 미국 시세를 찾지 못했어요.")
    return {"market": "US", "code": symbol, "symbol": symbol, "currency": "USD"}


# ---------------------------------------------------------------------------
# 분기 재무
# ---------------------------------------------------------------------------
_REV_IDS = {"ifrs-full_Revenue", "ifrs_Revenue"}
_REV_NAMES = {"매출액", "수익(매출액)", "영업수익", "매출", "수익"}
_OP_IDS = {"dart_OperatingIncomeLoss"}
_OP_NAMES = {"영업이익", "영업이익(손실)", "영업손익"}
_NI_IDS = {"ifrs-full_ProfitLoss", "ifrs_ProfitLoss"}
_NI_NAMES = {"당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익", "분기순이익(손실)", "반기순이익(손실)"}


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick(rows: list[dict], ids: set[str], names: set[str]) -> dict | None:
    rows = [r for r in rows if r.get("sj_div") in ("IS", "CIS")]
    for r in rows:
        if r.get("account_id") in ids:
            return r
    for r in rows:
        if r.get("account_nm", "").replace(" ", "") in names:
            return r
    return None


def _dart_report(api_key: str, corp_code: str, year: int, reprt_code: str) -> list[dict] | None:
    for fs_div in ("CFS", "OFS"):  # 연결 우선, 없으면 별도
        r = requests.get(
            f"{DART_BASE}/fnlttSinglAcntAll.json",
            params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": str(year),
                    "reprt_code": reprt_code, "fs_div": fs_div},
            timeout=30,
        )
        js = r.json()
        if js.get("status") == "000" and js.get("list"):
            return js["list"]
    return None


def dart_quarters(stock_code: str, n: int = 8) -> list[dict]:
    """DART 분기 매출·영업이익·순이익(원). 4Q = 연간 − 1~3Q."""
    api_key = os.getenv("DART_API_KEY", "").strip()
    corps = _dart_corp_list(api_key)
    corp = next((c for c in corps if c["stock_code"] == stock_code), None)
    if not corp:
        return []
    quarters: list[dict] = []
    this_year = date.today().year
    for year in range(this_year - 2, this_year + 1):
        got: dict[str, dict] = {}
        for q, code in (("1Q", "11013"), ("2Q", "11012"), ("3Q", "11014"), ("FY", "11011")):
            rows = _dart_report(api_key, corp["corp_code"], year, code)
            if not rows:
                continue
            vals = {}
            for key, ids, names in (("revenue", _REV_IDS, _REV_NAMES), ("op", _OP_IDS, _OP_NAMES),
                                    ("ni", _NI_IDS, _NI_NAMES)):
                row = _pick(rows, ids, names)
                vals[key] = _num(row.get("thstrm_amount")) if row else None
            got[q] = vals
        for q in ("1Q", "2Q", "3Q"):
            if q in got:
                quarters.append({"label": f"{str(year)[2:]}.{q}", **got[q]})
        if "FY" in got and all(q in got for q in ("1Q", "2Q", "3Q")):
            q4 = {}
            for k in ("revenue", "op", "ni"):
                parts = [got[q][k] for q in ("FY", "1Q", "2Q", "3Q")]
                q4[k] = None if any(p is None for p in parts) else parts[0] - sum(parts[1:])
            quarters.append({"label": f"{str(year)[2:]}.4Q", **q4})
    return quarters[-n:]


def yf_quarters(t: yf.Ticker, n: int = 8) -> list[dict]:
    try:
        df = t.quarterly_income_stmt
    except Exception:
        return []
    if df is None or df.empty:
        return []

    def row(*names):
        for nm in names:
            if nm in df.index:
                return df.loc[nm]
        return None

    rev = row("Total Revenue", "Operating Revenue")
    op = row("Operating Income", "Total Operating Income As Reported")
    ni = row("Net Income", "Net Income Common Stockholders")
    out = []
    for col in sorted(df.columns):
        def v(series):
            if series is None:
                return None
            x = series.get(col)
            return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        qn = (col.month - 1) // 3 + 1
        out.append({"label": f"{str(col.year)[2:]}.{qn}Q", "revenue": v(rev), "op": v(op), "ni": v(ni)})
    out = [q for q in out if q["revenue"] is not None]
    return out[-n:]


# ---------------------------------------------------------------------------
# 한 번에 모으기
# ---------------------------------------------------------------------------
_INFO_KEYS = {
    "marketCap": "시가총액", "trailingPE": "PER(TTM)", "forwardPE": "PER(선행)",
    "priceToBook": "PBR", "trailingPegRatio": "PEG", "returnOnEquity": "ROE",
    "debtToEquity": "부채비율(D/E,%)", "currentRatio": "유동비율", "profitMargins": "순이익률",
    "operatingMargins": "영업이익률(TTM)", "revenueGrowth": "매출성장률(YoY)",
    "earningsGrowth": "이익성장률(YoY)", "freeCashflow": "잉여현금흐름", "dividendYield": "배당수익률",
    "beta": "베타", "sector": "섹터", "industry": "산업",
}


def load_company(raw_ticker: str) -> dict:
    tk = resolve_ticker(raw_ticker)
    t = yf.Ticker(tk["symbol"])

    try:
        info = t.info or {}
    except Exception:
        info = {}

    hist = t.history(period="1y")
    close = hist["Close"].dropna()
    last, prev = float(close.iloc[-1]), float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1])
    price = {
        "last": last,
        "change_pct": (last / prev - 1) * 100 if prev else 0.0,
        "high_52w": float(close.max()),
        "low_52w": float(close.min()),
        "return_1y_pct": (last / float(close.iloc[0]) - 1) * 100,
        "as_of": close.index[-1].strftime("%Y-%m-%d"),
    }

    quarters, source = [], "yfinance"
    if tk["market"] == "KR" and os.getenv("DART_API_KEY", "").strip():
        try:
            quarters, source = dart_quarters(tk["code"]), "DART"
        except Exception as e:  # DART가 막히면 yfinance로
            print(f"[warn] DART 실패, yfinance로 대체: {e}")
    if not quarters:
        quarters, source = yf_quarters(t), "yfinance"

    for q in quarters:
        q["op_margin"] = (q["op"] / q["revenue"] * 100) if q.get("op") is not None and q.get("revenue") else None

    name = info.get("shortName") or info.get("longName") or tk["code"]
    if tk["market"] == "KR" and os.getenv("DART_API_KEY", "").strip():
        try:
            corp = next(c for c in _dart_corp_list(os.environ["DART_API_KEY"]) if c["stock_code"] == tk["code"])
            name = corp["corp_name"]
        except Exception:
            pass

    metrics = {}
    for k, label in _INFO_KEYS.items():
        v = info.get(k)
        if v not in (None, "", "Infinity"):
            metrics[label] = v

    return {**tk, "name": name, "price": price, "quarters": quarters,
            "fin_source": source, "metrics": metrics}
