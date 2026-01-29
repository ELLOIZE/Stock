# =========================================================
# 추세 추종 전략 (Breakout Strategy) - v4.0 완화된 진입
# =========================================================

from strategies.base import Strategy
from utils.helpers import safe_json_list, nearest_resistance_above
from config.settings import (
    TRAILING_STOP_LEVELS,
    BREAKOUT_PARTIAL_TP,
    BREAKOUT_MIN_SCORE,
    BREAKOUT_SL_ATR_MULT,
    BREAKOUT_RES_MARGIN_PCT,
    BREAKOUT_RSI_MIN,
    BREAKOUT_RSI_MAX
)


class BreakoutStrategy(Strategy):
    """
    추세 추종 전략 v4.0 - 완화된 진입 조건

    진입 조건:
    - 레짐: TREND_UP만
    - 저항선 1봉 돌파 (2봉→1봉 완화) + 0.15% 마진 (0.5%→0.15%)
    - EMA21 > EMA50 (EMA200 제거)
    - 종가 > EMA21
    - RSI 40-80 (45-70에서 확대)
    - 최근 5봉 중 3봉 이상 양봉
    - 점수 >= 1 (2→1)
    """

    def __init__(self, name="BREAKOUT"):
        super().__init__(name)
        self.partial_tp_taken = {}

    def reset_partial_tp(self, trade_id=None):
        """부분 익절 상태 초기화"""
        if trade_id:
            self.partial_tp_taken[trade_id] = {'tp1': False, 'tp2': False}
        else:
            self.partial_tp_taken = {}

    def _count_recent_bullish(self, df, i, lookback=5):
        """최근 N봉 중 양봉 개수"""
        count = 0
        for j in range(max(0, i - lookback + 1), i + 1):
            row = df.iloc[j]
            if row['close'] > row['open']:
                count += 1
        return count

    def _count_consecutive_bullish(self, df, i):
        """현재부터 연속 양봉 개수"""
        count = 0
        for j in range(i, max(i - 10, -1), -1):
            row = df.iloc[j]
            if row['close'] > row['open']:
                count += 1
            else:
                break
        return count

    def _calculate_entry_score(self, df, i):
        """
        점수 기반 진입 조건 계산 (v4.0)

        Returns:
            tuple: (필수조건 충족여부, 점수)
        """
        row = df.iloc[i]
        prev = df.iloc[i-1]

        # ========== 필수 조건 체크 ==========

        # 1. 저항선 1봉 돌파 (완화: 2봉→1봉, 마진 0.5%→0.15%)
        res_list = safe_json_list(prev.get('resistanceLevels_5m', []))
        target_res = nearest_resistance_above(prev['close'], res_list)
        if target_res is None:
            return False, 0

        margin = target_res * BREAKOUT_RES_MARGIN_PCT
        if not (row['close'] > target_res + margin):
            return False, 0

        # 2. EMA21 > EMA50 (EMA200 제거하여 완화)
        ema21 = row.get('ema21', 0)
        ema50 = row.get('ema50', 0)

        if not (ema21 > ema50):
            return False, 0

        # 3. 종가 > EMA21
        if row['close'] < ema21:
            return False, 0

        # 4. RSI 범위 확대 (40-80)
        rsi = row.get('rsi', 50)
        if rsi < BREAKOUT_RSI_MIN or rsi > BREAKOUT_RSI_MAX:
            return False, 0

        # 5. 최근 5봉 중 3봉 이상 양봉
        bullish_count = self._count_recent_bullish(df, i, 5)
        if bullish_count < 3:
            return False, 0

        # ========== 점수 조건 계산 ==========
        score = 0
        vol_ma = row.get('vol_ma20', 0)

        # 거래량 >= 1.5배: +1점
        if vol_ma > 0 and row['volume'] >= vol_ma * 1.5:
            score += 1

        # 거래량 >= 2.0배: +1점 (보너스)
        if vol_ma > 0 and row['volume'] >= vol_ma * 2.0:
            score += 1

        # ADX > 30: +1점 (강한 추세)
        adx = row.get('adx', 0)
        if adx > 30:
            score += 1

        # BB폭 10% 이상 증가: +1점
        bb_width = row.get('bb_width', 0)
        prev_bb_avg = (
            df.iloc[i-1].get('bb_width', 0) +
            df.iloc[i-2].get('bb_width', 0) +
            df.iloc[i-3].get('bb_width', 0)
        ) / 3
        if prev_bb_avg > 0 and bb_width > prev_bb_avg * 1.10:
            score += 1

        # 연속 양봉 3개 이상: +1점
        consecutive = self._count_consecutive_bullish(df, i)
        if consecutive >= 3:
            score += 1

        # EMA 3중 정배열 보너스: +1점
        ema200 = row.get('ema200', 0)
        if ema21 > ema50 > ema200:
            score += 1

        return True, score

    def check_entry(self, df, i):
        """레짐 기반 진입 신호 확인"""
        if i < 200:
            return False

        # 레짐 게이트: TREND_UP만 진입
        if df.iloc[i].get('regime') != 'TREND_UP':
            return False

        required_passed, score = self._calculate_entry_score(df, i)

        if not required_passed:
            return False

        return score >= BREAKOUT_MIN_SCORE

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        """4단계 트레일링 스탑 + 부분 익절"""
        new_sl = entry_sl
        partial_close = None

        if atr <= 0:
            return new_sl, None, None

        current_profit_atr = (row['high'] - entry_price) / atr

        # 부분 익절 체크
        if trade_info:
            trade_id = trade_info.get('entry_time', 'default')
            if trade_id not in self.partial_tp_taken:
                self.partial_tp_taken[trade_id] = {'tp1': False, 'tp2': False}

            tp_state = self.partial_tp_taken[trade_id]

            if not tp_state['tp1'] and current_profit_atr >= BREAKOUT_PARTIAL_TP['tp1']['profit_atr']:
                tp_state['tp1'] = True
                partial_close = BREAKOUT_PARTIAL_TP['tp1']['close_pct']

            elif tp_state['tp1'] and not tp_state['tp2'] and current_profit_atr >= BREAKOUT_PARTIAL_TP['tp2']['profit_atr']:
                tp_state['tp2'] = True
                partial_close = BREAKOUT_PARTIAL_TP['tp2']['close_pct']

        # 4단계 트레일링 스탑
        levels = TRAILING_STOP_LEVELS

        if row['high'] > entry_price + (levels['stage3']['profit_atr'] * atr):
            trail_sl = row['high'] - (levels['stage3']['trail_atr'] * atr)
            if trail_sl > new_sl:
                new_sl = trail_sl

        elif row['high'] > entry_price + (levels['stage2']['profit_atr'] * atr):
            trail_sl = row['high'] - (levels['stage2']['trail_atr'] * atr)
            if trail_sl > new_sl:
                new_sl = trail_sl

        elif row['high'] > entry_price + (levels['stage1']['profit_atr'] * atr):
            trail_sl = row['high'] - (levels['stage1']['trail_atr'] * atr)
            if trail_sl > new_sl:
                new_sl = trail_sl

        elif row['high'] > entry_price + (levels['breakeven']['profit_atr'] * atr):
            if entry_price > new_sl:
                new_sl = entry_price

        return new_sl, None, partial_close

    def get_stop_loss_dist(self, row):
        """손절폭 계산"""
        atr = row.get('atr', 0)
        return max(atr * BREAKOUT_SL_ATR_MULT, row['close'] * 0.004)
