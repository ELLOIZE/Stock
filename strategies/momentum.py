# =========================================================
# 모멘텀 전략 (Momentum Strategy) - v5.1 개선
# v4 진입 유지 + 조기 익절 + 시간 청산 완화 + 트레일링 최적화
# =========================================================

from strategies.base import Strategy
from config.settings import (
    MOM_RSI_ENTRY,
    MOM_RSI_EXIT_BELOW,
    MOM_RSI_OVERBOUGHT,
    MOM_RSI_SLOPE_PERIOD,
    MOM_ADX_MIN,
    MOM_VOL_MULT,
    MOM_MIN_BULLISH,
    MOM_SL_ATR_MULT,
    MOM_SL_MIN_PCT,
    MOM_TIME_EXIT_CANDLES,
    MOM_TIME_EXIT_MIN_ATR,
    MOM_PARTIAL_1_PCT,
    MOM_PARTIAL_2_RSI,
    MOM_PARTIAL_2_DROP,
    MOM_TRAIL_BE_ATR,
    MOM_TRAIL_S1_ATR,
    MOM_TRAIL_S1_DIST,
    MOM_TRAIL_S2_ATR,
    MOM_TRAIL_S2_DIST,
    MOM_PARTIAL_EARLY_ATR,
    MOM_PARTIAL_EARLY_PCT
)


