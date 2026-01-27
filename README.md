# BTC/USDT 다중 전략 백테스트 시스템

BTC/USDT 5분봉 데이터를 사용한 다중 전략 백테스트 시스템입니다.

> **v2.0 업데이트**: 점수 기반 진입, 4단계 트레일링, 부분 익절, 동적 리스크 관리 추가
> 상세 변경 내역: [CHANGELOG_v2.md](./CHANGELOG_v2.md)

---

## 실행 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│                        실행 순서                                  │
└─────────────────────────────────────────────────────────────────┘

[1단계] 환경 설정
    │
    ├── pip install -r requirements.txt
    │
    └── .env 파일 생성 (API 키 설정)

        ↓

[2단계] 데이터 수집
    │
    └── python fetch_data.py
        │
        └── 출력: test.json (약 300,000개 캔들)

        ↓

[3단계] 백테스트 실행 (택 1)
    │
    ├── [옵션 A] python main.py
    │   └── 단일 기간 백테스트 (전체 데이터)
    │
    └── [옵션 B] python multi_period_backtest.py
        └── Walk-Forward 백테스트 (100개 기간)

        ↓

[4단계] 결과 확인
    │
    ├── 콘솔: 통계 출력
    ├── output/reports/: 엑셀, CSV 리포트
    └── output/charts/: HTML 인터랙티브 차트
```

---

## 빠른 시작

### 1단계: 환경 설정

```bash
# 패키지 설치
pip install -r requirements.txt

# API 키 설정 (.env 파일 생성)
echo "BINANCE_API_KEY=your_api_key" > .env
echo "BINANCE_API_SECRET=your_api_secret" >> .env
```

### 2단계: 데이터 수집

```bash
python fetch_data.py
```

**출력:**
- `test.json` - 약 300,000개 캔들 + 저항선 레벨

### 3단계: 백테스트 실행

```bash
# 옵션 A: 단일 기간 (빠른 테스트)
python main.py

# 옵션 B: Walk-Forward (권장, 신뢰성 높음)
python multi_period_backtest.py
```

### 4단계: 결과 확인

| 출력 파일 | 위치 | 내용 |
|-----------|------|------|
| 매매 기록 | `output/reports/trades_result.xlsx` | 모든 거래 상세 |
| 자산 곡선 | `output/reports/equity_curve.csv` | 시간별 자산 변화 |
| Breakout 차트 | `output/charts/result_BREAKOUT.html` | 진입/청산 시각화 |
| Mean Rev 차트 | `output/charts/result_MEAN_REV.html` | 진입/청산 시각화 |

---

## 전략 설명

### 1. Breakout Strategy (추세 추종) - 60%

**목표**: 저항선 돌파 후 추세 추종으로 큰 수익 추구

| 항목 | v1 (기존) | v2 (개선) |
|------|-----------|-----------|
| **진입** | 6개 조건 모두 충족 | 필수 2개 + 점수 4점 이상 |
| **트레일링** | 2단계 | **4단계** (손익분기점 보호 추가) |
| **익절** | 없음 | **부분 익절** (3ATR: 25%, 5ATR: 25%) |

**진입 조건 (v2)**:
```
필수: 저항선 2봉 돌파 + 종가 > EMA200
점수: RSI>50(+1), 거래량(+1), ADX>15(+1), ADX>25(+1), BB확장(+1), RSI 50-70(+1)
→ 4점 이상 시 진입
```

**4단계 트레일링 스탑**:
| 수익 | 스탑 위치 |
|------|-----------|
| 1.5 ATR | 진입가 (손익분기) |
| 3 ATR | high - 1.8 ATR |
| 5 ATR | high - 1.2 ATR |
| 8 ATR | high - 0.8 ATR |

---

### 2. Mean Reversion Strategy (역추세) - 40%

**목표**: 과매도 구간에서 반등 포착

| 항목 | v1 (기존) | v2 (개선) |
|------|-----------|-----------|
| **진입** | BB 하단 터치 즉시 | **양봉 확인 후** 진입 |
| **익절** | 중심선 100% 청산 | **다단계** (30%→60%→100%) |
| **시간 관리** | 24시간 강제 청산 | **조기 탈출** (12h 축소, 18h 청산) |

**진입 조건 (v2)**:
```
1. BB 하단 터치 + RSI < 40 + ADX < 30
2. 다음 봉이 양봉(close > open)이면 진입
→ 반등 확인 후 진입으로 "떨어지는 칼날" 방지
```

**다단계 익절**:
| BB 진행률 | 청산 비율 |
|-----------|-----------|
| 30% | 33% |
| 60% | 33% |
| 100% (중심선) | 34% |

---

## 리스크 관리 (v2 신규)

### 동적 포지션 사이징

| 시장 변동성 (ATR/가격) | 거래당 리스크 |
|------------------------|---------------|
| < 1% (낮음) | 1.5% |
| 1-2% (중간) | 1.0% |
| > 2% (높음) | 0.7% |

### 드로우다운 기반 자동 조절

| 일일 DD | 조치 |
|---------|------|
| < 2% | 정상 거래 |
| 2-4% | 리스크 30% 축소 |
| 4-6% | 리스크 50% 축소 + 신규 진입 제한 |
| > 6% | **당일 거래 중단** |

### 동시 포지션 제한

- 최대 2개 포지션 동시 보유
- 2개째 진입 시 각 리스크 30% 축소

---

## 설정 변경

`config/settings.py` 파일에서 조정 가능:

### 기본 설정
```python
INITIAL_CAPITAL = 10000.0      # 초기 자본
RISK_PER_TRADE = 0.01          # 기본 리스크 (1%)
FEE_RATE = 0.0004              # 수수료 (0.04%)
MAX_HOLD_CANDLES = 288         # 최대 보유 (24시간)
```

### 전략 파라미터
```python
BREAKOUT_MIN_SCORE = 4         # Breakout 최소 진입 점수
MEAN_REV_REQUIRE_BULLISH_CONFIRM = True  # 양봉 확인 활성화
```

### 리스크 파라미터
```python
VOLATILITY_RISK_TIERS = {...}  # 변동성별 리스크
DRAWDOWN_RISK_TIERS = {...}    # DD별 리스크 조정
MAX_SAME_DIRECTION_POSITIONS = 2  # 최대 동시 포지션
```

전체 파라미터 설명: [CHANGELOG_v2.md](./CHANGELOG_v2.md#6-설정-파라미터-레퍼런스)

---

## 출력 결과 예시

### 콘솔 출력
```
========== [포트폴리오 통합 결과] ==========
최종 자산: $10,850.00 (+8.50%)
총 매매 횟수: 52회
통합 승률: 58.33%
수익 팩터: 1.45
샤프 비율: 1.82
최대 낙폭: -3.21%

