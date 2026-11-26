# Legends Desk · 레전드 5 오늘의 종목

월가 전설 5명(버핏·멍거·그레이엄·린치·드러켄밀러)의 투자 원칙을 AI가 공개 재무 데이터에 적용해,
**평일 아침마다 텔레그램 채널에 자동으로 올리는** 봇입니다.

분석과 발송은 모두 **깃헙 서버(GitHub Actions)** 에서 돌아갑니다.
내 PC가 꺼져 있거나 회사 보안으로 텔레그램이 막혀 있어도 상관없어요.

```
[매일 07:10 KST, 깃헙 서버]
 종목 고르기 (queue.txt → rotation.txt)
   → 주가·재무 수집 (yfinance, 국내는 DART)
   → 위원회 5명 판단 (Claude Code CLI)
   → 대시보드 이미지 생성
   → 텔레그램 채널에 이미지 + 판단 근거 발송
   → 발송 기록 저장 (history.csv)
```

## 폴더 구성

| 경로 | 내용 |
|---|---|
| `.github/workflows/daily.yml` | 자동 실행 일정과 단계 |
| `src/main.py` | 전체 흐름 (종목 선택 → 분석 → 발송) |
| `src/data.py` | 주가·분기 재무 수집 (DART / yfinance) |
| `src/market.py` | 오늘의 시황 (코스피·코스닥·S&P·나스닥·환율·美10년물) |
| `src/committee.py` | Claude 호출, 5명 판단 JSON 정리 |
| `src/dashboard.py` | 대시보드 이미지 |
| `src/tg.py` | 텔레그램 발송 |
| `prompts/committee.md` | 위원 5명의 원칙·말투 (여기를 고치면 판단 스타일이 바뀜) |
| `tickers/queue.txt` | **다음에 올릴 종목** (매일 직접 고르는 곳) |
| `tickers/rotation.txt` | queue가 비었을 때 돌아가는 기본 목록 |
| `data/history.csv` | 발송 기록 (자동) |

---

## 1. 준비물 (Secrets 4개)

| 이름 | 필수 | 어디서 받나 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | 휴대폰 텔레그램 → **@BotFather** → `/mybots` → 봇 선택 → *API Token* |
| `TELEGRAM_CHAT_ID` | ✅ | 공개 채널이면 `@채널아이디`, 비공개면 `-100…` 숫자 (아래 참고) |
| `CLAUDE_CODE_OAUTH_TOKEN` | ✅ (또는 API 키) | Claude Code가 깔린 PC에서 `claude setup-token` |
| `DART_API_KEY` | 선택 | opendart.fss.or.kr → 인증키 신청 (국내 종목 분기 재무가 정확해짐) |

### 텔레그램 채널 준비
1. 채널 → 관리자 → **관리자 추가** → 내 봇 검색 → **메시지 게시** 권한 켜기
2. `TELEGRAM_CHAT_ID`
   - 공개 채널: 채널 링크가 `t.me/legendsdesk`면 → `@legendsdesk`
   - 비공개 채널: 봇이 관리자인 상태에서 채널에 아무 글이나 올린 뒤, **휴대폰 브라우저**로
     `https://api.telegram.org/bot<봇토큰>/getUpdates` 를 열면 `"chat":{"id":-100xxxxxxxxxx` 가 보여요. 그 숫자 전체.

### Claude 토큰 (구독 계정 그대로 사용)
Claude Code가 설치된 PC의 터미널(PowerShell)에서:
```
claude setup-token
```
브라우저 로그인 후 나오는 `sk-ant-oat01-…` 토큰을 복사해 두세요. (한 번만 보여 줘요)
API 키로 돌리고 싶다면 대신 `ANTHROPIC_API_KEY` 를 넣으면 됩니다. 둘 다 있으면 API 키가 우선이에요.

---

## 🔐 공개 저장소로 올릴 때 키 보호
- 키·토큰은 **코드나 파일에 절대 쓰지 않고**, 깃헙 **Secrets** 에만 넣습니다. Secrets는 공개 저장소에서도 다른 사람이 볼 수 없고, 로그에 찍혀도 `***` 로 가려져요.
- 이 저장소의 워크플로는 **다른 사람의 Pull Request로는 실행되지 않아요** (schedule / 수동 실행만). 수동 실행은 저장소 주인만 할 수 있어요.
- 오류가 나도 로그에 키가 남지 않도록 `src/main.py` 가 오류 메시지 속 키를 가려서 출력해요.
- 웹 업로드(드래그)는 `.gitignore` 를 무시해요. **`.env`, `out/`, `.cache/` 는 끌어다 놓지 마세요.**
- 올리기 전 검사: `python scripts/check_secrets.py` → `OK` 가 나오면 안전. (워크플로도 매번 이 검사를 먼저 돌려요)
- 실수로 키를 올렸다면: 파일을 지우는 것만으로는 부족해요(커밋 기록에 남음). **바로 키를 재발급**하세요.
  BotFather `/revoke`, `claude setup-token` 재실행, DART 키 재발급 → Secrets 값 교체.

