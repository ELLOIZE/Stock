# BTC/USDT 다중 전략 백테스트 시스템

BTC/USDT 5분봉 데이터를 사용한 다중 전략 백테스트 시스템입니다.

> **v3.0 업데이트**: 레짐 기반 전략 시스템, Momentum 전략 추가, Walk-Forward 백테스트, 슬리피지 모델
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
        └── Walk-Forward 백테스트

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
| Momentum 차트 | `output/charts/result_MOMENTUM.html` | 진입/청산 시각화 |

---

## 시장 레짐 필터 (v3.0 신규)

시장 상태를 4가지 레짐으로 분류하여 전략별 진입을 제어합니다.

### 레짐 분류 기준

| 레짐 | 조건 |
|------|------|
| **TREND_UP** | EMA21 > EMA50 > EMA200, ADX > 25, price > EMA50 |
| **TREND_DOWN** | EMA21 < EMA50 < EMA200, ADX > 25, price < EMA50 |
| **RANGING** | ADX < 20 |
| **WEAK_TREND** | 위 조건에 해당하지 않는 경우 |

### 전략별 레짐 게이트

| 전략 | 허용 레짐 |
|------|-----------|
| Breakout | TREND_UP only |
| Mean Reversion | RANGING, WEAK_TREND |
| Momentum | TREND_UP, WEAK_TREND |

### 포트폴리오 레짐 보호

- **TREND_DOWN** 레짐 시 최대 1개 포지션으로 제한

---

## 전략 설명

### 1. Breakout Strategy (추세 추종) - 40%

**목표**: 저항선 돌파 후 추세 추종으로 큰 수익 추구

**레짐 게이트**: TREND_UP only

| 항목 | v2 (기존) | v3 (개선) |
|------|-----------|-----------|
| **비중** | 60% | **40%** |
| **레짐 필터** | 없음 | **TREND_UP only** |
| **최소 점수** | 4점 | **2점** |
| **RSI 범위** | 50-70 | **45-70** |
| **트레일링** | 1.5/3/5/8 ATR | **2.0/4.0/7.0/12.0 ATR** |
| **부분 익절** | 3ATR(25%), 5ATR(25%) | **4ATR(25%), 7ATR(25%)** |
| **손절** | 1.5 ATR | **3.0 ATR** |

**진입 조건 (v3)**:
```
필수: 저항선 2봉 돌파 + 종가 > EMA200
점수: 거래량≥2x(+1), ADX>35(+1), 3+연속 양봉(+1), RSI 45-70(+1)
→ 2점 이상 시 진입
```

**4단계 트레일링 스탑**:
| 수익 | 스탑 위치 |
|------|-----------|
| 2.0 ATR | 진입가 (손익분기) |
| 4.0 ATR | high - 2.5 ATR |
| 7.0 ATR | high - 2.0 ATR |
| 12.0 ATR | high - 1.5 ATR |

**부분 익절**:
| 수익 | 청산 비율 |
|------|-----------|
| 4 ATR | 25% |
| 7 ATR | 25% |

---

### 2. Mean Reversion Strategy (역추세) - 30%

**목표**: 과매도 구간에서 반등 포착

**레짐 게이트**: RANGING 또는 WEAK_TREND

| 항목 | v2 (기존) | v3 (개선) |
|------|-----------|-----------|
| **비중** | 40% | **30%** |
| **레짐 필터** | 없음 | **RANGING, WEAK_TREND** |
| **RSI** | < 40 | **< 30** |
| **ADX** | < 30 | **< 25** |
| **BB 폭** | 제한 없음 | **≥ 0.5%** |
| **EMA200** | 제한 없음 | **가격 ±3% 이내** |
| **거래량** | 제한 없음 | **≥ 1.5x** |
| **익절** | 3단계 (33/33/34%) | **2단계 (BB center 50%, BB upper 50%)** |
| **시간 청산** | 12h 축소, 18h 강제 | **제거됨** |
| **손절** | 1.5 ATR | **2.0 ATR (min 0.4%)** |

**진입 조건 (v3)**:
```
1. BB 하단 터치 + RSI < 30 + ADX < 25
2. BB 폭 ≥ 0.5%
3. 가격이 EMA200 ±3% 이내
4. 거래량 ≥ 1.5x 평균
5. 다음 봉이 양봉(close > open)이면 진입
→ 반등 확인 후 진입으로 "떨어지는 칼날" 방지
```

**2단계 익절**:
| 목표 | 청산 비율 |
|------|-----------|
| BB 중심선 | 50% |
| BB 상단 | 50% |

**부분 익절 후 보호**:
- 손절을 진입가(손익분기)로 이동
- 1.5 ATR 되돌림 시 보호 청산

---

### 3. Momentum Strategy (RSI 모멘텀) - 30% (v3.0 신규)

**목표**: RSI 모멘텀을 활용한 추세 초기 진입

**레짐 게이트**: TREND_UP 또는 WEAK_TREND

**진입 조건**:
```
1. RSI가 55 이상으로 상향 돌파
2. RSI 기울기 양수 (최근 5봉)
3. EMA21 > EMA50
4. 가격 > EMA50
5. 거래량 ≥ 1.5x 평균
6. 최근 5봉 중 3개 이상 양봉
```

