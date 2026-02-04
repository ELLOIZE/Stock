# =========================================================
# 설정값 중앙 관리
# =========================================================

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if exists)
load_dotenv()

# API 키 설정 (환경 변수에서 로드)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

def validate_api_credentials():
    """API 키 유효성 검사 (데이터 수집 시에만 호출)"""
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise ValueError(
            "BINANCE_API_KEY and BINANCE_API_SECRET environment variables are required.\n"
            "Set them via:\n"
            "  - .env file in project root\n"
            "  - System environment variables\n"
            "  - PowerShell: $env:BINANCE_API_KEY='your_key'"
        )

# 트레이딩 설정
INITIAL_CAPITAL = 10000.0
FEE_RATE = 0.0004  # 0.04% (Binance taker fee)
RISK_PER_TRADE = 0.01  # 1% 리스크

# 슬리피지 설정 (ATR 기반 비율)
SLIPPAGE_ATR_MULT = 0.05  # ATR의 5%를 슬리피지로 적용
SLIPPAGE_MIN_PCT = 0.0001  # 최소 슬리피지 0.01%
SLIPPAGE_MAX_PCT = 0.001   # 최대 슬리피지 0.1%

# 데이터 설정
TIMEFRAME = '5m'
DEFAULT_SYMBOL = "BTC/USDT"
MAX_CANDLES = 300000

# 지표 설정
EMA_PERIODS = [21, 50, 200]
ATR_PERIOD = 14
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2

# 전략별 가중치
STRATEGY_WEIGHTS = {
    'BREAKOUT': 0.2,
    'MEAN_REV': 0.15,
    'MOMENTUM': 0.15,
    'SHORT_BREAKOUT': 0.2,
    'SHORT_MEAN_REV': 0.15,
    'SHORT_MOMENTUM': 0.15,
}

# =========================================================
# Breakout Strategy 개선 파라미터
# =========================================================

# 4단계 트레일링 스탑 설정 (v4 - 빠른 보호)
TRAILING_STOP_LEVELS = {
    'breakeven': {'profit_atr': 1.5, 'trail_atr': 0.0},   # 손익분기점 (빠르게)
    'stage1': {'profit_atr': 3.5, 'trail_atr': 2.0},      # 기본 트레일링 (넉넉)
    'stage2': {'profit_atr': 6.0, 'trail_atr': 1.5},      # 중간 추격
    'stage3': {'profit_atr': 9.0, 'trail_atr': 1.0},      # 대형 수익 보호
}

# 부분 익절 설정 (Breakout) - 수익 확보 균형
BREAKOUT_PARTIAL_TP = {
    'tp1': {'profit_atr': 3.5, 'close_pct': 0.25},  # 3.5 ATR 도달: 25% 청산
    'tp2': {'profit_atr': 6.0, 'close_pct': 0.30},  # 6 ATR 도달: 추가 30% 청산
}

# 점수 기반 진입 시스템 (최소 점수)
BREAKOUT_MIN_SCORE = 1

# 저항선 돌파 마진 (0.5% → 0.15%)
BREAKOUT_RES_MARGIN_PCT = 0.0015

# RSI 진입 범위 (45-70 → 40-80)
BREAKOUT_RSI_MIN = 40
BREAKOUT_RSI_MAX = 80

# 손절폭 ATR 배수 (축소)
BREAKOUT_SL_ATR_MULT = 2.0

