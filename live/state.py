# =========================================================
# 상태 저장/복구 모듈
# 봇 재시작 시 포지션 및 상태 복원
# =========================================================

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 기본 상태 저장 경로
DEFAULT_STATE_DIR = "state"
DEFAULT_STATE_FILE = "bot_state.json"


class StateManager:
    """
    봇 상태 저장/복구 관리자
    
    봇 재시작 시 포지션, 거래 기록, 설정 등을 복원합니다.
    """
    
    def __init__(self, state_dir: str = DEFAULT_STATE_DIR,
                 state_file: str = DEFAULT_STATE_FILE):
        """
        Args:
            state_dir: 상태 저장 디렉토리
            state_file: 상태 파일 이름
        """
        self.state_dir = state_dir
        self.state_file = state_file
        self.state_path = os.path.join(state_dir, state_file)
        
        # 상태 디렉토리 생성
        os.makedirs(state_dir, exist_ok=True)
    
    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        상태 저장
        
        Args:
            state: 저장할 상태 딕셔너리
        
        Returns:
            성공 여부
        """
        try:
            # 저장 시간 추가
            state['saved_at'] = datetime.now().isoformat()
            state['version'] = '1.0'
            
            # 백업 파일 생성
            if os.path.exists(self.state_path):
                backup_path = self.state_path + '.backup'
                try:
                    os.replace(self.state_path, backup_path)
                except Exception as e:
                    logger.warning(f"백업 파일 생성 실패: {e}")
            
            # JSON으로 저장
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False, default=str)
            
            logger.debug(f"상태 저장 완료: {self.state_path}")
            return True
            
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")
            return False
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        상태 로드
        
        Returns:
            저장된 상태 또는 None
        """
        try:
            if not os.path.exists(self.state_path):
                logger.info("저장된 상태 파일이 없습니다")
                return None
            
            with open(self.state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            logger.info(f"상태 로드 완료 (저장 시간: {state.get('saved_at', 'N/A')})")
            return state
            
        except json.JSONDecodeError as e:
            logger.error(f"상태 파일 파싱 실패: {e}")
            return self._try_load_backup()
            
        except Exception as e:
            logger.error(f"상태 로드 실패: {e}")
            return None
    
    def _try_load_backup(self) -> Optional[Dict[str, Any]]:
        """백업 파일에서 로드 시도"""
        backup_path = self.state_path + '.backup'
        
        if not os.path.exists(backup_path):
            return None
        
        try:
            logger.info("백업 파일에서 복구 시도...")
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            logger.info("백업 파일에서 복구 성공")
            return state
            
        except Exception as e:
            logger.error(f"백업 파일 복구 실패: {e}")
            return None
    
    def clear_state(self) -> bool:
        """
        저장된 상태 삭제
        
        Returns:
            성공 여부
        """
        try:
            if os.path.exists(self.state_path):
                os.remove(self.state_path)
                logger.info("상태 파일 삭제 완료")
            return True
        except Exception as e:
            logger.error(f"상태 파일 삭제 실패: {e}")
            return False
    
    def state_exists(self) -> bool:
        """저장된 상태 파일 존재 여부"""
        return os.path.exists(self.state_path)
    
    def get_state_info(self) -> Optional[Dict[str, Any]]:
        """상태 파일 정보 조회 (내용 로드 없이)"""
        if not os.path.exists(self.state_path):
            return None
        
        stat = os.stat(self.state_path)
        return {
            'path': self.state_path,
            'size_bytes': stat.st_size,
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }


class BotState:
    """
    봇 상태 구조체
    
    저장/복원할 상태 정보를 구조화합니다.
    """
    
    def __init__(self):
        # 포지션 정보
        self.positions: Dict[str, dict] = {}
        
        # 거래 기록
        self.trade_history: list = []
        
        # 자본 정보
        self.initial_capital: float = 0.0
        self.current_capital: float = 0.0
        
        # 일일 추적
        self.daily_high_watermark: float = 0.0
        self.current_day: Optional[str] = None
        self.daily_loss_count: int = 0
        
        # 봇 상태
        self.is_running: bool = False
        self.safe_mode: bool = False
        self.start_time: Optional[str] = None
        self.last_candle_time: Optional[int] = None
        
        # 전략 상태
        self.strategy_states: Dict[str, dict] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'positions': self.positions,
            'trade_history': self.trade_history,
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'daily_high_watermark': self.daily_high_watermark,
            'current_day': self.current_day,
            'daily_loss_count': self.daily_loss_count,
            'is_running': self.is_running,
            'safe_mode': self.safe_mode,
            'start_time': self.start_time,
            'last_candle_time': self.last_candle_time,
            'strategy_states': self.strategy_states
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotState':
        """딕셔너리에서 생성"""
        state = cls()
        state.positions = data.get('positions', {})
        state.trade_history = data.get('trade_history', [])
        state.initial_capital = data.get('initial_capital', 0.0)
        state.current_capital = data.get('current_capital', 0.0)
        state.daily_high_watermark = data.get('daily_high_watermark', 0.0)
        state.current_day = data.get('current_day')
        state.daily_loss_count = data.get('daily_loss_count', 0)
        state.is_running = data.get('is_running', False)
        state.safe_mode = data.get('safe_mode', False)
        state.start_time = data.get('start_time')
        state.last_candle_time = data.get('last_candle_time')
        state.strategy_states = data.get('strategy_states', {})
        return state
    
    def update_from_position_manager(self, position_manager):
        """PositionManager에서 포지션 정보 업데이트"""
        self.positions = position_manager.get_positions_dict()
        self.trade_history = position_manager.get_trade_history()
    
    def update_daily_tracking(self, capital: float):
        """일일 추적 정보 업데이트"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self.current_day != today:
            # 새로운 날
            self.current_day = today
            self.daily_high_watermark = capital
            self.daily_loss_count = 0
        
        if capital > self.daily_high_watermark:
            self.daily_high_watermark = capital
        
        self.current_capital = capital
