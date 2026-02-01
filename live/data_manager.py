# =========================================================
# 실시간 데이터 관리자
# WebSocket으로 캔들 수신 + 지표 계산
# =========================================================

import logging
import threading
from datetime import datetime
from typing import Optional, Callable, List

import pandas as pd

from live.client import BinanceFuturesClient
from data.features import compute_indicators

logger = logging.getLogger(__name__)


class DataManager:
    """
    실시간 데이터 관리자
    
    WebSocket을 통해 실시간 캔들 데이터를 수신하고,
    지표를 계산하여 DataFrame으로 제공합니다.
    """
    
    def __init__(self, client: BinanceFuturesClient, symbol: str = 'BTCUSDT',
                 interval: str = '5m', buffer_size: int = 500):
        """
        Args:
            client: Binance Futures 클라이언트
            symbol: 심볼 (예: BTCUSDT)
            interval: 캔들 인터벌 (예: 5m)
            buffer_size: 메모리에 유지할 캔들 수
        """
        self.client = client
        self.symbol = symbol
        self.interval = interval
        self.buffer_size = buffer_size
        
        # 데이터 저장
        self._df: Optional[pd.DataFrame] = None
        self._lock = threading.Lock()
        
        # 콜백
        self._on_candle_close: Optional[Callable] = None
        
        # 마지막 캔들 정보
        self._last_candle_time: Optional[int] = None
        self._current_candle: Optional[dict] = None
    
    def initialize(self) -> bool:
        """
        초기화 - REST API로 과거 캔들 로드
        
        Returns:
            성공 여부
        """
        try:
            logger.info(f"과거 캔들 데이터 로드 중... ({self.symbol}, {self.interval})")
            
            # REST API로 과거 캔들 가져오기
            klines = self.client.get_klines(self.symbol, self.interval, self.buffer_size)
            
            if not klines:
                logger.error("캔들 데이터를 가져올 수 없습니다")
                return False
            
            # DataFrame 변환
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # 타입 변환
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # 마지막 미완성 캔들 제외 (현재 진행 중인 캔들)
            df = df.iloc[:-1].reset_index(drop=True)
            
            # 지표 계산
            df = compute_indicators(df)
            
            with self._lock:
                self._df = df
                if len(df) > 0:
                    self._last_candle_time = int(df.iloc[-1]['timestamp'].timestamp() * 1000)
            
            logger.info(f"초기화 완료: {len(df)}개 캔들 로드")
            return True
            
        except Exception as e:
            logger.error(f"데이터 초기화 실패: {e}")
            return False
    
    def start_stream(self, on_candle_close: Callable = None):
        """
        실시간 스트림 시작
        
        Args:
            on_candle_close: 캔들 완성 시 호출될 콜백 (df, index)
        """
        self._on_candle_close = on_candle_close
        
        # WebSocket 시작
        if not self.client.is_connected():
            if not self.client.start_websocket():
                logger.error("WebSocket 연결 실패")
                return False
        
        # 캔들 스트림 구독
        self.client.subscribe_kline(self.symbol, self.interval, self._handle_kline)
        logger.info(f"실시간 스트림 시작: {self.symbol} {self.interval}")
        return True
    
    def _handle_kline(self, data: dict):
        """WebSocket 캔들 데이터 처리"""
        try:
            kline = data.get('k', {})
            
            is_closed = kline.get('x', False)  # 캔들 완성 여부
            
            # 현재 캔들 정보 업데이트
            self._current_candle = {
                'timestamp': kline['t'],
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v'])
            }
            
            # 캔들이 완성되면 DataFrame에 추가
            if is_closed:
                self._add_candle(self._current_candle)
                
        except Exception as e:
            logger.error(f"캔들 처리 오류: {e}")
    
    def _add_candle(self, candle: dict):
        """완성된 캔들을 DataFrame에 추가"""
        with self._lock:
            if self._df is None:
                logger.warning("DataFrame이 초기화되지 않았습니다")
                return
            
            # 중복 체크
            if self._last_candle_time and candle['timestamp'] <= self._last_candle_time:
                return
            
            # 새 캔들 추가
            new_row = pd.DataFrame([{
                'timestamp': pd.to_datetime(candle['timestamp'], unit='ms'),
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'volume': candle['volume']
            }])
            
            self._df = pd.concat([self._df, new_row], ignore_index=True)
            
            # 버퍼 크기 유지
            if len(self._df) > self.buffer_size:
                self._df = self._df.iloc[-self.buffer_size:].reset_index(drop=True)
            
            # 지표 재계산
            self._df = compute_indicators(self._df)
            
            self._last_candle_time = candle['timestamp']
            
            logger.info(f"새 캔들 추가: {candle['timestamp']} | Close: {candle['close']:.2f}")
        
        # 콜백 호출
        if self._on_candle_close:
            try:
                self._on_candle_close(self.get_dataframe(), len(self._df) - 1)
            except Exception as e:
                logger.error(f"캔들 콜백 오류: {e}")
    
    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """현재 DataFrame 복사본 반환"""
        with self._lock:
            if self._df is None:
                return None
            return self._df.copy()
    
    def get_latest_row(self) -> Optional[pd.Series]:
        """최신 캔들 데이터 반환"""
        with self._lock:
            if self._df is None or len(self._df) == 0:
                return None
            return self._df.iloc[-1].copy()
    
    def get_current_price(self) -> float:
        """현재가 반환 (실시간 캔들 기준)"""
        if self._current_candle:
            return self._current_candle['close']
        
        latest = self.get_latest_row()
        if latest is not None:
            return latest['close']
        
        return 0.0
    
    def get_current_atr(self) -> float:
        """현재 ATR 반환"""
        latest = self.get_latest_row()
        if latest is not None and 'atr' in latest:
            return latest['atr']
        return 0.0
    
    def stop_stream(self):
        """스트림 중지"""
        self.client.stop_websocket()
        logger.info("실시간 스트림 중지")
    
    def sync_with_exchange(self) -> bool:
        """
        거래소와 데이터 동기화 (재연결 시 사용)
        
        Returns:
            성공 여부
        """
        try:
            logger.info("거래소와 데이터 동기화 중...")
            
            # 최근 캔들 가져오기
            klines = self.client.get_klines(self.symbol, self.interval, 50)
            
            if not klines:
                return False
            
            with self._lock:
                if self._df is None:
                    return False
                
                # 마지막 캔들 시간 이후의 캔들만 추가
                for kline in klines[:-1]:  # 마지막 미완성 캔들 제외
                    candle_time = kline[0]
                    if self._last_candle_time and candle_time <= self._last_candle_time:
                        continue
                    
                    new_row = pd.DataFrame([{
                        'timestamp': pd.to_datetime(candle_time, unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    }])
                    
                    self._df = pd.concat([self._df, new_row], ignore_index=True)
                    self._last_candle_time = candle_time
                
                # 버퍼 크기 유지
                if len(self._df) > self.buffer_size:
                    self._df = self._df.iloc[-self.buffer_size:].reset_index(drop=True)
                
                # 지표 재계산
                self._df = compute_indicators(self._df)
            
            logger.info("동기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"동기화 실패: {e}")
            return False
