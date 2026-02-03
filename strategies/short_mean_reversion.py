# =========================================================
# 숏 역추세 전략 (Short Mean Reversion Strategy) - v3.0
# =========================================================

from strategies.base import Strategy
from config.settings import (
    SHORT_MR_RSI_THRESHOLD,
    SHORT_MR_SL_ATR_MULT,
    SHORT_MR_SL_MIN_PCT,
    SHORT_MR_REQUIRE_BEARISH,
    SHORT_MR_EMA200_DIST,
    SHORT_MR_PROTECTION_ATR
)


class ShortMeanReversionStrategy(Strategy):
    """
    숏 역추세 전략 v3.0 - 과매수 반전

    진입 조건:
    - 레짐: RANGING 또는 WEAK_TREND만
    - 볼린저 밴드 상단 돌파 (과매수)
    - RSI >= 70 (강한 과매수)
    - ADX < 25 (강한 추세 아님)
    - 밴드폭 0.5% 이상
    - 가격 < EMA200 * 1.03 (위로 3% 이내)
    - 음봉 확인 (설정에 따라)
    - 거래량 >= 1.5배 평균

    청산:
    - BB 중심선 도달 → 50% 부분 익절
    - BB 하단 도달 → 나머지 청산
    - 가격 상승 시 보호 청산
    """

    def __init__(self, name="SHORT_MEAN_REV"):
        super().__init__(name)
        self.direction = 'SHORT'
        self._partial_taken = {}

    def check_entry(self, df, i):
        if i < 200:
            return False

        row = df.iloc[i]

        # 레짐 게이트: RANGING 또는 WEAK_TREND만
        regime = row.get('regime', '')
        if regime not in ('RANGING', 'WEAK_TREND'):
            return False

        # 1. 밴드 상단 돌파 (과매수)
        if row['close'] < row['upperBB']:
            return False
        # 2. RSI 70 이상 (강한 과매수)
        if row.get('rsi', 50) < SHORT_MR_RSI_THRESHOLD:
            return False
        # 3. ADX 25 미만 (강한 추세가 아닐 때만)
        if row.get('adx', 0) >= 25:
            return False
        # 4. 밴드폭 최소 확보
        if row.get('bb_width', 0) < 0.005:
            return False
        # 5. 가격이 EMA200 위로 너무 멀지 않음 (3% 이내)
        ema200 = row.get('ema200', row['close'])
        if row['close'] > ema200 * SHORT_MR_EMA200_DIST:
            return False
        # 6. 음봉 확인 (LONG의 양봉 확인 반전)
        if SHORT_MR_REQUIRE_BEARISH and row['close'] >= row['open']:
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

        # 1단계: BB 중심선 도달 → 50% 부분 익절 (숏: 가격이 내려가서 중심선 도달)
        if not self._partial_taken[trade_id] and row['low'] <= row['maBB']:
            self._partial_taken[trade_id] = True
            return entry_sl, None, 0.5

        # 2단계: BB 하단 도달 → 나머지 전량 청산 (숏: 하단까지 하락)
        if self._partial_taken[trade_id] and row['low'] <= row['lowerBB']:
            self._partial_taken.pop(trade_id, None)
            return entry_sl, "TP_BB_Lower", None

        # 부분 익절 후 가격 상승 보호
        if self._partial_taken[trade_id]:
            # 손익분기점으로 SL 이동 (숏: entry < SL이면 SL을 entry로)
            if entry_price < entry_sl:
                entry_sl = entry_price
            # 진입가 대비 1.5 ATR 상승 시 즉시 청산 (숏 반대 방향)
            if atr > 0 and row['close'] > entry_price + SHORT_MR_PROTECTION_ATR * atr:
                self._partial_taken.pop(trade_id, None)
                return entry_sl, "EXIT_MR_RETRACE", None

        return entry_sl, None, None

    def get_stop_loss_dist(self, row):
        atr = row.get('atr', 0)
        return max(atr * SHORT_MR_SL_ATR_MULT, row['close'] * SHORT_MR_SL_MIN_PCT)