# Enhanced Regime Detection 활용 (v5.0)
BREAKOUT_USE_ENHANCED_REGIME = True  # False로 설정 시 v4.0 동작
BREAKOUT_PHASE_SCORES = {
    'EARLY_BULL': 2,   # 상승 초기: +2점 보너스
    'MATURE_BULL': 1,  # 상승 성숙기: +1점 보너스
    'LATE_BULL': -1,   # 상승 후반: -1점 패널티 (반전 위험)
}
BREAKOUT_REQUIRE_BULLISH_MOMENTUM = False  # True면 BEARISH 모멘텀 시 진입 불가
BREAKOUT_MOMENTUM_BULLISH_BONUS = 1  # BULLISH 모멘텀 보너스 점수
BREAKOUT_VOL_SL_MULT = {
    'HIGH': 1.3,    # 고변동성: SL 30% 확대
    'NORMAL': 1.0,  # 보통: 변경 없음
    'LOW': 0.8,     # 저변동성: SL 20% 축소
}
BREAKOUT_VOLUME_HIGH_BONUS = 1  # HIGH 거래량 보너스 점수
BREAKOUT_LATE_PHASE_TRAIL_MULT = 0.7  # LATE_BULL 시 트레일링 거리 30% 축소

# =========================================================
# Mean Reversion Strategy 개선 파라미터
# =========================================================

# 양봉 확인 필요 여부
MEAN_REV_REQUIRE_BULLISH_CONFIRM = True

# 다단계 익절 설정
MEAN_REV_PARTIAL_TP = {
    'tp1': {'bb_progress': 0.30, 'close_pct': 0.33},  # 30% 지점: 33% 청산
    'tp2': {'bb_progress': 0.60, 'close_pct': 0.33},  # 60% 지점: 33% 청산
    'tp3': {'bb_progress': 1.00, 'close_pct': 0.34},  # 중심선: 나머지 청산
}

# Mean Reversion 손절 설정
MEAN_REV_SL_ATR_MULT = 2.0      # 손절 ATR 배수 (기존 하드코딩 3.0에서 축소)
MEAN_REV_SL_MIN_PCT = 0.004     # 최소 손절 비율 (기존 하드코딩 0.006에서 축소)

# Enhanced Regime Detection 활용 (v4.0)
MEAN_REV_USE_ENHANCED_REGIME = True  # False로 설정 시 v3.0 동작

# Phase-based scoring (mean reversion prefers ranging phases)
MEAN_REV_PHASE_SCORES = {
    'CONSOLIDATION': 2,      # 안정적 횡보: +2점 (최적)
    'VOLATILE_RANGE': -1,    # 불안정 횡보: -1점 (반전 위험)
    'LATE_BEAR': 1,          # 하락 후반: +1점 (반등 가능성)
    'NEUTRAL': 0,            # 기본
}

# Momentum scoring (BEARISH at oversold = reversal imminent)
MEAN_REV_MOMENTUM_BEARISH_BONUS = 1  # BEARISH 모멘텀 + 과매도 = +1점 (캐피튤레이션)
MEAN_REV_REQUIRE_NOT_BULLISH = False  # True면 BULLISH 모멘텀 시 진입 불가

# Volatility-adaptive stop loss
MEAN_REV_VOL_SL_MULT = {
    'HIGH': 1.4,    # 고변동성: SL 40% 확대 (휩쏘 방지)
    'NORMAL': 1.0,  # 보통: 변경 없음
    'LOW': 0.7,     # 저변동성: SL 30% 축소 (타이트한 관리)
}

# Volume-based entry quality (capitulation detection)
MEAN_REV_VOLUME_HIGH_BONUS = 1  # HIGH 거래량 + 과매도 = 캐피튤레이션 신호

# Minimum score for entry (enhanced mode only)
MEAN_REV_MIN_SCORE = 1  # 최소 점수 기준

# Phase-based exit tightening
MEAN_REV_VOLATILE_PHASE_PROTECT_ATR = 1.0  # VOLATILE_RANGE에서 보호 청산 ATR (기본 1.5 → 1.0)

# =========================================================
# Momentum Strategy 파라미터
# =========================================================