class MomentumStrategy(Strategy):
    """
    RSI 모멘텀 전략 v5.1

    진입 조건 (v4 유지):
    - 레짐: TREND_UP만
    - RSI 상향 돌파 (이전 < 60, 현재 >= 60)
    - RSI 기울기 양수 (3캔들)
    - EMA 정배열 (EMA21 > EMA50 > EMA200)
    - 가격 > EMA21
    - ADX >= 30
    - 거래량 >= 2.0배
    - 최근 5봉 중 3봉 양봉

    청산 개선:
    - Stage 0→1: 2.0 ATR 수익 → 25% 조기 익절 (NEW)
    - Stage 1→2: RSI 75+ 피크 후 10pt 하락 → 30%
    - Stage 2→3: RSI 80+ 피크 후 15pt 하락 → 30%
    - 잔여: RSI < 60 → 전량
    - EXIT_MOM_LOST: RSI < 45 AND 손실 중
    - EXIT_TIME_STALE: 30캔들 내 0.5 ATR 수익 미달
    - 3단계 트레일링 (1.5→BE, 2.5→1.0, 4.0→0.8)
    """

    def __init__(self, name="MOMENTUM"):
        super().__init__(name)
        self._peak_rsi = {}
        self._partial_stage = {}  # 0=없음, 1=ATR TP, 2=RSI TP1, 3=RSI TP2

    def check_entry(self, df, i):
        if i < 200:
            return False

        row = df.iloc[i]
        prev = df.iloc[i - 1]

        # 레짐 게이트: TREND_UP만
        regime = row.get('regime', '')
        if regime != 'TREND_UP':
            return False

        rsi = row.get('rsi', 50)
        prev_rsi = prev.get('rsi', 50)

        # 1. RSI 상향 돌파 (v4 유지)
        if not (prev_rsi < MOM_RSI_ENTRY and rsi >= MOM_RSI_ENTRY):
            return False

        # 2. RSI 기울기 양수
        rsi_past = df.iloc[i - MOM_RSI_SLOPE_PERIOD].get('rsi', 50)
        if rsi <= rsi_past:
            return False

        # 3. EMA 정배열 (EMA21 > EMA50 > EMA200)
        ema21 = row.get('ema21', 0)
        ema50 = row.get('ema50', 0)
        ema200 = row.get('ema200', 0)
        if not (ema21 > ema50 > ema200):
            return False

        # 4. 가격 > EMA21
        if row['close'] <= ema21:
            return False

        # 5. ADX >= MOM_ADX_MIN
        adx = row.get('adx', 0)
        if adx < MOM_ADX_MIN:
            return False

        # 6. 거래량 >= MOM_VOL_MULT배 평균
        vol_ma = row.get('vol_ma20', 0)
        if vol_ma > 0 and row['volume'] < vol_ma * MOM_VOL_MULT:
            return False

        # 7. 최근 5봉 중 3봉 이상 양봉
        bullish = 0
        for j in range(max(0, i - 4), i + 1):
            r = df.iloc[j]
            if r['close'] > r['open']:
                bullish += 1
        if bullish < MOM_MIN_BULLISH:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        new_sl = entry_sl
        rsi = row.get('rsi', 50)
        trade_id = trade_info.get('entry_time', 'default') if trade_info else 'default'

        # 상태 초기화
        if trade_id not in self._peak_rsi:
            self._peak_rsi[trade_id] = rsi
        if trade_id not in self._partial_stage:
            self._partial_stage[trade_id] = 0

        # RSI peak 추적
        peak = self._peak_rsi[trade_id]
        if rsi > peak:
            self._peak_rsi[trade_id] = rsi
            peak = rsi

        stage = self._partial_stage[trade_id]

        # 시간 기반 청산: N캔들 내 최소 수익 미달
        if trade_info:
            candles_held = trade_info.get('candles_held', 0)
            if candles_held >= MOM_TIME_EXIT_CANDLES and atr > 0:
                profit_atr = (row['close'] - entry_price) / atr
                if profit_atr < MOM_TIME_EXIT_MIN_ATR:
                    self._cleanup(trade_id)
                    return new_sl, "EXIT_TIME_STALE", None

        # Stage 0→1: 조기 ATR 부분 익절
        if stage == 0 and atr > 0:
            profit_atr = (row['close'] - entry_price) / atr
            if profit_atr >= MOM_PARTIAL_EARLY_ATR:
                self._partial_stage[trade_id] = 1
                return new_sl, None, MOM_PARTIAL_EARLY_PCT

        # Stage 1→2: RSI 75+ 피크 후 10pt 하락 → 30%
        if stage == 1:
            if peak >= MOM_RSI_OVERBOUGHT and rsi < peak - 10:
                self._partial_stage[trade_id] = 2
                return new_sl, None, MOM_PARTIAL_1_PCT

        # Stage 2→3: RSI 80+ 피크 후 15pt 하락 → 추가 30%
        if stage == 2:
            if peak >= MOM_PARTIAL_2_RSI and rsi < peak - MOM_PARTIAL_2_DROP:
                self._partial_stage[trade_id] = 3
                return new_sl, None, MOM_PARTIAL_1_PCT

        # 잔여분 청산: stage>=1 후 RSI < 60
        if stage >= 1 and rsi < 60:
            self._cleanup(trade_id)
            return new_sl, "TP_MOM_FADE", None

        # EXIT_MOM_LOST: RSI 하락 AND 손실 중
        if rsi < MOM_RSI_EXIT_BELOW and row['close'] < entry_price:
            self._cleanup(trade_id)
            return new_sl, "EXIT_MOM_LOST", None

        # 3단계 트레일링 스탑
        if atr > 0:
            if row['high'] > entry_price + MOM_TRAIL_S2_ATR * atr:
                trail = row['high'] - MOM_TRAIL_S2_DIST * atr
                if trail > new_sl:
                    new_sl = trail
            elif row['high'] > entry_price + MOM_TRAIL_S1_ATR * atr:
                trail = row['high'] - MOM_TRAIL_S1_DIST * atr
                if trail > new_sl:
                    new_sl = trail
            elif row['high'] > entry_price + MOM_TRAIL_BE_ATR * atr:
                if entry_price > new_sl:
                    new_sl = entry_price

        return new_sl, None, None

    def _cleanup(self, trade_id):
        """거래 상태 정리"""
        self._peak_rsi.pop(trade_id, None)
        self._partial_stage.pop(trade_id, None)

    def get_stop_loss_dist(self, row):
        atr = row.get('atr', 0)
        return max(atr * MOM_SL_ATR_MULT, row['close'] * MOM_SL_MIN_PCT)