**RSI 기반 청산**:
| 조건 | 동작 |
|------|------|
| RSI 75+ 도달 후 10pt 하락 | 50% 부분 청산 |
| 부분 청산 후 RSI < 65 | 나머지 전량 청산 |
| RSI < 30 AND 손실 중 | 전량 즉시 청산 |

**2단계 트레일링 스탑**:
| 수익 | 스탑 위치 |
|------|-----------|
| 3 ATR | high - 1.5 ATR |
| 2 ATR | 진입가 (손익분기) |

**손절**: 2.5 ATR (최소 0.5%)

---

## 리스크 관리

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

### 슬리피지 모델 (v3.0 신규)

| 항목 | 값 |
|------|-----|
| 기본 슬리피지 | ATR의 5% |
| 최소 슬리피지 | 0.01% |
| 최대 슬리피지 | 0.1% |

### 레짐 기반 포지션 보호 (v3.0 신규)

- **TREND_DOWN** 레짐 감지 시 최대 1개 포지션으로 제한
- 하락 추세에서의 과도한 노출 방지

---

## Walk-Forward 백테스트

`multi_period_backtest.py`는 Walk-Forward 방법론을 사용합니다.

### 방법론

| 항목 | 설정 |
|------|------|
| In-sample 비율 | 70% |
| Out-of-sample 비율 | 30% |
| 최소 윈도우 | 5,000 캔들 |
| 스텝 크기 | 1,500 캔들 |
| 모드 | Rolling 또는 Anchored |

**Rolling 모드**: 고정 크기 윈도우가 이동하며 최신 데이터에 적응
**Anchored 모드**: 시작점 고정, 데이터가 누적되며 학습

### 실행
```bash
python multi_period_backtest.py
```

---

## 설정 변경

`config/settings.py` 파일에서 조정 가능:

### 기본 설정
```python
INITIAL_CAPITAL = 10000.0      # 초기 자본
RISK_PER_TRADE = 0.01          # 기본 리스크 (1%)
FEE_RATE = 0.0004              # 수수료 (0.04%)
```

### 전략 비중
```python
STRATEGY_WEIGHTS = {
    'BREAKOUT': 0.4,    # 40%
    'MEAN_REV': 0.3,    # 30%
    'MOMENTUM': 0.3,    # 30%
}
```

### Breakout 파라미터
```python
BREAKOUT_MIN_SCORE = 2                  # 최소 진입 점수
BREAKOUT_SL_ATR_MULT = 3.0             # 손절 ATR 배수
BREAKOUT_TRAIL_STAGES = [2.0, 4.0, 7.0, 12.0]  # 트레일링 단계
BREAKOUT_PARTIAL_EXITS = {4.0: 0.25, 7.0: 0.25} # 부분 익절
```

### Mean Reversion 파라미터
```python
MEAN_REV_SL_ATR_MULT = 2.0            # 손절 ATR 배수
MEAN_REV_SL_MIN_PCT = 0.004           # 최소 손절 0.4%
MEAN_REV_REQUIRE_BULLISH_CONFIRM = True # 양봉 확인 활성화
```

### Momentum 파라미터
```python
MOMENTUM_RSI_ENTRY = 55               # RSI 진입 기준
MOMENTUM_RSI_SLOPE_PERIOD = 5         # RSI 기울기 기간
MOMENTUM_SL_ATR_MULT = 2.5            # 손절 ATR 배수
MOMENTUM_SL_MIN_PCT = 0.005           # 최소 손절 0.5%
```

### Walk-Forward 설정
```python
WF_MIN_WINDOW = 5000                   # 최소 윈도우 크기
WF_STEP_SIZE = 1500                    # 스텝 크기
WF_IS_RATIO = 0.7                      # In-sample 비율
WF_MODE = 'rolling'                    # rolling 또는 anchored
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
총 매매 횟수: 75회
통합 승률: 58.33%
수익 팩터: 1.45
샤프 비율: 1.82
소르티노 비율: 2.15
최대 낙폭: -3.21%

--- 전략별 성과 ---
                count      sum     mean
type
BREAKOUT           30   420.00   14.00
MEAN_REV           22   280.00   12.73
MOMENTUM           23   300.00   13.04
```

### 청산 사유 코드

| 코드 | 의미 |
|------|------|
| `SL` | 손절 |
| `Trailing_Win` | 트레일링 스탑 수익 청산 |
| `TP_Mean` | Mean Reversion 목표가 도달 |
| `PARTIAL_*` | 부분 익절 |
| `TP_MOM_FADE` | Momentum RSI 피크 후 하락 청산 |
| `EXIT_MOM_LOST` | Momentum RSI 모멘텀 상실 청산 |
| `EXIT_MR_RETRACE` | Mean Reversion 되돌림 보호 청산 |
| `TIME` | 시간 초과 청산 |

---

## 폴더 구조

```
military_service_0119/
│
├── config/
│   └── settings.py          # 모든 설정값 (v3 파라미터 포함)
│
├── data/
│   ├── fetcher.py           # Binance API 데이터 수집
│   └── features.py          # 기술적 지표 계산
│
├── strategies/
│   ├── base.py              # 전략 추상 클래스
│   ├── breakout.py          # Breakout 전략 (v3 개선)
│   ├── mean_reversion.py    # Mean Reversion 전략 (v3 개선)
│   └── momentum.py          # Momentum 전략 (v3 신규)
│
├── engine/
│   └── portfolio.py         # 포트폴리오 매니저 (v3 개선)
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

*v3.0 - 2026-01-29 업데이트*
