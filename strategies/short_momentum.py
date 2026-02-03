# =========================================================
# 숏 모멘텀 전략 (Short Momentum Strategy) - v5.1
# v4 진입 반전 + 조기 익절 + 시간 청산 + 트레일링 최적화
# =========================================================

from strategies.base import Strategy
from config.settings import (
    MOM_RSI_OVERBOUGHT,
    MOM_RSI_SLOPE_PERIOD,
    MOM_MIN_BULLISH,
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
    MOM_PARTIAL_EARLY_PCT,
    SHORT_MOM_RSI_ENTRY,
    SHORT_MOM_RSI_EXIT,
    SHORT_MOM_SL_ATR_MULT,
    SHORT_MOM_SL_MIN_PCT,
    SHORT_MOM_ADX_MIN,
    SHORT_MOM_VOL_MULT,
    SHORT_MOM_TIME_EXIT_CANDLES
)


class ShortMomentumStrategy(Strategy):
    """
    숏 RSI 모멘텀 전략 v5.1

    진입 조건 (LONG 반전):
    - 레짐: TREND_DOWN만
    - RSI 하향 돌파 (이전 > 40, 현재 <= 40)
    - RSI 기울기 음수 (3캔들)
    - EMA 역배열 (EMA21 < EMA50 < EMA200)
    - 가격 < EMA21
    - ADX >= 30
    - 거래량 >= 2.0배
    - 최근 5봉 중 3봉 음봉

    청산 (LONG 반전):
    - Stage 0→1: 2.0 ATR 수익 → 25% 조기 익절
    - Stage 1→2: RSI 25 이하 저점 후 10pt 상승 → 30%
    - Stage 2→3: RSI 20 이하 저점 후 15pt 상승 → 30%
    - 잔여: RSI > 40 → 전량
    - EXIT_MOM_LOST: RSI > 55 AND 손실 중
    - EXIT_TIME_STALE: 30캔들 내 0.5 ATR 수익 미달
    - 3단계 트레일링 (숏 반전)
    """

    def __init__(self, name="SHORT_MOMENTUM"):
        super().__init__(name)
        self.direction = 'SHORT'
        self._trough_rsi = {}   # 숏: RSI 저점 추적 (LONG의 peak 반전)
        self._partial_stage = {}  # 0=없음, 1=ATR TP, 2=RSI TP1, 3=RSI TP2

    def check_entry(self, df, i):
        if i < 200:
            return False

        row = df.iloc[i]
        prev = df.iloc[i - 1]

        # 레짐 게이트: TREND_DOWN만
        regime = row.get('regime', '')
        if regime != 'TREND_DOWN':
            return False

        # 추가 필터: 최근 3봉 연속 하락 필수
        if i >= 3:
            consecutive_down = all(df.iloc[i-j]['close'] < df.iloc[i-j]['open'] for j in range(3))
            if not consecutive_down:
                return False

        rsi = row.get('rsi', 50)
        prev_rsi = prev.get('rsi', 50)

        # 1. RSI 하향 돌파 (이전 > 35, 현재 <= 35)
        if not (prev_rsi > SHORT_MOM_RSI_ENTRY and rsi <= SHORT_MOM_RSI_ENTRY):
            return False

        # 2. RSI 기울기 음수 (하락 중)
        rsi_past = df.iloc[i - MOM_RSI_SLOPE_PERIOD].get('rsi', 50)
        if rsi >= rsi_past:
            return False

        # 3. EMA 역배열 (EMA21 < EMA50 < EMA200)
        ema21 = row.get('ema21', 0)
        ema50 = row.get('ema50', 0)
        ema200 = row.get('ema200', 0)
        if not (ema21 < ema50 < ema200):
            return False

        # 4. 가격 < EMA21
        if row['close'] >= ema21:
            return False

        # 5. ADX >= SHORT_MOM_ADX_MIN
        adx = row.get('adx', 0)
        if adx < SHORT_MOM_ADX_MIN:
            return False

        # 6. 거래량 >= SHORT_MOM_VOL_MULT배 평균
        vol_ma = row.get('vol_ma20', 0)
        if vol_ma > 0 and row['volume'] < vol_ma * SHORT_MOM_VOL_MULT:
            return False

        # 7. 최근 5봉 중 3봉 이상 음봉
        bearish = 0
        for j in range(max(0, i - 4), i + 1):
            r = df.iloc[j]
            if r['close'] < r['open']:
                bearish += 1
        if bearish < MOM_MIN_BULLISH:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        new_sl = entry_sl
        rsi = row.get('rsi', 50)
        trade_id = trade_info.get('entry_time', 'default') if trade_info else 'default'

        # 상태 초기화
        if trade_id not in self._trough_rsi:
            self._trough_rsi[trade_id] = rsi
        if trade_id not in self._partial_stage:
            self._partial_stage[trade_id] = 0

        # RSI 저점(trough) 추적 (LONG의 peak 반전)
        trough = self._trough_rsi[trade_id]
        if rsi < trough:
            self._trough_rsi[trade_id] = rsi
            trough = rsi

        stage = self._partial_stage[trade_id]

        # 시간 기반 청산: N캔들 내 최소 수익 미달
        if trade_info:
            candles_held = trade_info.get('candles_held', 0)
            if candles_held >= SHORT_MOM_TIME_EXIT_CANDLES and atr > 0:
                profit_atr = (entry_price - row['close']) / atr  # 숏 수익
                if profit_atr < MOM_TIME_EXIT_MIN_ATR:
                    self._cleanup(trade_id)
                    return new_sl, "EXIT_TIME_STALE", None

        # Stage 0→1: 조기 ATR 부분 익절
        if stage == 0 and atr > 0:
            profit_atr = (entry_price - row['close']) / atr  # 숏 수익
            if profit_atr >= MOM_PARTIAL_EARLY_ATR:
                self._partial_stage[trade_id] = 1
                return new_sl, None, MOM_PARTIAL_EARLY_PCT

        # Stage 1→2: RSI 25 이하 저점 후 10pt 상승 → 30%
        if stage == 1:
            oversold_threshold = 100 - MOM_RSI_OVERBOUGHT  # 75 → 25
            if trough <= oversold_threshold and rsi > trough + 10:
                self._partial_stage[trade_id] = 2
                return new_sl, None, MOM_PARTIAL_1_PCT

        # Stage 2→3: RSI 20 이하 저점 후 15pt 상승 → 추가 30%
        if stage == 2:
            deep_oversold = 100 - MOM_PARTIAL_2_RSI  # 80 → 20
            if trough <= deep_oversold and rsi > trough + MOM_PARTIAL_2_DROP:
                self._partial_stage[trade_id] = 3
                return new_sl, None, MOM_PARTIAL_1_PCT

        # 잔여분 청산: stage>=1 후 RSI > 55 (중립선 상향 돌파)
        if stage >= 1 and rsi > 55:
            self._cleanup(trade_id)
            return new_sl, "TP_MOM_FADE", None

        # EXIT_MOM_LOST: RSI 상승 AND 손실 0.3% 초과 (덜 공격적으로)
        if rsi > SHORT_MOM_RSI_EXIT and row['close'] > entry_price * 1.003:
            self._cleanup(trade_id)
            return new_sl, "EXIT_MOM_LOST", None

        # 3단계 트레일링 스탑 (숏 반전)
        if atr > 0:
            if row['low'] < entry_price - MOM_TRAIL_S2_ATR * atr:
                trail = row['low'] + MOM_TRAIL_S2_DIST * atr
                if trail > new_sl:
                    new_sl = trail
            elif row['low'] < entry_price - MOM_TRAIL_S1_ATR * atr:
                trail = row['low'] + MOM_TRAIL_S1_DIST * atr
                if trail > new_sl:
                    new_sl = trail
            elif row['low'] < entry_price - MOM_TRAIL_BE_ATR * atr:
                if entry_price < new_sl:
                    new_sl = entry_price

        return new_sl, None, None

    def _cleanup(self, trade_id):
        """거래 상태 정리"""
        self._trough_rsi.pop(trade_id, None)
        self._partial_stage.pop(trade_id, None)

    def get_stop_loss_dist(self, row):
        atr = row.get('atr', 0)
        return max(atr * SHORT_MOM_SL_ATR_MULT, row['close'] * SHORT_MOM_SL_MIN_PCT)