MOM_RSI_ENTRY = 60          # RSI 진입 기준선 (v4 유지)
MOM_RSI_EXIT_BELOW = 45     # RSI 이 아래로 하락 시 청산 (v4 유지)
MOM_RSI_OVERBOUGHT = 75     # 과매수 청산 기준
MOM_RSI_SLOPE_PERIOD = 3    # RSI 기울기 계산 기간
MOM_ADX_MIN = 30            # 최소 ADX (v4 유지)
MOM_VOL_MULT = 2.0          # 최소 거래량 배수 (v4 유지)
MOM_MIN_BULLISH = 3         # 최근 5봉 중 최소 양봉 수
MOM_SL_ATR_MULT = 2.0       # 손절 ATR 배수
MOM_SL_MIN_PCT = 0.005      # 최소 손절 비율
MOM_TIME_EXIT_CANDLES = 30  # 시간 기반 청산 (20→30 완화)
MOM_TIME_EXIT_MIN_ATR = 0.5 # 시간 청산 최소 수익 ATR (1.0→0.5 완화)
MOM_PARTIAL_1_PCT = 0.30    # RSI 부분 익절 비율
MOM_PARTIAL_2_RSI = 80      # 2차 익절 RSI 기준
MOM_PARTIAL_2_DROP = 15     # 2차 익절 RSI 하락폭

# 트레일링 스탑 파라미터 (더 빨리 수익 보호)
MOM_TRAIL_BE_ATR = 1.5      # 손익분기점 이동 기준 ATR
MOM_TRAIL_S1_ATR = 2.5      # Stage1 트레일링 진입 ATR
MOM_TRAIL_S1_DIST = 1.0     # Stage1 트레일링 거리
MOM_TRAIL_S2_ATR = 4.0      # Stage2 트레일링 진입 ATR
MOM_TRAIL_S2_DIST = 0.8     # Stage2 트레일링 거리

# 조기 부분 익절 파라미터
MOM_PARTIAL_EARLY_ATR = 2.0 # 조기 부분 익절 기준 ATR
MOM_PARTIAL_EARLY_PCT = 0.25  # 조기 부분 익절 비율

# =========================================================
# SHORT 전략 전용 파라미터
# =========================================================

# SHORT Breakout 파라미터
SHORT_BREAKOUT_MIN_SCORE = 5           # 점수 더 엄격하게 (3 → 5)
SHORT_BREAKOUT_SL_ATR_MULT = 3.5       # SL 더 넓힘 (3.0 → 3.5)
SHORT_BREAKOUT_RSI_MIN = 10            # RSI 하한 더 완화 (15 → 10)
SHORT_BREAKOUT_RSI_MAX = 55            # RSI 상한 더 타이트 (65 → 55)

# SHORT Mean Reversion 파라미터
SHORT_MR_RSI_THRESHOLD = 72            # RSI 더 엄격 (68 → 72, 더 확실한 과매수만)
SHORT_MR_SL_ATR_MULT = 3.5             # SL 넓힘 (3.0 → 3.5)
SHORT_MR_SL_MIN_PCT = 0.008            # 최소 SL 넓힘 (0.006 → 0.008)
SHORT_MR_REQUIRE_BEARISH = True         # 음봉 확인 필수 (LONG: 양봉 필수)
SHORT_MR_EMA200_DIST = 1.06            # EMA200 거리 더 완화 (1.04 → 1.06)
SHORT_MR_PROTECTION_ATR = 2.5          # 보호 청산 여유 (2.0 → 2.5)

# SHORT Momentum 파라미터
SHORT_MOM_RSI_ENTRY = 30               # RSI 더 낮아야 진입 (40 → 30, 더 확실한 하락)
SHORT_MOM_RSI_EXIT = 62                # EXIT_MOM_LOST 더 완화 (58 → 62, 더 오래 홀딩)
SHORT_MOM_SL_ATR_MULT = 3.5            # SL 대폭 넓힘 (2.8 → 3.5)
SHORT_MOM_SL_MIN_PCT = 0.008           # 최소 SL 넓힘 (0.006 → 0.008)
SHORT_MOM_ADX_MIN = 35                 # ADX 더 엄격 (28 → 35, 더 강한 추세만)
SHORT_MOM_VOL_MULT = 2.5               # 거래량 더 엄격 (1.8 → 2.5)
SHORT_MOM_TIME_EXIT_CANDLES = 50        # 시간 청산 더 완화 (40 → 50)