--- 전략별 성과 ---
                count      sum     mean
type
BREAKOUT           32   520.00   16.25
MEAN_REV           20   330.00   16.50
```

### 청산 사유 코드

| 코드 | 의미 |
|------|------|
| `SL` | 손절 |
| `Trailing_Win` | 트레일링 스탑 수익 청산 |
| `TP_Mean` | Mean Reversion 목표가 도달 |
| `PARTIAL_*` | 부분 익절 (신규) |
| `TIME` | 시간 초과 청산 |
| `TIME_EARLY` | 조기 시간 청산 (신규) |

---

## 폴더 구조

```
military_service_0119/
│
├── config/
│   └── settings.py          # 모든 설정값 (v2 파라미터 포함)
│
├── data/
│   ├── fetcher.py           # Binance API 데이터 수집
│   └── features.py          # 기술적 지표 계산
│
├── strategies/
│   ├── base.py              # 전략 추상 클래스
│   ├── breakout.py          # Breakout 전략 (v2 개선)
│   └── mean_reversion.py    # Mean Reversion 전략 (v2 개선)
│
├── engine/
│   └── portfolio.py         # 포트폴리오 매니저 (v2 개선)
│
├── analysis/
│   ├── stats.py             # 통계 계산
│   └── visualizer.py        # 차트 생성
│
├── utils/
│   └── helpers.py           # 유틸리티 함수
│
├── output/
│   ├── charts/              # HTML 차트
│   └── reports/             # Excel, CSV 리포트
│
├── main.py                  # 단일 백테스트 실행
├── multi_period_backtest.py # Walk-Forward 백테스트
├── fetch_data.py            # 데이터 수집 스크립트
│
├── CHANGELOG_v2.md          # v2 상세 변경 내역
├── CLAUDE.md                # Claude Code 가이드
└── README.md                # 이 문서
```

---

## 문제 해결

### API 키 오류
```
BINANCE_API_KEY and BINANCE_API_SECRET environment variables are required.
```
→ `.env` 파일 생성 또는 환경 변수 설정

### 데이터 파일 없음
```
test.json 파일이 없습니다. fetch_data.py를 먼저 실행하세요.
```
→ `python fetch_data.py` 실행

### 매매 기록 없음
```
매매 기록이 없어 리포트를 생성하지 않습니다.
```
→ 데이터 기간이 너무 짧거나 진입 조건이 충족되지 않음. 더 많은 데이터 수집 필요.

---

## 라이선스

개인 학습 및 연구 목적으로 작성되었습니다.

---

*v2.0 - 2026-01-27 업데이트*
