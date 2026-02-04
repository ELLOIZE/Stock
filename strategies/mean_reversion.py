# =========================================================
# 역추세 전략 (Mean Reversion Strategy) - v3.0 레짐 기반
# =========================================================

from strategies.base import Strategy
from config.settings import (
    MEAN_REV_REQUIRE_BULLISH_CONFIRM,
    MEAN_REV_SL_ATR_MULT,
    MEAN_REV_SL_MIN_PCT,
    # Enhanced Regime Detection (v4.0)
    MEAN_REV_USE_ENHANCED_REGIME,
    MEAN_REV_PHASE_SCORES,
    MEAN_REV_MOMENTUM_BEARISH_BONUS,
    MEAN_REV_REQUIRE_NOT_BULLISH,
    MEAN_REV_VOL_SL_MULT,
    MEAN_REV_VOLUME_HIGH_BONUS,
    MEAN_REV_MIN_SCORE,
    MEAN_REV_VOLATILE_PHASE_PROTECT_ATR,
)


class MeanReversionStrategy(Strategy):
    """
    역추세 전략 v4.0 - Enhanced Regime Detection

    v4.0 Changes:
    - Phase-based scoring (CONSOLIDATION preferred)
    - Momentum scoring (BEARISH at oversold = capitulation)
    - Volume scoring (HIGH volume at oversold)
    - Volatility-adaptive stop loss
    - Phase-based exit tightening

    진입 조건:
    - 레짐: RANGING 또는 WEAK_TREND만
    - 볼린저 밴드 하단 이탈 (과매도)
    - RSI < 30 (강한 과매도)
    - ADX < 25 (강한 추세 아님)
    - 밴드폭 0.5% 이상
    - 가격 > EMA200 * 0.97 (3% 이내)
    - 양봉 확인 (설정에 따라)
    - 거래량 >= 1.5배 평균

    청산:
    - BB 중심선 도달 → 50% 부분 익절
    - BB 상단 도달 → 나머지 청산
    - 가격 하락 시 보호 청산
    """

    def __init__(self, name="MEAN_REV"):
        super().__init__(name)
        self._partial_taken = {}

    def _calculate_entry_score(self, row):
        """
        Enhanced regime scoring for entry quality (v4.0)
        Following BreakoutStrategy pattern: calculate and return score immediately.

        Returns:
            tuple: (should_block_entry, score)
        """
        score = 0

        # Phase-based scoring
        phase = row.get('regime_phase', 'NEUTRAL')
        phase_score = MEAN_REV_PHASE_SCORES.get(phase, 0)
        score += phase_score

        # Momentum scoring (BEARISH at oversold = capitulation)
        momentum = row.get('regime_momentum', 'NEUTRAL')
        if MEAN_REV_REQUIRE_NOT_BULLISH and momentum == 'BULLISH':
            return True, 0  # Block: already bouncing
        if momentum == 'BEARISH':
            score += MEAN_REV_MOMENTUM_BEARISH_BONUS

        # Volume scoring (HIGH volume at oversold = capitulation)
        regime_volume = row.get('regime_volume', 'NORMAL')
        if regime_volume == 'HIGH':
            score += MEAN_REV_VOLUME_HIGH_BONUS

        return False, score

    def check_entry(self, df, i):
        if i < 200:
            return False

        row = df.iloc[i]

        # 레짐 게이트: RANGING 또는 WEAK_TREND만
        regime = row.get('regime', '')
        if regime not in ('RANGING', 'WEAK_TREND'):
            return False

        # ========== Enhanced Regime Scoring (v4.0) ==========
        if MEAN_REV_USE_ENHANCED_REGIME:
            should_block, score = self._calculate_entry_score(row)
            if should_block:
                return False
            if score < MEAN_REV_MIN_SCORE:
                return False

        # 1. 밴드 하단 이탈 (과매도)
        if row['close'] > row['lowerBB']:
            return False
        # 2. RSI 30 미만 (더 강한 과매도만)
        if row.get('rsi', 50) >= 30:
            return False
        # 3. ADX 25 미만 (강한 추세가 아닐 때만)
        if row.get('adx', 0) >= 25:
            return False
        # 4. 밴드폭 최소 확보
        if row.get('bb_width', 0) < 0.005:
            return False
        # 5. 가격이 EMA200 아래로 너무 멀지 않음 (3% 이내)
        ema200 = row.get('ema200', row['close'])
        if row['close'] < ema200 * 0.97:
            return False
        # 6. 양봉 확인
        if MEAN_REV_REQUIRE_BULLISH_CONFIRM and row['close'] <= row['open']:
            return False
        # 7. 거래량 >= 1.5배 평균
        vol_ma = row.get('vol_ma20', 0)
        if vol_ma > 0 and row['volume'] < vol_ma * 1.5:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        trade_id = trade_info.get('entry_time', 'default') if trade_info else 'default'

        if trade_id not in self._partial_taken:
            self._partial_taken[trade_id] = False

        # 1단계: BB 중심선 도달 → 50% 부분 익절
        if not self._partial_taken[trade_id] and row['high'] >= row['maBB']:
            self._partial_taken[trade_id] = True
            return entry_sl, None, 0.5

        # 2단계: BB 상단 도달 → 나머지 전량 청산
        if self._partial_taken[trade_id] and row['high'] >= row['upperBB']:
            self._partial_taken.pop(trade_id, None)
            return entry_sl, "TP_BB_Upper", None

        # 부분 익절 후 가격 하락 보호
        if self._partial_taken[trade_id]:
            # 손익분기점으로 SL 이동
            if entry_price > entry_sl:
                entry_sl = entry_price

            # Phase-aware protection (v4.0): tighter in VOLATILE_RANGE
            protect_atr = 1.5  # Default v3.0 value
            if MEAN_REV_USE_ENHANCED_REGIME:
                phase = row.get('regime_phase', 'NEUTRAL')
                if phase == 'VOLATILE_RANGE':
                    protect_atr = MEAN_REV_VOLATILE_PHASE_PROTECT_ATR

            # 진입가 대비 protect_atr ATR 하락 시 즉시 청산
            if atr > 0 and row['close'] < entry_price - protect_atr * atr:
                self._partial_taken.pop(trade_id, None)
                return entry_sl, "EXIT_MR_RETRACE", None

        return entry_sl, None, None

    def get_stop_loss_dist(self, row):
        """손절폭 계산 (v4.0: 변동성 적응형)"""
        atr = row.get('atr', 0)
        base_sl = atr * MEAN_REV_SL_ATR_MULT

        # Volatility adaptation (v4.0)
        if MEAN_REV_USE_ENHANCED_REGIME:
            volatility = row.get('regime_volatility', 'NORMAL')
            vol_mult = MEAN_REV_VOL_SL_MULT.get(volatility, 1.0)
            base_sl *= vol_mult

        return max(base_sl, row['close'] * MEAN_REV_SL_MIN_PCT)
