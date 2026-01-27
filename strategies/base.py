# =========================================================
# 전략 베이스 클래스
# =========================================================

from abc import ABC, abstractmethod


class Strategy(ABC):
    """모든 전략의 부모 클래스 (설계도)"""
    
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def check_entry(self, df, i):
        """
        진입 신호 확인
        
        Args:
            df: 전체 데이터프레임
            i: 현재 인덱스
        
        Returns:
            bool: 진입 여부
        """
        pass

    @abstractmethod
    def check_exit(self, row, entry_price, entry_sl, atr):
        """
        청산 신호 확인
        
        Args:
            row: 현재 캔들 데이터
            entry_price: 진입 가격
            entry_sl: 현재 손절가
            atr: ATR 값
        
        Returns:
            tuple: (새로운 손절가, 청산 사유 또는 None)
        """
        pass
    
    @abstractmethod
    def get_stop_loss_dist(self, row):
        """
        진입 시 손절폭 계산
        
        Args:
            row: 현재 캔들 데이터
        
        Returns:
            float: 손절폭
        """
        pass