## 2. 깃헙에 올리기

1. github.com 로그인 → 오른쪽 위 **＋ → New repository**
   - Repository name: `legends-desk`
   - **Public** 또는 Private (어느 쪽이든 키는 Secrets에만 있어 안전해요)
   - 나머지는 그대로 → **Create repository**
2. 만들어진 빈 저장소 화면에서 **uploading an existing file** 링크 클릭
3. 압축을 푼 `legends-desk` 폴더 **안의 내용 전부**(`.github`, `src`, `prompts`, `tickers`, `data`, `README.md` …)를 드래그해서 놓기
   - 폴더째가 아니라 **안의 것들**을 끌어다 놓아야 해요.
4. 아래 **Commit changes** 클릭
5. 저장소 첫 화면에 `.github` 폴더가 보이는지 확인
   - 안 보이면: **Add file → Create new file** → 이름 칸에 `.github/workflows/daily.yml` 입력 → `daily.yml` 내용 붙여넣기 → Commit

## 3. Secrets 넣기
저장소 **Settings → Secrets and variables → Actions → New repository secret**
위 표의 이름 그대로(대소문자 포함) 하나씩 추가.

(선택) 같은 화면 **Variables** 탭에 `CLAUDE_MODEL` 을 만들면 모델을 지정할 수 있어요. 비우면 기본 모델.

## 4. 첫 실행 (3단계로 확인)
**Actions** 탭 → (처음이면 *I understand… enable* 클릭) → 왼쪽 **Legends Desk 데일리 발송** → **Run workflow**

1. `test_telegram` 체크 → Run → 채널에 "연결 테스트" 메시지가 오면 OK
2. `dry_run` 체크 + ticker `005930` → Run → 끝나면 실행 화면 아래 **Artifacts** 에서 이미지 내려받아 확인
3. 체크 없이 Run → 실제 채널 발송

그다음부터는 **평일 07:10 전후 자동 발송**이에요. (깃헙 사정으로 10~30분 늦을 수 있어요)

---

## 매일 종목 바꾸기
- **방법 A (추천)**: 깃헙 웹/모바일 앱에서 `tickers/queue.txt` → 연필 아이콘 → 종목을 한 줄에 하나씩 적고 Commit.
  맨 위 줄부터 하루 하나씩 쓰이고, 발송되면 자동으로 지워져요. 며칠 치를 미리 적어 둬도 됩니다.
- **방법 B**: Actions → Run workflow → `ticker` 칸에 입력해 바로 발송.
- queue가 비어 있으면 `rotation.txt` 에서 차례대로 돌아가요.

입력 형식: 국내 `005930` (DART 키가 있으면 `삼성전자`도 가능) / 미국 `NVDA`

## 발송 시간 바꾸기
`daily.yml` 의 `cron: "10 22 * * 0-4"` 는 **UTC** 기준이에요. 한국시간 = UTC + 9시간.
예) 한국 08:00 발송 → `"0 23 * * 0-4"`

## 내 PC에서 테스트 (선택)
```
pip install -r requirements.txt
copy .env.example .env      # 값 채우기
python -m src.main --dry-run --ticker 005930
```
결과는 `out/` 폴더에 이미지·캡션으로 저장돼요.

## 문제 해결
| 증상 | 확인할 것 |
|---|---|
| `chat not found` | 봇이 채널 관리자인지, CHAT_ID 형식(`@아이디` 또는 `-100…`) |
| `Unauthorized` | 봇 토큰 오타 / BotFather에서 토큰 재발급했는지 |
| `claude 실행 실패` / 인증 오류 | `CLAUDE_CODE_OAUTH_TOKEN` 다시 발급해 교체 |
| 분기 재무가 비어 있음 | 국내 종목이면 `DART_API_KEY` 추가 |
| 한글이 □로 깨짐 | 워크플로의 "한글 폰트 설치" 단계 로그 확인 |
| 자동 실행이 안 됨 | Actions 탭에서 워크플로가 *disabled* 인지 확인 |

---
⚠️ 실제 투자자 본인의 의견이 아니라, 그들의 원칙을 AI가 공개 재무 데이터에 적용한 결과입니다.
참고용 정보이며 투자 권유나 매매 추천이 아닙니다. 데이터 오류나 누락이 있을 수 있습니다.
