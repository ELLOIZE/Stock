# =========================================================
# 역추세 전략 (Mean Reversion Strategy)
# =========================================================

from strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    """
    역추세 전략 (짧게 먹기)

    진입 조건:
    - 볼린저 밴드 하단 이탈 (과매도)
    - RSI < 35 (강한 과매도)
    - ADX < 25 (강한 추세 아님)
    - 밴드폭 0.5% 이상

    청산 로직:
    - 볼린저 밴드 중심선 도달 시 익절
    """

    def check_entry(self, df, i):
        if i < 200:
            return False

        row = df.iloc[i]

        # 1. 밴드 하단 이탈 (과매도)
        if row['close'] > row['lowerBB']:
            return False
        # 2. RSI 35 미만 (강한 과매도)
        if row.get('rsi', 50) >= 35:
            return False
        # 3. ADX 25 미만 (강한 추세가 아닐 때만)
        if row.get('adx', 0) >= 25:
            return False
        # 4. 밴드폭 최소 확보
        if row.get('bb_width', 0) < 0.005:
            return False
        # 5. 가격이 EMA200 아래로 너무 멀지 않음
        ema200 = row.get('ema200', row['close'])
        if row['close'] < ema200 * 0.93:
            return False

        return True

    def check_exit(self, row, entry_price, entry_sl, atr, trade_info=None):
        # 평균 회귀 (밴드 중심선 터치 시 익절)
        if row['high'] >= row['maBB']:
            return entry_sl, "TP_Mean", None
        return entry_sl, None, None

    def get_stop_loss_dist(self, row):
        # 역추세는 2.0 ATR
        atr = row.get('atr', 0)
        return max(atr * 2.0, row['close'] * 0.004)