# =========================================================
# 리스크 관리 개선 파라미터
# =========================================================

# 동적 포지션 사이징 (변동성 기반)
VOLATILITY_RISK_TIERS = {
    'low': {'max_atr_pct': 0.01, 'risk': 0.015},    # ATR/가격 < 1%: 1.5% 리스크
    'medium': {'max_atr_pct': 0.02, 'risk': 0.01},  # ATR/가격 1-2%: 1.0% 리스크
    'high': {'max_atr_pct': float('inf'), 'risk': 0.007},  # ATR/가격 > 2%: 0.7% 리스크
}

# 드로우다운 기반 리스크 조정
DRAWDOWN_RISK_TIERS = {
    'normal': {'max_dd': 0.02, 'risk_mult': 1.0, 'allow_entry': True},   # DD < 2%
    'caution': {'max_dd': 0.04, 'risk_mult': 0.7, 'allow_entry': True},  # DD 2-4%
    'warning': {'max_dd': 0.06, 'risk_mult': 0.5, 'allow_entry': False}, # DD 4-6%
    'halt': {'max_dd': float('inf'), 'risk_mult': 0.0, 'allow_entry': False},  # DD > 6%
}

# 동시 포지션 관리 (방향별 독립 적용: LONG 최대 2, SHORT 최대 2)
MAX_SAME_DIRECTION_POSITIONS = 2
CONCURRENT_POSITION_RISK_MULT = 0.7  # 동시 진입 시 리스크 축소

# 숏 전략 활성화 토글
ENABLE_SHORT = True

# 파일 경로
DATA_FILE = "test.json"
OUTPUT_DIR = "output"

# 멀티 기간 백테스트 설정
NUM_PERIODS = 100           # 테스트할 랜덤 기간 개수
BACKTEST_WINDOW_SIZE = 5000  # 각 기간의 캔들 수 (~17일 for 5m)
RANDOM_SEED = 42             # 재현성을 위한 랜덤 시드

# =========================================================
# Walk-Forward 테스트 설정
# =========================================================
# =========================================================
# 시장 레짐 필터 설정
# =========================================================
REGIME_ADX_TREND = 25       # ADX 이 값 이상 = 추세 시장
REGIME_ADX_RANGE = 20       # ADX 이 값 이하 = 횡보 시장

# Enhanced regime momentum thresholds
REGIME_RSI_BULLISH = 55      # Above = bullish momentum
REGIME_RSI_BEARISH = 45      # Below = bearish momentum
REGIME_RSI_OVERBOUGHT = 70   # Overbought for late phase
REGIME_RSI_OVERSOLD = 30     # Oversold for late phase

# Volatility classification (BB width percentile)
REGIME_BB_LOW_PCTL = 20      # Below = low volatility
REGIME_BB_HIGH_PCTL = 80     # Above = high volatility
REGIME_BB_LOOKBACK = 100     # Lookback for percentile calc

# Volume classification
REGIME_VOL_HIGH_MULT = 1.5   # Above = high volume
REGIME_VOL_LOW_MULT = 0.7    # Below = low volume

# Early trend detection (less strict than full alignment)
REGIME_EARLY_TREND_RSI_MIN = 50   # RSI must be at least this for EARLY_BULL
REGIME_EARLY_TREND_ADX_MIN = 18   # ADX must be at least this for early trend

WALK_FORWARD_CONFIG = {
    'in_sample_ratio': 0.7,      # In-sample 비율 (70%) - 전략 검증용
    'out_sample_ratio': 0.3,     # Out-of-sample 비율 (30%) - 실제 테스트
    'min_window_candles': 5000,  # 최소 윈도우 크기 (~17일)
    'step_candles': 1500,        # 롤링 스텝 (~5일)
    'anchored': False,           # True: 시작점 고정 (expanding window), False: 롤링
}
