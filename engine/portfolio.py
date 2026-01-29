# =========================================================
# 포트폴리오 매니저 (관제탑) - 개선 버전
# =========================================================

import pandas as pd
from datetime import datetime

from config.settings import (
    FEE_RATE, RISK_PER_TRADE,
    SLIPPAGE_ATR_MULT, SLIPPAGE_MIN_PCT, SLIPPAGE_MAX_PCT,
    VOLATILITY_RISK_TIERS, DRAWDOWN_RISK_TIERS,
    MAX_SAME_DIRECTION_POSITIONS, CONCURRENT_POSITION_RISK_MULT
)


class PortfolioManager:
    """
    다중 전략 포트폴리오 관리자 - 개선 버전

    개선 사항:
    - 부분 청산 지원
    - 동적 포지션 사이징 (변동성 기반)
    - 드로우다운 기반 리스크 조정
    - 동시 포지션 리스크 관리
    """

    def __init__(self, initial_capital=10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.strategies = []  # [(strategy, weight), ...]
        self.active_trades = {}  # {strategy_name: trade_info}
        self.trade_history = []
        self.equity_curve = []
        self.fee_rate = FEE_RATE
        self.slippage_atr_mult = SLIPPAGE_ATR_MULT
        self.slippage_min_pct = SLIPPAGE_MIN_PCT
        self.slippage_max_pct = SLIPPAGE_MAX_PCT

        # 드로우다운 추적
        self.daily_high_watermark = initial_capital
        self.current_day = None
        self.daily_dd_halt = False  # 당일 거래 중단 플래그

    def add_strategy(self, strategy, weight=0.5):
        """전략 등록 및 비중 설정"""
        self.strategies.append({'algo': strategy, 'weight': weight})
        self.active_trades[strategy.name] = None

    def _apply_slippage(self, price, atr, direction='buy'):
        """슬리피지 적용"""
        slippage_amt = atr * self.slippage_atr_mult
        min_slip = price * self.slippage_min_pct
        max_slip = price * self.slippage_max_pct
        slippage_amt = max(min_slip, min(slippage_amt, max_slip))

        if direction == 'buy':
            return price + slippage_amt
        else:
            return price - slippage_amt

    def _get_volatility_risk(self, atr, price):
        """변동성 기반 리스크 계산"""
        if atr <= 0 or price <= 0:
            return RISK_PER_TRADE

        atr_pct = atr / price

        for tier_name, tier in VOLATILITY_RISK_TIERS.items():
            if atr_pct < tier['max_atr_pct']:
                return tier['risk']

        return VOLATILITY_RISK_TIERS['high']['risk']

    def _get_drawdown_adjustment(self):
        """드로우다운 기반 리스크 조정"""
        if self.daily_high_watermark <= 0:
            return 1.0, True

        current_dd = (self.daily_high_watermark - self.current_capital) / self.daily_high_watermark

        for tier_name, tier in DRAWDOWN_RISK_TIERS.items():
            if current_dd < tier['max_dd']:
                return tier['risk_mult'], tier['allow_entry']

        # 최악의 경우 거래 중단
        return 0.0, False

    def _get_concurrent_position_count(self):
        """현재 활성 포지션 수"""
        return sum(1 for t in self.active_trades.values() if t is not None)

    def _calculate_position_size(self, atr, price, sl_dist):
        """
        동적 포지션 사이징

        고려 요소:
        1. 변동성 기반 기본 리스크
        2. 드로우다운 기반 조정
        3. 동시 포지션 시 리스크 축소
        """
        # 기본 리스크 (변동성 기반)
        base_risk = self._get_volatility_risk(atr, price)

        # 드로우다운 조정
        dd_mult, allow_entry = self._get_drawdown_adjustment()
        if not allow_entry:
            return 0, False  # 진입 불가

        adjusted_risk = base_risk * dd_mult

        # 동시 포지션 시 리스크 축소
        active_count = self._get_concurrent_position_count()
        if active_count >= 1:  # 이미 포지션이 있으면
            if active_count >= MAX_SAME_DIRECTION_POSITIONS:
                return 0, False  # 최대 포지션 도달
            adjusted_risk *= CONCURRENT_POSITION_RISK_MULT

        # 리스크 금액 및 사이즈 계산
        risk_amt = self.current_capital * adjusted_risk
        size = risk_amt / sl_dist if sl_dist > 0 else 0

        return size, True

    def _update_daily_tracking(self, timestamp):
        """일별 추적 업데이트"""
        try:
            if isinstance(timestamp, str):
                current_day = timestamp[:10]  # YYYY-MM-DD
            elif isinstance(timestamp, (datetime, pd.Timestamp)):
                current_day = timestamp.strftime('%Y-%m-%d')
            else:
                current_day = str(timestamp)[:10]
        except Exception:
            current_day = str(timestamp)[:10]

        # 새로운 날 시작
        if current_day != self.current_day:
            self.current_day = current_day
            self.daily_high_watermark = self.current_capital
            self.daily_dd_halt = False

        # 고점 갱신
        if self.current_capital > self.daily_high_watermark:
            self.daily_high_watermark = self.current_capital

        # DD 6% 초과 시 당일 거래 중단
        if self.daily_high_watermark > 0:
            current_dd = (self.daily_high_watermark - self.current_capital) / self.daily_high_watermark
            if current_dd > DRAWDOWN_RISK_TIERS['halt']['max_dd']:
                self.daily_dd_halt = True

    def _handle_partial_exit(self, strat_name, trade, row, timestamp, exit_price, exit_reason, close_pct):
        """부분 청산 처리"""
        atr = row.get('atr', 0) if hasattr(row, 'get') else 0
        actual_exit_price = self._apply_slippage(exit_price, atr, 'sell')

        # 청산할 수량 계산
        close_size = trade['remaining_size'] * close_pct
        pnl = (actual_exit_price - trade['entry_price']) * close_size
        fee = (trade['entry_price'] + exit_price) * close_size * self.fee_rate
        net_pnl = pnl - fee

        self.current_capital += net_pnl

        # 잔여 수량 업데이트
        trade['remaining_size'] -= close_size

        # 부분 청산 기록
        self.trade_history.append({
            'entry_time': trade['entry_time'],
            'exit_time': timestamp,
            'entry_price': trade['entry_price'],
            'exit_price': actual_exit_price,
            'size': close_size,
            'net_pnl': net_pnl,
            'exit_reason': f"PARTIAL_{exit_reason}",
            'type': strat_name,
            'is_partial': True
        })

        # 잔여 수량이 거의 없으면 포지션 종료
        if trade['remaining_size'] < trade['original_size'] * 0.01:
            self.active_trades[strat_name] = None
            return True  # 포지션 완전 종료

        return False  # 포지션 유지

    def _handle_exit(self, strat_name, trade, row, timestamp, exit_price, exit_reason):
        """전체 포지션 청산 처리"""
        atr = row.get('atr', 0) if hasattr(row, 'get') else 0
        actual_exit_price = self._apply_slippage(exit_price, atr, 'sell')

        remaining_size = trade.get('remaining_size', trade['size'])
        pnl = (actual_exit_price - trade['entry_price']) * remaining_size
        fee = (trade['entry_price'] + exit_price) * remaining_size * self.fee_rate
        net_pnl = pnl - fee

        self.current_capital += net_pnl

        self.trade_history.append({
            'entry_time': trade['entry_time'],
            'exit_time': timestamp,
            'entry_price': trade['entry_price'],
            'exit_price': actual_exit_price,
            'size': remaining_size,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'type': strat_name,
            'is_partial': False
        })

        self.active_trades[strat_name] = None

    def _check_exits(self, df, i, row, timestamp, atr):
        """기존 포지션 청산 체크"""
        for strat_name in list(self.active_trades.keys()):
            trade = self.active_trades[strat_name]
            if trade is None:
                continue

            algo = next(s['algo'] for s in self.strategies if s['algo'].name == strat_name)

            # 보유 기간 계산
            candles_held = i - trade['entry_index']
            trade_info = {
                'entry_time': trade['entry_time'],
                'candles_held': candles_held,
                'entry_price': trade['entry_price']
            }

            # 전략별 청산 로직 호출 (확장된 반환값 처리)
            exit_result = algo.check_exit(row, trade['entry_price'], trade['entry_sl'], atr, trade_info)

            # 반환값 파싱 (2개 또는 3개)
            if len(exit_result) == 3:
                new_sl, force_exit_reason, partial_close = exit_result
            else:
                new_sl, force_exit_reason = exit_result
                partial_close = None

            # SL 업데이트
            trade['entry_sl'] = new_sl

            # 부분 청산 처리
            if partial_close is not None and partial_close > 0:
                position_closed = self._handle_partial_exit(
                    strat_name, trade, row, timestamp, row['close'],
                    force_exit_reason or "PARTIAL_TP", partial_close
                )
                if position_closed:
                    continue  # 포지션 완전 종료됨

            exit_reason = force_exit_reason
            exit_price = None

            # SL 체크
            if row['low'] <= trade['entry_sl']:
                exit_price = trade['entry_sl']
                if exit_price > trade['entry_price']:
                    exit_reason = "Trailing_Win"
                else:
                    exit_reason = "SL"

            # 강제 익절/청산
            elif force_exit_reason and partial_close is None:
                exit_price = row['close']

            # 포지션 종료 실행
            if exit_reason and exit_price is not None:
                self._handle_exit(strat_name, trade, row, timestamp, exit_price, exit_reason)

    def _check_entries(self, df, i, row, timestamp, atr):
        """신규 진입 체크"""
        # 당일 거래 중단 상태면 진입 불가
        if self.daily_dd_halt:
            return

        # Portfolio-level regime gate: limit positions during TREND_DOWN
        current_regime = row.get('regime', 'UNKNOWN')
        if current_regime == 'TREND_DOWN':
            active_count = self._get_concurrent_position_count()
            if active_count >= 1:
                return  # No new entries during downtrend if already have a position

        for item in self.strategies:
            algo = item['algo']
            weight = item['weight']
            name = algo.name

            # ATR 추출
            atr = row.get('atr', 0)

            # 이미 포지션 있으면 패스
            if self.active_trades[name] is not None:
                continue

            # 진입 신호 발생?
            if algo.check_entry(df, i):
                # 손절폭 계산
                sl_dist = algo.get_stop_loss_dist(row)

                # 동적 포지션 사이징
                size, allow_entry = self._calculate_position_size(atr, row['close'], sl_dist)

                if not allow_entry or size <= 0:
                    continue  # 진입 불가

                # 진입 실행 (슬리피지 적용)
                actual_entry_price = self._apply_slippage(row['close'], atr, 'buy')

                self.active_trades[name] = {
                    'entry_price': actual_entry_price,
                    'entry_sl': actual_entry_price - sl_dist,
                    'size': size,
                    'original_size': size,
                    'remaining_size': size,
                    'entry_time': timestamp,
                    'entry_index': i
                }

                # 전략의 부분 익절 상태 초기화
                if hasattr(algo, 'reset_partial_tp'):
                    algo.reset_partial_tp(timestamp)

    def run_backtest(self, df):
        """
        백테스트 실행

        Args:
            df: 지표가 계산된 데이터프레임

        Returns:
            tuple: (거래 기록 DataFrame, 자산 곡선 DataFrame)
        """
        print(f"백테스팅 시작 (총 {len(df)} 캔들)...")

        for i in range(len(df)):
            row = df.iloc[i]
            timestamp = row['timestamp']

            # 일별 추적 업데이트
            self._update_daily_tracking(timestamp)

            # 자산 기록 (현금 + 미실현 손익)
            unrealized = 0.0
            for trade in self.active_trades.values():
                if trade is not None:
                    unrealized += (row['close'] - trade['entry_price']) * trade.get('remaining_size', trade.get('size', 0))
            self.equity_curve.append({'timestamp': timestamp, 'equity': self.current_capital + unrealized})

            atr = row.get('atr', 0)
            if pd.isna(atr) or atr == 0:
                continue

            # A. 기존 포지션 관리 (청산 체크)
            self._check_exits(df, i, row, timestamp, atr)

            # B. 신규 진입 체크
            self._check_entries(df, i, row, timestamp, atr)

        return pd.DataFrame(self.trade_history), pd.DataFrame(self.equity_curve)

    def get_risk_status(self):
        """현재 리스크 상태 반환"""
        dd_mult, allow_entry = self._get_drawdown_adjustment()
        current_dd = 0
        if self.daily_high_watermark > 0:
            current_dd = (self.daily_high_watermark - self.current_capital) / self.daily_high_watermark

        return {
            'current_capital': self.current_capital,
            'daily_high_watermark': self.daily_high_watermark,
            'current_drawdown': current_dd,
            'risk_multiplier': dd_mult,
            'entry_allowed': allow_entry and not self.daily_dd_halt,
            'active_positions': self._get_concurrent_position_count()
        }
