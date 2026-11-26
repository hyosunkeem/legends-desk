"""위원회 실행: Claude Code CLI(`claude -p`)로 5명의 판단을 JSON으로 받는다.

인증은 CLI가 알아서 처리한다.
- CLAUDE_CODE_OAUTH_TOKEN : Claude 구독 계정 토큰(`claude setup-token`으로 발급)  ← 추천
- ANTHROPIC_API_KEY       : API 키(사용량만큼 과금)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

AGENTS = ["Warren Buffett", "Charlie Munger", "Benjamin Graham", "Peter Lynch", "Stanley Druckenmiller"]
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "committee.md"


def _build_prompt(company: dict, market: list[dict]) -> str:
    payload = {
        "종목": {"이름": company["name"], "코드": company["code"], "시장": company["market"],
               "통화": company["currency"]},
        "주가": company["price"],
        "분기실적(오래된→최근)": company["quarters"],
        "분기실적_단위": "원" if company["market"] == "KR" else "USD",
        "분기실적_출처": company["fin_source"],
        "밸류에이션·재무지표": company["metrics"],
        "시황": market,
    }
    return (PROMPT_FILE.read_text(encoding="utf-8")
            + "\n\n## 오늘 점검할 데이터\n"
            + json.dumps(payload, ensure_ascii=False, indent=1, default=str))


def _call_claude(prompt: str) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI가 없어요. `npm install -g @anthropic-ai/claude-code`로 설치하세요.")
    cmd = [exe, "-p", "--output-format", "json", "--tools", ""]
    model = os.getenv("CLAUDE_MODEL", "").strip()
    if model:
        cmd += ["--model", model]
    # 깃헙에서 안 쓰는 Secret은 빈 문자열로 들어오므로 지워 준다
    env = {k: v for k, v in os.environ.items()
           if not (k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN") and not v.strip())}
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          encoding="utf-8", timeout=600, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"claude 실행 실패 (code {proc.returncode}): {proc.stderr[-1500:] or proc.stdout[-1500:]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout
    if envelope.get("is_error"):
        raise RuntimeError(f"claude 오류: {envelope.get('result')}")
    return envelope.get("result", "")


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("응답에서 JSON을 찾지 못했어요.")
    return json.loads(text[start:end + 1])


def _norm_signal(s) -> str:
    s = str(s).upper()
    return next((x for x in ("BUY", "SELL", "HOLD") if x in s), "HOLD")


def _norm_conf(c) -> int:
    try:
        return max(0, min(100, int(round(float(c)))))
    except (TypeError, ValueError):
        return 50


def normalize(raw: dict) -> dict:
    raw_agents = [a for a in (raw.get("agents") or []) if isinstance(a, dict)]
    by_name = {a.get("name", ""): a for a in raw_agents}
    agents = []
    for i, name in enumerate(AGENTS):
        a = by_name.get(name) or (raw_agents[i] if i < len(raw_agents) else {})
        agents.append({
            "name": name,
            "signal": _norm_signal(a.get("signal", "HOLD")),
            "confidence": _norm_conf(a.get("confidence", 50)),
            "summary": str(a.get("summary", "")).strip(),
            "reasoning": str(a.get("reasoning", "")).strip(),
        })
    c = raw.get("committee", {}) or {}
    committee = {
        "signal": _norm_signal(c.get("signal", "HOLD")),
        "confidence": _norm_conf(c.get("confidence", 50)),
        "headline": str(c.get("headline", "")).strip(),
        "summary": str(c.get("summary", "")).strip(),
    }
    return {"agents": agents, "committee": committee,
            "market_comment": str(raw.get("market_comment", "")).strip()}


def run(company: dict, market: list[dict]) -> dict:
    prompt = _build_prompt(company, market)
    last_err = None
    for attempt in range(2):  # JSON이 깨지면 한 번 더
        try:
            return normalize(_extract_json(_call_claude(prompt)))
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            print(f"[warn] 위원회 응답 파싱 실패({attempt + 1}/2): {e}")
            prompt += "\n\n(주의: 반드시 JSON 객체 하나만 출력해.)"
    raise RuntimeError(f"위원회 응답을 읽지 못했어요: {last_err}")
