# =========================================================
# Trend pullback continuation strategy
# =========================================================

from strategies.base import Strategy


class _TrendPullbackBase(Strategy):
    """Trade trend continuation only after a controlled pullback and confirmation."""

    direction = None
    allowed_regime = None
    blocked_phase = None

    def __init__(self, name):
        super().__init__(name)
        self.direction = self.__class__.direction
        self._partial_stage = {}

    def reset_partial_tp(self, trade_id=None):
        if trade_id is None:
            self._partial_stage = {}
        else:
            self._partial_stage[trade_id] = 0

    def _valid_common_filters(self, row):
        atr = row.get('atr', 0)
        close = row.get('close', 0)
        if atr <= 0 or close <= 0:
            return False

        atr_pct = atr / close
        if atr_pct < 0.002 or atr_pct > 0.04:
            return False

        if row.get('regime') != self.allowed_regime:
            return False

        if row.get('regime_phase') == self.blocked_phase:
            return False

        adx = row.get('adx', 0)
        if adx < 18 or adx > 55:
            return False

        vol_ma = row.get('vol_ma20', 0)
        if vol_ma > 0 and row.get('volume', 0) < vol_ma * 0.8:
            return False

        bb_width = row.get('bb_width', 0)
        if bb_width <= 0 or bb_width > 0.12:
            return False

        return True

    def _recent_pullback_long(self, df, i, lookback=8):
        window = df.iloc[max(0, i - lookback):i]
        if window.empty:
            return False
        ema21_touch = (window['low'] <= window['ema21'] + window['atr'] * 0.25).any()
        bb_mid_touch = (window['low'] <= window['maBB'] + window['atr'] * 0.20).any()
        return bool(ema21_touch or bb_mid_touch)

    def _recent_pullback_short(self, df, i, lookback=8):
        window = df.iloc[max(0, i - lookback):i]
        if window.empty:
            return False
        ema21_touch = (window['high'] >= window['ema21'] - window['atr'] * 0.25).any()
        bb_mid_touch = (window['high'] >= window['maBB'] - window['atr'] * 0.20).any()
        return bool(ema21_touch or bb_mid_touch)

    def get_stop_loss_dist(self, row):
        atr = row.get('atr', 0)
        close = row.get('close', 0)
        return max(atr * 1.8, close * 0.005)


class TrendPullbackStrategy(_TrendPullbackBase):
    """
    Long trend continuation:
    1. Market is TREND_UP but not late-bull.
    2. EMA stack confirms the trend.
    3. Price recently pulled back to EMA21/BB mid.
    4. Current candle confirms the bounce with RSI recovery.
    """

    direction = 'LONG'
    allowed_regime = 'TREND_UP'
    blocked_phase = 'LATE_BULL'

    def __init__(self, name="TREND_PULLBACK"):
        super().__init__(name)

    def check_entry(self, df, i):
        if i < 220:
            return False

        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if not self._valid_common_filters(row):
            return False

        ema21 = row.get('ema21', 0)
        ema50 = row.get('ema50', 0)
        ema200 = row.get('ema200', 0)
        if not (ema21 > ema50 > ema200):
            return False

        if row['close'] <= ema21 or row['close'] <= row.get('maBB', ema21):
            return False

        if not self._recent_pullback_long(df, i):
            return False

        rsi = row.get('rsi', 50)
        prev_rsi = prev.get('rsi', 50)
        if not (45 <= rsi <= 66 and rsi > prev_rsi):
            return False

        bullish_confirmation = (
            row['close'] > row['open'] and
            row['close'] > prev['high'] and
            row['close'] > ema21
        )
        if not bullish_confirmation:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        trade_id = trade_info.get('entry_time', 'default') if trade_info else 'default'
        stage = self._partial_stage.get(trade_id, 0)
        new_sl = entry_sl

        if atr <= 0:
            return new_sl, None, None

        candles_held = trade_info.get('candles_held', 0) if trade_info else 0
        close_profit_atr = (row['close'] - entry_price) / atr
        high_profit_atr = (row['high'] - entry_price) / atr

        if candles_held >= 36 and close_profit_atr < 0.5:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_NO_FOLLOW_THROUGH", None

        if row.get('rsi', 50) < 42 and row['close'] < row.get('ema21', row['close']):
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_MOMENTUM_LOST", None

        if row['close'] < row.get('ema50', row['close']) and close_profit_atr < 1.0:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_TREND_FAIL", None

        if high_profit_atr >= 4.0:
            new_sl = max(new_sl, row['high'] - atr * 1.0)
        elif high_profit_atr >= 2.5:
            new_sl = max(new_sl, row['high'] - atr * 1.25)
        elif high_profit_atr >= 1.2:
            new_sl = max(new_sl, entry_price)

        if stage == 0 and high_profit_atr >= 1.5:
            self._partial_stage[trade_id] = 1
            return max(new_sl, entry_price), None, 0.30

        if stage == 1 and high_profit_atr >= 3.0:
            self._partial_stage[trade_id] = 2
            return new_sl, None, 0.30

        if candles_held >= 96:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_TIME_MAX", None

        return new_sl, None, None


