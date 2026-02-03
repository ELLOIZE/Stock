# =========================================================
# 주문 실행 모듈
# Market Order 진입/청산
# =========================================================

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from live.client import BinanceFuturesClient

logger = logging.getLogger(__name__)


class OrderManager:
    """
    주문 실행 관리자
    
    시장가 주문을 통한 진입/청산을 담당합니다.
    """
    
    def __init__(self, client: BinanceFuturesClient, symbol: str = 'BTCUSDT'):
        """
        Args:
            client: Binance Futures 클라이언트
            symbol: 심볼 (예: BTCUSDT)
        """
        self.client = client
        self.symbol = symbol
        
        # 주문 기록
        self._order_history: list = []
        
        # 심볼 정보 캐시
        self._symbol_info: Optional[dict] = None
        
        # 드라이런 모드
        self._dry_run = False
    
    def initialize(self, leverage: int = 1, dry_run: bool = False) -> bool:
        """
        초기화 - 레버리지 설정 및 심볼 정보 로드
        
        Args:
            leverage: 레버리지 배수
            dry_run: 드라이런 모드 (True면 레버리지/마진 설정 스킵)
        
        Returns:
            성공 여부
        """
        self._dry_run = dry_run
        
        try:
            # 심볼 정보 로드 (public API - 드라이런에서도 필요)
            self._symbol_info = self.client.get_symbol_info(self.symbol)
            if not self._symbol_info:
                logger.error(f"심볼 정보를 찾을 수 없습니다: {self.symbol}")
                return False
            
            # 드라이런 모드에서는 레버리지/마진 설정 스킵
            if dry_run:
                logger.info(f"드라이런 모드 - 레버리지/마진 설정 스킵 (가정: {leverage}x)")
                return True
            
            # 레버리지 설정
            result = self.client.set_leverage(self.symbol, leverage)
            logger.info(f"레버리지 설정: {leverage}x")
            
            # 마진 타입 설정 (CROSSED)
            try:
                self.client.set_margin_type(self.symbol, 'CROSSED')
                logger.info("마진 타입 설정: CROSSED")
            except Exception as e:
                # 이미 설정된 경우 무시
                logger.debug(f"마진 타입 설정 스킵: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"OrderManager 초기화 실패: {e}")
            return False
    
    def calculate_quantity(self, usdt_amount: float, price: float) -> float:
        """
        USDT 금액으로 수량 계산
        
        Args:
            usdt_amount: USDT 금액
            price: 현재가
        
        Returns:
            수량 (LOT_SIZE 규칙에 맞춤)
        """
        if not self._symbol_info:
            logger.error("심볼 정보가 없습니다")
            return 0.0
        
        # LOT_SIZE 필터 찾기
        lot_size_filter = None
        for f in self._symbol_info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                lot_size_filter = f
                break
        
        if not lot_size_filter:
            logger.error("LOT_SIZE 필터를 찾을 수 없습니다")
            return 0.0
        
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])
        
        # 수량 계산
        raw_qty = usdt_amount / price
        
        # step_size에 맞춤
        precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
        qty = round(raw_qty - (raw_qty % step_size), precision)
        
        # 최소 수량 체크
        if qty < min_qty:
            logger.warning(f"계산된 수량({qty})이 최소 수량({min_qty})보다 작습니다")
            return 0.0
        
        return qty
    
    def validate_order(self, quantity: float, price: float) -> bool:
        """
        주문 유효성 검사
        
        Args:
            quantity: 수량
            price: 가격
        
        Returns:
            유효 여부
        """
        if not self._symbol_info:
            return False
        
        for f in self._symbol_info.get('filters', []):
            filter_type = f['filterType']
            
            if filter_type == 'LOT_SIZE':
                min_qty = float(f['minQty'])
                max_qty = float(f['maxQty'])
                if quantity < min_qty or quantity > max_qty:
                    logger.error(f"수량 범위 초과: {quantity} (min: {min_qty}, max: {max_qty})")
                    return False
            
            elif filter_type == 'MIN_NOTIONAL':
                min_notional = float(f.get('notional', f.get('minNotional', 0)))
                notional = quantity * price
                if notional < min_notional:
                    logger.error(f"최소 주문 금액 미달: ${notional:.2f} < ${min_notional}")
                    return False
        
        return True
    
    def place_market_buy(self, quantity: float) -> Optional[Dict[str, Any]]:
        """
        시장가 매수 주문
        
        Args:
            quantity: 수량
        
        Returns:
            주문 결과 또는 None
        """
        if self._dry_run:
            # 드라이런 모드: 가상 주문 생성
            order = {
                'orderId': f"DRY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'symbol': self.symbol,
                'side': 'BUY',
                'type': 'MARKET',
                'origQty': str(quantity),
                'executedQty': str(quantity),
                'avgPrice': '0',  # 실제 가격은 나중에 설정
                'status': 'FILLED',
                'dry_run': True
            }
            self._order_history.append(order)
            logger.info(f"[드라이런] 시장가 매수: {quantity} {self.symbol}")
            return order
        
        try:
            order = self.client.market_order(
                symbol=self.symbol,
                side='BUY',
                quantity=quantity
            )
            
            if order:
                self._order_history.append(order)
                avg_price = float(order.get('avgPrice', 0))
                logger.info(f"시장가 매수 완료: {quantity} @ {avg_price}")
            
            return order
            
        except Exception as e:
            logger.error(f"시장가 매수 실패: {e}")
            return None
    
    def place_market_sell(self, quantity: float, reduce_only: bool = True) -> Optional[Dict[str, Any]]:
        """
        시장가 매도 주문 (포지션 청산)
        
        Args:
            quantity: 수량
            reduce_only: 포지션 축소 전용
        
        Returns:
            주문 결과 또는 None
        """
        if self._dry_run:
            # 드라이런 모드: 가상 주문 생성
            order = {
                'orderId': f"DRY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'symbol': self.symbol,
                'side': 'SELL',
                'type': 'MARKET',
                'origQty': str(quantity),
                'executedQty': str(quantity),
                'avgPrice': '0',
                'status': 'FILLED',
                'reduceOnly': reduce_only,
                'dry_run': True
            }
            self._order_history.append(order)
            logger.info(f"[드라이런] 시장가 매도: {quantity} {self.symbol}")
            return order
        
        try:
            order = self.client.market_order(
                symbol=self.symbol,
                side='SELL',
                quantity=quantity,
                reduce_only=reduce_only
            )
            
            if order:
                self._order_history.append(order)
                avg_price = float(order.get('avgPrice', 0))
                logger.info(f"시장가 매도 완료: {quantity} @ {avg_price}")
            
            return order
            
        except Exception as e:
            logger.error(f"시장가 매도 실패: {e}")
            return None
    
    def close_all_positions(self) -> Optional[Dict[str, Any]]:
        """
        모든 포지션 청산 (긴급용)
        
        Returns:
            청산 결과 또는 None
        """
        if self._dry_run:
            logger.info("[드라이런] 전체 포지션 청산 시뮬레이션")
            return {'status': 'simulated', 'dry_run': True}
        
        try:
            # 현재 포지션 확인
            position = self.client.get_open_position(self.symbol)
            if not position:
                logger.info("청산할 포지션이 없습니다")
                return None
            
            position_amt = float(position.get('positionAmt', 0))
            if position_amt == 0:
                return None
            
            # 롱 포지션이면 매도로 청산
            if position_amt > 0:
                return self.place_market_sell(abs(position_amt), reduce_only=True)
            # 숏 포지션이면 매수로 청산
            else:
                return self.place_market_buy(abs(position_amt))
                
        except Exception as e:
            logger.error(f"전체 청산 실패: {e}")
            return None
    
    def get_order_history(self) -> list:
        """주문 기록 반환"""
        return self._order_history.copy()
    
    def get_symbol_info(self) -> Optional[dict]:
        """심볼 정보 반환"""
        return self._symbol_info
