# =========================================================
# 포지션 관리자
# 트레일링 스탑, 부분 청산 처리
# =========================================================

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd

from live.client import BinanceFuturesClient
from live.order_manager import OrderManager
from strategies.base import Strategy

logger = logging.getLogger(__name__)


class Position:
    """포지션 정보 클래스"""
    
    def __init__(self, strategy_name: str, entry_price: float, quantity: float,
                 stop_loss: float, entry_time: datetime, entry_index: int):
        self.strategy_name = strategy_name
        self.entry_price = entry_price
        self.original_quantity = quantity
        self.remaining_quantity = quantity
        self.stop_loss = stop_loss
        self.entry_time = entry_time
        self.entry_index = entry_index
        self.partial_exits: List[Dict] = []
        self.candles_held = 0
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환 (상태 저장용)"""
        return {
            'strategy_name': self.strategy_name,
            'entry_price': self.entry_price,
            'original_quantity': self.original_quantity,
            'remaining_quantity': self.remaining_quantity,
            'stop_loss': self.stop_loss,
            'entry_time': self.entry_time.isoformat() if isinstance(self.entry_time, datetime) else self.entry_time,
            'entry_index': self.entry_index,
            'partial_exits': self.partial_exits,
            'candles_held': self.candles_held
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """딕셔너리에서 생성"""
        entry_time = data['entry_time']
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        
        pos = cls(
            strategy_name=data['strategy_name'],
            entry_price=data['entry_price'],
            quantity=data['original_quantity'],
            stop_loss=data['stop_loss'],
            entry_time=entry_time,
            entry_index=data['entry_index']
        )
        pos.remaining_quantity = data['remaining_quantity']
        pos.partial_exits = data.get('partial_exits', [])
        pos.candles_held = data.get('candles_held', 0)
        return pos


class PositionManager:
    """
    포지션 관리자
    
    활성 포지션 추적, 트레일링 스탑, 부분 청산을 담당합니다.
    """
    
    def __init__(self, client: BinanceFuturesClient, order_manager: OrderManager):
        """
        Args:
            client: Binance Futures 클라이언트
            order_manager: 주문 실행 관리자
        """
        self.client = client
        self.order_manager = order_manager
        
        # 전략별 활성 포지션
        self._positions: Dict[str, Position] = {}
        
        # 청산된 거래 기록
        self._trade_history: List[Dict] = []
        
        # 전략 객체 참조
        self._strategies: Dict[str, Strategy] = {}
    
    def register_strategy(self, strategy: Strategy):
        """전략 등록"""
        self._strategies[strategy.name] = strategy
        logger.info(f"전략 등록: {strategy.name}")
    
    def has_position(self, strategy_name: str) -> bool:
        """특정 전략의 포지션 존재 여부"""
        return strategy_name in self._positions and self._positions[strategy_name] is not None
    
    def get_position(self, strategy_name: str) -> Optional[Position]:
        """특정 전략의 포지션 조회"""
        return self._positions.get(strategy_name)
    
    def get_all_positions(self) -> Dict[str, Position]:
        """모든 활성 포지션 조회"""
        return {k: v for k, v in self._positions.items() if v is not None}
    
    def get_position_count(self) -> int:
        """활성 포지션 수"""
        return sum(1 for p in self._positions.values() if p is not None)
    
    def open_position(self, strategy_name: str, entry_price: float,
                      quantity: float, stop_loss: float, 
                      entry_index: int) -> Optional[Position]:
        """
        새 포지션 열기
        
        Args:
            strategy_name: 전략 이름
            entry_price: 진입가
            quantity: 수량
            stop_loss: 손절가
            entry_index: 진입 캔들 인덱스
        
        Returns:
            생성된 포지션 또는 None
        """
        if self.has_position(strategy_name):
            logger.warning(f"{strategy_name} 포지션이 이미 존재합니다")
            return None
        
        # 주문 실행
        order_result = self.order_manager.place_market_buy(quantity)
        if not order_result:
            logger.error(f"{strategy_name} 진입 주문 실패")
            return None
        
        # 실제 체결가로 포지션 생성 (Binance API 응답 형식)
        actual_price = float(order_result.get('avgPrice', 0)) or entry_price
        actual_qty = float(order_result.get('executedQty', quantity))
        
        position = Position(
            strategy_name=strategy_name,
            entry_price=actual_price,
            quantity=actual_qty,
            stop_loss=stop_loss,
            entry_time=datetime.now(),
            entry_index=entry_index
        )
        
        self._positions[strategy_name] = position
        
        logger.info(f"포지션 생성: {strategy_name} | 진입: {actual_price:.2f} | 수량: {actual_qty} | SL: {stop_loss:.2f}")
        
        return position
    
    def close_position(self, strategy_name: str, exit_price: float,
                       exit_reason: str, partial_pct: float = None) -> Optional[Dict]:
        """
        포지션 청산 (전체 또는 부분)
        
        Args:
            strategy_name: 전략 이름
            exit_price: 청산가
            exit_reason: 청산 사유
            partial_pct: 부분 청산 비율 (None이면 전체 청산)
        
        Returns:
            청산 결과
        """
        position = self.get_position(strategy_name)
        if not position:
            logger.warning(f"{strategy_name} 포지션이 없습니다")
            return None
        
        # 청산 수량 계산
        if partial_pct is not None:
            close_qty = position.remaining_quantity * partial_pct
            is_partial = True
        else:
            close_qty = position.remaining_quantity
            is_partial = False
        
        # 주문 실행
        order_result = self.order_manager.place_market_sell(close_qty, reduce_only=True)
        if not order_result:
            logger.error(f"{strategy_name} 청산 주문 실패")
            return None
        
        actual_price = float(order_result.get('avgPrice', 0)) or exit_price
        actual_qty = float(order_result.get('executedQty', close_qty))
        
        # 손익 계산
        pnl = (actual_price - position.entry_price) * actual_qty
        pnl_pct = (actual_price / position.entry_price - 1) * 100
        
        # 거래 기록
        trade_record = {
            'strategy': strategy_name,
            'entry_time': position.entry_time.isoformat(),
            'exit_time': datetime.now().isoformat(),
            'entry_price': position.entry_price,
            'exit_price': actual_price,
            'quantity': actual_qty,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'is_partial': is_partial,
            'candles_held': position.candles_held
        }
        
        self._trade_history.append(trade_record)
        
        if is_partial:
            # 부분 청산
            position.remaining_quantity -= actual_qty
            position.partial_exits.append(trade_record)
            
            logger.info(f"부분 청산: {strategy_name} | {exit_reason} | "
                       f"수량: {actual_qty:.6f} | 잔여: {position.remaining_quantity:.6f} | "
                       f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
            
            # 잔여 수량이 거의 없으면 포지션 종료
            if position.remaining_quantity < position.original_quantity * 0.01:
                self._positions[strategy_name] = None
                logger.info(f"포지션 완전 종료: {strategy_name}")
        else:
            # 전체 청산
            self._positions[strategy_name] = None
            
            logger.info(f"포지션 청산: {strategy_name} | {exit_reason} | "
                       f"수량: {actual_qty:.6f} | PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
        
        return trade_record
    
    def check_exits(self, df: pd.DataFrame, current_index: int) -> List[Dict]:
        """
        모든 포지션의 청산 조건 체크
        
        Args:
            df: 캔들 데이터프레임
            current_index: 현재 캔들 인덱스
        
        Returns:
            청산된 거래 기록 리스트
        """
        closed_trades = []
        row = df.iloc[current_index]
        current_price = row['close']
        current_low = row['low']
        atr = row.get('atr', 0)
        
        for strategy_name, position in list(self._positions.items()):
            if position is None:
                continue
            
            # 캔들 보유 수 증가
            position.candles_held += 1
            
            # 전략 객체 가져오기
            strategy = self._strategies.get(strategy_name)
            if not strategy:
                continue
            
            # 거래 정보 구성
            trade_info = {
                'entry_time': position.entry_time,
                'candles_held': position.candles_held,
                'entry_price': position.entry_price
            }
            
            # 전략의 check_exit 호출
            exit_result = strategy.check_exit(
                row, position.entry_price, position.stop_loss, atr, trade_info
            )
            
            # 반환값 파싱
            if len(exit_result) == 3:
                new_sl, force_exit_reason, partial_close = exit_result
            else:
                new_sl, force_exit_reason = exit_result
                partial_close = None
            
            # 손절가 업데이트
            if new_sl > position.stop_loss:
                position.stop_loss = new_sl
                logger.debug(f"{strategy_name} SL 업데이트: {new_sl:.2f}")
            
            # 부분 청산 처리
            if partial_close is not None and partial_close > 0:
                trade = self.close_position(
                    strategy_name, current_price,
                    force_exit_reason or "PARTIAL_TP",
                    partial_pct=partial_close
                )
                if trade:
                    closed_trades.append(trade)
                
                # 포지션이 완전히 종료되었으면 다음으로
                if not self.has_position(strategy_name):
                    continue
            
            # 손절가 체크
            if current_low <= position.stop_loss:
                exit_reason = "Trailing_Win" if position.stop_loss > position.entry_price else "SL"
                trade = self.close_position(strategy_name, position.stop_loss, exit_reason)
                if trade:
                    closed_trades.append(trade)
                continue
            
            # 강제 청산 (전략에서 지정)
            if force_exit_reason and partial_close is None:
                trade = self.close_position(strategy_name, current_price, force_exit_reason)
                if trade:
                    closed_trades.append(trade)
        
        return closed_trades
    
    def sync_with_exchange(self, symbol: str) -> bool:
        """
        거래소와 포지션 동기화
        
        Returns:
            성공 여부
        """
        try:
            position = self.client.get_open_position(symbol)
            
            if not position:
                logger.info("거래소에 열린 포지션이 없습니다")
                return True
            
            position_amt = float(position['positionAmt'])
            entry_price = float(position['entryPrice'])
            
            if position_amt == 0:
                logger.info("포지션 크기가 0입니다")
                return True
            
            # 내부 상태와 비교
            total_internal = sum(
                p.remaining_quantity for p in self._positions.values() if p is not None
            )
            
            if abs(total_internal - position_amt) > 0.0001:
                logger.warning(f"포지션 불일치! 거래소: {position_amt}, 내부: {total_internal}")
                # 차이가 크면 경고만 하고 진행
            
            logger.info(f"포지션 동기화 완료: {position_amt} @ {entry_price}")
            return True
            
        except Exception as e:
            logger.error(f"포지션 동기화 실패: {e}")
            return False
    
    def emergency_close_all(self) -> bool:
        """
        긴급 전체 청산
        
        Returns:
            성공 여부
        """
        try:
            logger.warning("긴급 전체 청산 실행!")
            
            result = self.order_manager.close_all_positions()
            
            # 내부 상태 초기화
            for strategy_name in list(self._positions.keys()):
                if self._positions[strategy_name] is not None:
                    trade_record = {
                        'strategy': strategy_name,
                        'exit_time': datetime.now().isoformat(),
                        'exit_reason': 'EMERGENCY_CLOSE',
                        'is_partial': False
                    }
                    self._trade_history.append(trade_record)
                    self._positions[strategy_name] = None
            
            return True
            
        except Exception as e:
            logger.error(f"긴급 청산 실패: {e}")
            return False
    
    def get_trade_history(self) -> List[Dict]:
        """거래 기록 반환"""
        return self._trade_history.copy()
    
    def get_positions_dict(self) -> Dict[str, dict]:
        """포지션을 딕셔너리로 반환 (상태 저장용)"""
        return {
            k: v.to_dict() for k, v in self._positions.items() if v is not None
        }
    
    def restore_positions(self, positions_dict: Dict[str, dict]):
        """포지션 복원 (상태 로드용)"""
        for strategy_name, pos_data in positions_dict.items():
            self._positions[strategy_name] = Position.from_dict(pos_data)
            logger.info(f"포지션 복원: {strategy_name}")
