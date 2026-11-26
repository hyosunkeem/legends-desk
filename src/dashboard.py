"""대시보드 이미지 한 장(1080x1350, 텔레그램·인스타 세로 비율)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

KOR_NAMES = {
    "Warren Buffett": "워런 버핏", "Charlie Munger": "찰리 멍거", "Benjamin Graham": "벤저민 그레이엄",
    "Peter Lynch": "피터 린치", "Stanley Druckenmiller": "스탠리 드러켄밀러",
}
# 국내 관례: 상승·매수=빨강, 하락·매도=파랑
SIGNAL_COLOR = {"BUY": "#D64545", "HOLD": "#8A8F98", "SELL": "#2F6FD0"}
UP, DOWN, FLAT = "#D64545", "#2F6FD0", "#8A8F98"
INK, SUB, LINE, BG, CARD = "#1D2129", "#6B7280", "#E5E7EB", "#F6F6F3", "#FFFFFF"
BAR, MARGIN = "#C9CED6", "#1D2129"
BRAND = "Legends Desk"


def _set_font():
    for name in ("NanumGothic", "Noto Sans CJK KR", "Malgun Gothic", "AppleGothic", "Noto Sans KR"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def _box(fig, x, y, w, h, color=CARD, ec=LINE, r=0.012):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                      transform=fig.transFigure, fc=color, ec=ec, lw=1, zorder=-1))


def fmt_amount(v: float | None, market: str) -> str:
    if v is None:
        return "-"
    if market == "KR":
        return f"{v / 1e12:,.1f}조" if abs(v) >= 1e13 else f"{v / 1e9:,.0f}십억"
    return f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.0f}M"


def fmt_price(v: float, market: str) -> str:
    return f"{v:,.0f}원" if market == "KR" else f"${v:,.2f}"


def _chg_color(x: float) -> str:
    return UP if x > 0 else DOWN if x < 0 else FLAT


def render(company: dict, market: list[dict], result: dict, out_path: str | Path, run_date: str) -> Path:
    _set_font()
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100)
    fig.patch.set_facecolor(BG)
    mk = company["market"]
    L, R = 0.055, 0.945
    W = R - L

    # ── 헤더 ────────────────────────────────────────────────
    fig.text(L, 0.962, "레전드 5 · 오늘의 종목", fontsize=15, color=SUB, weight="bold")
    fig.text(R, 0.962, run_date, fontsize=15, color=SUB, ha="right")
    fig.text(L, 0.918, company["name"], fontsize=34, color=INK, weight="bold")
    p = company["price"]
    fig.text(L, 0.889, f"{company['code']} · {'국내' if mk == 'KR' else '미국'}", fontsize=14, color=SUB)
    fig.text(R, 0.918, fmt_price(p["last"], mk), fontsize=26, color=INK, weight="bold", ha="right")
    fig.text(R, 0.889, f"{p['change_pct']:+.2f}%  ·  {p['as_of']} 종가",
             fontsize=14, color=_chg_color(p["change_pct"]), ha="right")

    # ── 위원회 결론 ─────────────────────────────────────────
    c = result["committee"]
    col = SIGNAL_COLOR[c["signal"]]
    _box(fig, L, 0.765, W, 0.105)
    fig.text(L + 0.025, 0.842, "위원회 결론", fontsize=13, color=SUB, weight="bold")
    fig.text(L + 0.025, 0.787, c["signal"], fontsize=40, color=col, weight="bold")
    fig.text(L + 0.205, 0.795, f"확신도\n{c['confidence']}%", fontsize=13, color=SUB, linespacing=1.4)
    head = "\n".join(textwrap.wrap(c["headline"] or c["summary"], 24)[:2])
    fig.text(L + 0.33, 0.817, head, fontsize=17, color=INK, weight="bold", va="center", linespacing=1.45)

    # ── 5명 판단 ────────────────────────────────────────────
    top, row_h = 0.745, 0.064
    fig.text(L, top, "위원 5명의 판단", fontsize=15, color=INK, weight="bold")
    for i, a in enumerate(result["agents"]):
        y = top - 0.012 - (i + 1) * row_h
        _box(fig, L, y, W, row_h - 0.008)
        mid = y + (row_h - 0.008) / 2
        fig.text(L + 0.02, mid + 0.009, KOR_NAMES.get(a["name"], a["name"]), fontsize=15, color=INK,
                 weight="bold", va="center")
        fig.text(L + 0.02, mid - 0.012, a["name"], fontsize=10.5, color=SUB, va="center")
        scol = SIGNAL_COLOR[a["signal"]]
        fig.text(L + 0.265, mid, a["signal"], fontsize=15, color="white", weight="bold", va="center",
                 ha="center", bbox=dict(boxstyle="round,pad=0.35", fc=scol, ec="none"))
        # 확신도 막대
        bx, bw = L + 0.33, 0.13
        fig.patches.append(FancyBboxPatch((bx, mid - 0.004), bw, 0.008, boxstyle="round,pad=0,rounding_size=0.004",
                                          transform=fig.transFigure, fc=LINE, ec="none"))
        fig.patches.append(FancyBboxPatch((bx, mid - 0.004), bw * a["confidence"] / 100, 0.008,
                                          boxstyle="round,pad=0,rounding_size=0.004",
                                          transform=fig.transFigure, fc=scol, ec="none"))
        fig.text(bx + bw + 0.012, mid, f"{a['confidence']}", fontsize=13, color=INK, va="center", weight="bold")
        summ = "\n".join(textwrap.wrap(a["summary"], 27)[:2])
        fig.text(L + 0.52, mid, summ, fontsize=12.5, color=INK, va="center", linespacing=1.35)

    # ── 분기 매출 · 영업이익률 ───────────────────────────────
    qs = company["quarters"]
    unit = "십억 원" if mk == "KR" else "USD bn"
    div = 1e9
    fig.text(L, 0.375, f"분기 매출 · 영업이익률", fontsize=15, color=INK, weight="bold")
    fig.text(R, 0.375, f"매출 단위: {unit} · 출처: {company['fin_source']}", fontsize=11, color=SUB, ha="right")
    _box(fig, L, 0.175, W, 0.19)
    ax = fig.add_axes([L + 0.06, 0.205, W - 0.13, 0.14])
    ax.set_facecolor(CARD)
    if qs:
        x = range(len(qs))
        revs = [(q["revenue"] or 0) / div for q in qs]
        bars = ax.bar(x, revs, color=BAR, width=0.6, zorder=2)
        bars[-1].set_color("#7C8594")
        ax.set_xticks(list(x), [q["label"] for q in qs], fontsize=10.5, color=SUB)
        ax.tick_params(axis="y", labelsize=10, colors=SUB, length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(axis="y", color=LINE, lw=0.8, zorder=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax2 = ax.twinx()
        mg = [q.get("op_margin") for q in qs]
        pts = [(i, m) for i, m in enumerate(mg) if m is not None]
        if pts:
            ax2.plot([p_[0] for p_ in pts], [p_[1] for p_ in pts], color=MARGIN, lw=2.2, marker="o", ms=5, zorder=3)
            for i, m in pts:
                ax2.annotate(f"{m:.1f}%", (i, m), textcoords="offset points", xytext=(0, 8),
                             ha="center", fontsize=9.5, color=INK, weight="bold")
            lo, hi = min(m for _, m in pts), max(m for _, m in pts)
            pad = max(2.0, (hi - lo) * 0.6)
            ax2.set_ylim(lo - pad * 2.2, hi + pad)
        ax2.tick_params(axis="y", labelsize=10, colors=SUB, length=0)
        ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        for s in ax2.spines.values():
            s.set_visible(False)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "분기 재무 데이터를 불러오지 못했어요", ha="center", va="center", color=SUB, fontsize=13,
                transform=ax.transAxes)

    # ── 오늘의 시황 ─────────────────────────────────────────
    fig.text(L, 0.148, "오늘의 시황", fontsize=15, color=INK, weight="bold")
    as_of = market[0]["as_of"] if market else ""
    fig.text(R, 0.148, f"{as_of} 종가 기준", fontsize=11, color=SUB, ha="right")
    n = max(len(market), 1)
    gap = 0.008
    tw = (W - gap * (n - 1)) / n
    for i, m in enumerate(market):
        x0 = L + i * (tw + gap)
        _box(fig, x0, 0.068, tw, 0.07)
        fig.text(x0 + tw / 2, 0.118, m["name"], fontsize=11, color=SUB, ha="center")
        val = f"{m['last']:.2f}%" if m["kind"] == "bp" else f"{m['last']:,.2f}" if m["last"] < 100 else f"{m['last']:,.0f}"
        fig.text(x0 + tw / 2, 0.095, val, fontsize=13.5, color=INK, ha="center", weight="bold")
        chg = f"{m['change']:+.0f}bp" if m["kind"] == "bp" else f"{m['change']:+.2f}%"
        fig.text(x0 + tw / 2, 0.076, chg, fontsize=11, color=_chg_color(m["change"]), ha="center")

    # ── 푸터 ────────────────────────────────────────────────
    fig.text(L, 0.032, BRAND, fontsize=14, color=INK, weight="bold")
    fig.text(R, 0.032, "AI가 투자 원칙을 공개 데이터에 적용한 참고용 정보이며, 투자 권유가 아닙니다.",
             fontsize=10.5, color=SUB, ha="right")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path
