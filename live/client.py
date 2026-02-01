# =========================================================
# Binance Futures API 클라이언트
# REST API + WebSocket 통합
# =========================================================

import time
import json
import hmac
import hashlib
import logging
import threading
from urllib.parse import urlencode
from typing import Optional, Callable, Dict, Any, List

import requests
import websocket

from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """
    Binance Futures (USDT-M) API 클라이언트
    
    REST API와 WebSocket을 통합하여 제공합니다.
    """
    
    # API 엔드포인트
    REST_BASE_URL = "https://fapi.binance.com"
    WS_BASE_URL = "wss://fstream.binance.com/ws"
    
    def __init__(self):
        self.api_key = BINANCE_API_KEY
        self.api_secret = BINANCE_API_SECRET
        
        # WebSocket 관련
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_connected = False
        self._ws_callbacks: Dict[str, Callable] = {}
        self._reconnect_count = 0
        self._max_reconnects = 10
        self._should_reconnect = True
        
        # 세션
        self._session = requests.Session()
        self._session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })
    
    # =========================================================
    # REST API - 서명 및 요청
    # =========================================================
    
    def _generate_signature(self, params: dict) -> str:
        """HMAC SHA256 서명 생성"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """REST API 요청"""
        url = f"{self.REST_BASE_URL}{endpoint}"
        params = params or {}
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            if method == 'GET':
                response = self._session.get(url, params=params, timeout=10)
            elif method == 'POST':
                response = self._session.post(url, params=params, timeout=10)
            elif method == 'DELETE':
                response = self._session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {endpoint} - {e}")
            raise
    
    # =========================================================
    # REST API - 계좌 정보
    # =========================================================
    
    def get_account_info(self) -> dict:
        """계좌 정보 조회"""
        return self._request('GET', '/fapi/v2/account', signed=True)
    
    def get_balance(self) -> List[dict]:
        """잔고 조회"""
        return self._request('GET', '/fapi/v2/balance', signed=True)
    
    def get_usdt_balance(self) -> float:
        """USDT 잔고 조회"""
        balances = self.get_balance()
        for b in balances:
            if b['asset'] == 'USDT':
                return float(b['availableBalance'])
        return 0.0
    
    def get_position_info(self, symbol: str = None) -> List[dict]:
        """포지션 정보 조회"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/fapi/v2/positionRisk', params, signed=True)
    
    def get_open_position(self, symbol: str) -> Optional[dict]:
        """특정 심볼의 열린 포지션 조회"""
        positions = self.get_position_info(symbol)
        for pos in positions:
            if pos['symbol'] == symbol and float(pos['positionAmt']) != 0:
                return pos
        return None
    
    # =========================================================
    # REST API - 주문
    # =========================================================
    
    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """레버리지 설정"""
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._request('POST', '/fapi/v1/leverage', params, signed=True)
    
    def set_margin_type(self, symbol: str, margin_type: str = 'CROSSED') -> dict:
        """마진 타입 설정 (CROSSED/ISOLATED)"""
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        try:
            return self._request('POST', '/fapi/v1/marginType', params, signed=True)
        except requests.exceptions.HTTPError as e:
            # 이미 설정된 마진 타입이면 무시
            if 'No need to change margin type' in str(e):
                return {'msg': 'Already set'}
            raise
    
    def market_order(self, symbol: str, side: str, quantity: float, 
                     reduce_only: bool = False) -> dict:
        """
        시장가 주문
        
        Args:
            symbol: 심볼 (예: BTCUSDT)
            side: BUY 또는 SELL
            quantity: 수량
            reduce_only: 청산 전용 여부
        
        Returns:
            주문 결과
        """
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': 'MARKET',
            'quantity': quantity
        }
        
        if reduce_only:
            params['reduceOnly'] = 'true'
        
        logger.info(f"주문 실행: {side} {quantity} {symbol}")
        result = self._request('POST', '/fapi/v1/order', params, signed=True)
        logger.info(f"주문 결과: orderId={result.get('orderId')}, status={result.get('status')}")
        
        return result
    
    def get_order_status(self, symbol: str, order_id: int) -> dict:
        """주문 상태 조회"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        return self._request('GET', '/fapi/v1/order', params, signed=True)
    
    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """주문 취소"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        return self._request('DELETE', '/fapi/v1/order', params, signed=True)
    
    def cancel_all_orders(self, symbol: str) -> dict:
        """특정 심볼의 모든 주문 취소"""
        params = {'symbol': symbol}
        return self._request('DELETE', '/fapi/v1/allOpenOrders', params, signed=True)
    
    # =========================================================
    # REST API - 시장 데이터
    # =========================================================
    
    def get_klines(self, symbol: str, interval: str = '5m', limit: int = 500) -> List[list]:
        """
        캔들 데이터 조회
        
        Returns:
            [[timestamp, open, high, low, close, volume, ...], ...]
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._request('GET', '/fapi/v1/klines', params)
    
    def get_ticker_price(self, symbol: str) -> float:
        """현재가 조회"""
        params = {'symbol': symbol}
        result = self._request('GET', '/fapi/v1/ticker/price', params)
        return float(result['price'])
    
    def get_exchange_info(self, symbol: str = None) -> dict:
        """거래소 정보 조회 (최소 주문 단위 등)"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/fapi/v1/exchangeInfo', params)
    
    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """특정 심볼 정보 조회"""
        info = self.get_exchange_info()
        for s in info.get('symbols', []):
            if s['symbol'] == symbol:
                return s
        return None
    
    # =========================================================
    # WebSocket - 연결 관리
    # =========================================================
    
    def _on_ws_open(self, ws):
        """WebSocket 연결 성공"""
        self._ws_connected = True
        self._reconnect_count = 0
        logger.info("WebSocket 연결 성공")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료"""
        self._ws_connected = False
        logger.warning(f"WebSocket 연결 종료: {close_status_code} - {close_msg}")
        
        if self._should_reconnect and self._reconnect_count < self._max_reconnects:
            self._reconnect_count += 1
            wait_time = min(self._reconnect_count * 2, 30)
            logger.info(f"WebSocket 재연결 시도 {self._reconnect_count}/{self._max_reconnects} ({wait_time}초 후)")
            time.sleep(wait_time)
            self._start_ws_internal()
    
    def _on_ws_error(self, ws, error):
        """WebSocket 에러"""
        logger.error(f"WebSocket 에러: {error}")
    
    def _on_ws_message(self, ws, message):
        """WebSocket 메시지 수신"""
        try:
            data = json.loads(message)
            event_type = data.get('e', '')
            
            # 콜백 호출
            if event_type in self._ws_callbacks:
                self._ws_callbacks[event_type](data)
            elif 'default' in self._ws_callbacks:
                self._ws_callbacks['default'](data)
                
        except json.JSONDecodeError as e:
            logger.error(f"WebSocket 메시지 파싱 실패: {e}")
    
    def _start_ws_internal(self):
        """WebSocket 내부 시작"""
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
        
        self._ws = websocket.WebSocketApp(
            self.WS_BASE_URL,
            on_open=self._on_ws_open,
            on_close=self._on_ws_close,
            on_error=self._on_ws_error,
            on_message=self._on_ws_message
        )
        
        self._ws_thread = threading.Thread(target=self._ws.run_forever)
        self._ws_thread.daemon = True
        self._ws_thread.start()
    
    def start_websocket(self):
        """WebSocket 시작"""
        self._should_reconnect = True
        self._start_ws_internal()
        
        # 연결 대기
        for _ in range(50):  # 5초 대기
            if self._ws_connected:
                return True
            time.sleep(0.1)
        
        logger.error("WebSocket 연결 타임아웃")
        return False
    
    def stop_websocket(self):
        """WebSocket 중지"""
        self._should_reconnect = False
        if self._ws:
            self._ws.close()
        self._ws_connected = False
    
    def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """
        캔들 스트림 구독
        
        Args:
            symbol: 심볼 (소문자, 예: btcusdt)
            interval: 인터벌 (예: 5m)
            callback: 콜백 함수 (data: dict)
        """
        self._ws_callbacks['kline'] = callback
        
        stream = f"{symbol.lower()}@kline_{interval}"
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }
        
        if self._ws and self._ws_connected:
            self._ws.send(json.dumps(subscribe_msg))
            logger.info(f"캔들 스트림 구독: {stream}")
        else:
            logger.error("WebSocket이 연결되지 않았습니다")
    
    def is_connected(self) -> bool:
        """WebSocket 연결 상태 확인"""
        return self._ws_connected
    
    # =========================================================
    # 유틸리티
    # =========================================================
    
    def ping(self) -> bool:
        """API 연결 테스트"""
        try:
            self._request('GET', '/fapi/v1/ping')
            return True
        except:
            return False
    
    def get_server_time(self) -> int:
        """서버 시간 조회 (밀리초)"""
        result = self._request('GET', '/fapi/v1/time')
        return result['serverTime']
    
    def round_quantity(self, symbol: str, quantity: float) -> float:
        """수량을 심볼의 최소 단위로 반올림"""
        info = self.get_symbol_info(symbol)
        if not info:
            return round(quantity, 3)
        
        for f in info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                precision = len(str(step_size).rstrip('0').split('.')[-1])
                return round(quantity - (quantity % step_size), precision)
        
        return round(quantity, 3)
    
    def round_price(self, symbol: str, price: float) -> float:
        """가격을 심볼의 최소 단위로 반올림"""
        info = self.get_symbol_info(symbol)
        if not info:
            return round(price, 2)
        
        for f in info.get('filters', []):
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
                precision = len(str(tick_size).rstrip('0').split('.')[-1])
                return round(price - (price % tick_size), precision)
        
        return round(price, 2)
