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
    'BREAKOUT': 0.6,
    'MEAN_REV': 0.4
}

# 시간 청산 (캔들 개수, 5분봉 기준 288 = 24시간)
MAX_HOLD_CANDLES = 288

# =========================================================
# Breakout Strategy 개선 파라미터
# =========================================================

# 4단계 트레일링 스탑 설정 (v2.1 - 더 넓은 간격)
TRAILING_STOP_LEVELS = {
    'breakeven': {'profit_atr': 2.0, 'trail_atr': 0.0},   # 손익분기점 (2.0 ATR로 상향)
    'stage1': {'profit_atr': 3.5, 'trail_atr': 2.0},      # 기본 트레일링 (더 넓게)
    'stage2': {'profit_atr': 6.0, 'trail_atr': 1.5},      # 타이트 추격
    'stage3': {'profit_atr': 10.0, 'trail_atr': 1.0},     # 대형 수익 보호
}

# 부분 익절 설정 (Breakout) - 더 늦게 익절
BREAKOUT_PARTIAL_TP = {
    'tp1': {'profit_atr': 4.0, 'close_pct': 0.25},  # 4 ATR 도달: 25% 청산
    'tp2': {'profit_atr': 7.0, 'close_pct': 0.25},  # 7 ATR 도달: 추가 25% 청산
}

# 점수 기반 진입 시스템 (최소 점수) - 더 엄격하게
BREAKOUT_MIN_SCORE = 5

# 손절폭 ATR 배수 (v2.1 - 추세 추종에 맞게 확대)
BREAKOUT_SL_ATR_MULT = 2.5

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

# 시간 기반 조기 탈출
MEAN_REV_TIME_EXIT = {
    'tighten_candles': 144,   # 144봉 경과 시 손절폭 50% 축소
    'force_exit_candles': 216  # 216봉 경과 시 강제 청산
}

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

# 동시 포지션 관리
MAX_SAME_DIRECTION_POSITIONS = 2
CONCURRENT_POSITION_RISK_MULT = 0.7  # 동시 진입 시 리스크 축소

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
WALK_FORWARD_CONFIG = {
    'in_sample_ratio': 0.7,      # In-sample 비율 (70%) - 전략 검증용
    'out_sample_ratio': 0.3,     # Out-of-sample 비율 (30%) - 실제 테스트
    'min_window_candles': 5000,  # 최소 윈도우 크기 (캔들 수)
    'step_candles': 2500,        # 롤링 스텝 (캔들 수) - 비중첩 구간
    'anchored': False,           # True: 시작점 고정 (expanding window), False: 롤링
}
