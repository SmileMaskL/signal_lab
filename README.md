# Signal Lab

미국 주식 RSI/MACD 기반 자동 시그널 봇 + Telegram 구독 수익화 플랫폼

## 기능

| 기능 | FREE | PREMIUM |
|------|------|---------|
| RSI 시그널 | ✅ (3종목) | ✅ (전체 종목) |
| MACD 시그널 | ❌ | ✅ |
| Confluence 시그널 | ❌ | ✅ |
| 일일 시장 리포트 | ❌ | ✅ |
| 백테스트 성과 | ❌ | ✅ |

## 빠른 시작

```powershell
cd e:\signal_lab
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# .env 파일에 TELEGRAM_TOKEN, TELEGRAM_CHAT_ID 설정
```

### Chat ID 확인

```powershell
python telegram/get_chat_id.py
```

Telegram에서 봇에게 메시지를 보내면 Chat ID가 출력됩니다.

## 실행 모드

```powershell
# 스케줄러 모드 (매일 22:00 자동 실행 + 즉시 1회)
python main.py

# 1회만 실행
python main.py --once

# 백테스트 실행 (성과 DB 저장)
python main.py --backtest

# 구독/결제용 인터랙티브 Telegram 봇
python main.py --bot
```

## 수익화 운영 가이드

### 1. Telegram 봇 배포

```powershell
python main.py --bot
```

사용자가 `/start` → 무료 구독 자동 등록  
`/premium` → 요금 안내  
`/premium SIGNAL2026` → 프리미엄 코드로 활성화

### 2. 프리미엄 결제 흐름

1. 사용자가 `/premium` 으로 요금 확인
2. 결제 완료 후 초대 코드 전달 또는 관리자가 `/grant_premium CHAT_ID` 실행
3. 프리미엄 구독자에게 MACD/Confluence/일일 리포트 자동 발송

### 3. 시그널 파이프라인 (수익 핵심)

```powershell
python main.py
```

매일 자동으로:
1. Yahoo Finance에서 주가 수집
2. RSI / MACD / Confluence 시그널 생성
3. 구독 등급별 Telegram 발송
4. 프리미엄 구독자에게 일일 리포트 발송

### 4. 백테스트 (신뢰도/마케팅)

```powershell
python main.py --backtest
```

승률·평균수익률을 DB에 저장. 프리미엄 사용자가 `/backtest` 로 조회 가능.

## 환경 변수

`.env.example` 참고. 주요 설정:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `TELEGRAM_TOKEN` | BotFather 토큰 | (필수) |
| `TELEGRAM_CHAT_ID` | 관리자 Chat ID | (필수) |
| `ADMIN_CHAT_IDS` | 관리자 ID 목록 | TELEGRAM_CHAT_ID |
| `PREMIUM_CODES` | 프리미엄 초대 코드 | SIGNAL2026,PREMIUM |
| `TICKERS` | 전체 분석 종목 | SPY,QQQ,AAPL,... |
| `FREE_TICKERS` | 무료 종목 | SPY,QQQ,AAPL |
| `SCHEDULE_TIME` | 일일 실행 시간 | 22:00 |
| `PREMIUM_PRICE_KRW` | 표시용 월 요금 | 29000 |

## Telegram 명령어

| 명령 | 설명 |
|------|------|
| `/start` | 서비스 시작 + 무료 구독 |
| `/status` | 현재 RSI/MACD 상태 |
| `/signals` | 최근 시그널 |
| `/backtest` | 백테스트 성과 (프리미엄) |
| `/premium` | 프리미엄 안내 |
| `/premium 코드` | 프리미엄 활성화 |
| `/admin_stats` | 구독자 통계 (관리자) |
| `/grant_premium ID` | 프리미엄 부여 (관리자) |

## 테스트

```powershell
pip install pytest
pytest tests/ -v
```

## Windows 자동 실행 (Task Scheduler)

1. 작업 스케줄러 → 기본 작업 만들기
2. 트리거: 매일 22:00
3. 동작: `e:\signal_lab\venv\Scripts\python.exe e:\signal_lab\main.py --once`

봇은 별도로 상시 실행:

```powershell
python main.py --bot
```

## 프로젝트 구조

```
signal_lab/
├── main.py                 # 진입점 (스케줄러/파이프라인/백테스트)
├── config/settings.py      # 환경 설정
├── data/collector.py       # Yahoo Finance 데이터 수집
├── database/db.py          # SQLite (가격/시그널/구독자/백테스트)
├── signals/                # RSI, MACD, Confluence 시그널
├── backtest/backtester.py  # 백테스트 엔진
├── reports/daily_report.py # 일일 시장 리포트
├── subscription/manager.py # FREE/PREMIUM 구독 관리
├── telegram/
│   ├── bot.py              # 구독/결제 인터랙티브 봇
│   └── sender.py           # 등급별 시그널 발송
└── tests/                  # 단위 테스트
```

## 보안 주의

- `.env` 파일을 Git에 커밋하지 마세요
- Telegram 토큰이 로그에 노출된 경우 BotFather에서 **토큰 재발급** 권장
- 투자 손실 책임 고지 문구 포함 (일일 리포트에 자동 삽입)

## 면책

Signal Lab은 투자 정보 제공 서비스이며, 투자 손실에 대한 책임은 사용자에게 있습니다.