class ShortTrendPullbackStrategy(_TrendPullbackBase):
    """
    Short trend continuation:
    1. Market is TREND_DOWN but not late-bear capitulation.
    2. EMA stack confirms the downtrend.
    3. Price recently pulled back to EMA21/BB mid.
    4. Current candle confirms rejection with RSI rollover.
    """

    direction = 'SHORT'
    allowed_regime = 'TREND_DOWN'
    blocked_phase = 'LATE_BEAR'

    def __init__(self, name="SHORT_TREND_PULLBACK"):
        super().__init__(name)

    def check_entry(self, df, i):
        if i < 220:
            return False

        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if not self._valid_common_filters(row):
            return False

        ema21 = row.get('ema21', 0)
        ema50 = row.get('ema50', 0)
        ema200 = row.get('ema200', 0)
        if not (ema21 < ema50 < ema200):
            return False

        if row['close'] >= ema21 or row['close'] >= row.get('maBB', ema21):
            return False

        if not self._recent_pullback_short(df, i):
            return False

        rsi = row.get('rsi', 50)
        prev_rsi = prev.get('rsi', 50)
        if not (34 <= rsi <= 55 and rsi < prev_rsi):
            return False

        bearish_confirmation = (
            row['close'] < row['open'] and
            row['close'] < prev['low'] and
            row['close'] < ema21
        )
        if not bearish_confirmation:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        trade_id = trade_info.get('entry_time', 'default') if trade_info else 'default'
        stage = self._partial_stage.get(trade_id, 0)
        new_sl = entry_sl

        if atr <= 0:
            return new_sl, None, None

        candles_held = trade_info.get('candles_held', 0) if trade_info else 0
        close_profit_atr = (entry_price - row['close']) / atr
        low_profit_atr = (entry_price - row['low']) / atr

        if candles_held >= 36 and close_profit_atr < 0.5:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_NO_FOLLOW_THROUGH", None

        if row.get('rsi', 50) > 58 and row['close'] > row.get('ema21', row['close']):
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_MOMENTUM_LOST", None

        if row['close'] > row.get('ema50', row['close']) and close_profit_atr < 1.0:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_TREND_FAIL", None

        if low_profit_atr >= 4.0:
            new_sl = min(new_sl, row['low'] + atr * 1.0)
        elif low_profit_atr >= 2.5:
            new_sl = min(new_sl, row['low'] + atr * 1.25)
        elif low_profit_atr >= 1.2:
            new_sl = min(new_sl, entry_price)

        if stage == 0 and low_profit_atr >= 1.5:
            self._partial_stage[trade_id] = 1
            return min(new_sl, entry_price), None, 0.30

        if stage == 1 and low_profit_atr >= 3.0:
            self._partial_stage[trade_id] = 2
            return new_sl, None, 0.30

        if candles_held >= 96:
            self._partial_stage.pop(trade_id, None)
            return new_sl, "EXIT_TIME_MAX", None

        return new_sl, None, None
