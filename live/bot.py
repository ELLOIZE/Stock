# =========================================================
# 메인 트레이딩 봇
# 전체 시스템 통합 및 실행 루프
# =========================================================

import os
import sys
import time
import signal
import logging
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import INITIAL_CAPITAL, STRATEGY_WEIGHTS, ENABLE_SHORT
from config.live_settings import (
    LIVE_STRATEGIES, LIVE_SYMBOL, LIVE_INTERVAL, LIVE_LEVERAGE,
    MAX_POSITION_USDT, DAILY_LOSS_LIMIT_PCT, MAX_CONCURRENT_POSITIONS,
    TOTAL_LOSS_LIMIT_PCT, CANDLE_BUFFER_SIZE, STATE_SAVE_INTERVAL,
    LOG_LEVEL, CONSOLE_OUTPUT, DRY_RUN_MODE, SYNC_ON_START
)
from live.client import BinanceFuturesClient
from live.data_manager import DataManager
from live.order_manager import OrderManager
from live.position_manager import PositionManager
from live.state import StateManager, BotState

from strategies import (BreakoutStrategy, MeanReversionStrategy, MomentumStrategy,
                         ShortBreakoutStrategy, ShortMeanReversionStrategy, ShortMomentumStrategy)

# =========================================================
# 로깅 설정
# =========================================================

def setup_logging():
    """로깅 설정"""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    if CONSOLE_OUTPUT:
        root_logger.addHandler(console_handler)
    
    return logging.getLogger('TradingBot')


logger = setup_logging()


class TradingBot:
    """
    라이브 트레이딩 봇
    
    실시간 데이터 수신, 전략 실행, 포지션 관리를 통합합니다.
    """
    
    def __init__(self):
        # 컴포넌트 초기화
        self.client: Optional[BinanceFuturesClient] = None
        self.data_manager: Optional[DataManager] = None
        self.order_manager: Optional[OrderManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.state_manager: Optional[StateManager] = None
        
        # 전략
        self.strategies: Dict[str, object] = {}
        
        # 상태
        self.bot_state = BotState()
        self.bot_state.initial_capital = INITIAL_CAPITAL
        self.bot_state.current_capital = INITIAL_CAPITAL
        
        # 플래그
        self.is_running = False
        self.safe_mode = False
        self._last_state_save = 0
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """종료 시그널 처리"""
        logger.info(f"종료 시그널 수신: {signum}")
        self.stop()
    
    def initialize(self) -> bool:
        """
        봇 초기화
        
        Returns:
            성공 여부
        """
        logger.info("=" * 60)
        logger.info("트레이딩 봇 초기화 시작")
        logger.info("=" * 60)
        
        try:
            # 1. API 클라이언트 초기화
            logger.info("API 클라이언트 초기화...")
            self.client = BinanceFuturesClient()
            
            if not self.client.ping():
                logger.error("Binance API 연결 실패")
                return False
            logger.info("API 연결 성공")
            
            # 2. 주문 관리자 초기화
            logger.info("주문 관리자 초기화...")
            self.order_manager = OrderManager(self.client, LIVE_SYMBOL)
            if not self.order_manager.initialize(LIVE_LEVERAGE, dry_run=DRY_RUN_MODE):
                logger.error("주문 관리자 초기화 실패")
                return False
            
            # 3. 포지션 관리자 초기화
            logger.info("포지션 관리자 초기화...")
            self.position_manager = PositionManager(self.client, self.order_manager)
            
            # 4. 전략 등록
            logger.info("전략 등록...")
            self._register_strategies()
            
            # 5. 데이터 관리자 초기화
            logger.info("데이터 관리자 초기화...")
            self.data_manager = DataManager(
                self.client, LIVE_SYMBOL, LIVE_INTERVAL, CANDLE_BUFFER_SIZE
            )
            if not self.data_manager.initialize():
                logger.error("데이터 관리자 초기화 실패")
                return False
            
            # 6. 상태 관리자 초기화
            logger.info("상태 관리자 초기화...")
            self.state_manager = StateManager()
            
            # 7. 이전 상태 복원 시도
            if self.state_manager.state_exists():
                self._restore_state()
            
            # 8. 거래소와 동기화
            if SYNC_ON_START:
                self._sync_with_exchange()
            
            # 9. 잔고 확인
            balance = self.client.get_usdt_balance()
            logger.info(f"USDT 잔고: ${balance:.2f}")
            
            logger.info("=" * 60)
            logger.info("봇 초기화 완료")
            logger.info(f"  - 심볼: {LIVE_SYMBOL}")
            logger.info(f"  - 인터벌: {LIVE_INTERVAL}")
            logger.info(f"  - 레버리지: {LIVE_LEVERAGE}x")
            logger.info(f"  - 활성 전략: {[k for k, v in LIVE_STRATEGIES.items() if v]}")
            logger.info(f"  - 최대 포지션: ${MAX_POSITION_USDT}")
            logger.info(f"  - 드라이런 모드: {DRY_RUN_MODE}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"초기화 실패: {e}", exc_info=True)
            return False
    
    def _register_strategies(self):
        """전략 등록"""
        if LIVE_STRATEGIES.get('BREAKOUT', False):
            strategy = BreakoutStrategy("BREAKOUT")
            self.strategies['BREAKOUT'] = strategy
            self.position_manager.register_strategy(strategy)
            logger.info("  - Breakout 전략 등록")
        
        if LIVE_STRATEGIES.get('MEAN_REV', False):
            strategy = MeanReversionStrategy("MEAN_REV")
            self.strategies['MEAN_REV'] = strategy
            self.position_manager.register_strategy(strategy)
            logger.info("  - Mean Reversion 전략 등록")
        
        if LIVE_STRATEGIES.get('MOMENTUM', False):
            strategy = MomentumStrategy("MOMENTUM")
            self.strategies['MOMENTUM'] = strategy
            self.position_manager.register_strategy(strategy)
            logger.info("  - Momentum 전략 등록")

        # 숏 전략 등록
        if ENABLE_SHORT:
            if LIVE_STRATEGIES.get('SHORT_BREAKOUT', False):
                strategy = ShortBreakoutStrategy("SHORT_BREAKOUT")
                self.strategies['SHORT_BREAKOUT'] = strategy
                self.position_manager.register_strategy(strategy)
                logger.info("  - Short Breakout 전략 등록")

            if LIVE_STRATEGIES.get('SHORT_MEAN_REV', False):
                strategy = ShortMeanReversionStrategy("SHORT_MEAN_REV")
                self.strategies['SHORT_MEAN_REV'] = strategy
                self.position_manager.register_strategy(strategy)
                logger.info("  - Short Mean Reversion 전략 등록")

            if LIVE_STRATEGIES.get('SHORT_MOMENTUM', False):
                strategy = ShortMomentumStrategy("SHORT_MOMENTUM")
                self.strategies['SHORT_MOMENTUM'] = strategy
                self.position_manager.register_strategy(strategy)
                logger.info("  - Short Momentum 전략 등록")

    def _restore_state(self):
        """이전 상태 복원"""
        try:
            state_data = self.state_manager.load_state()
            if state_data:
                self.bot_state = BotState.from_dict(state_data)
                
                # 포지션 복원
                if self.bot_state.positions:
                    self.position_manager.restore_positions(self.bot_state.positions)
                    logger.info(f"포지션 {len(self.bot_state.positions)}개 복원됨")
                
                logger.info("이전 상태 복원 완료")
        except Exception as e:
            logger.warning(f"상태 복원 실패: {e}")
    
    def _sync_with_exchange(self):
        """거래소와 동기화"""
        try:
            self.position_manager.sync_with_exchange(LIVE_SYMBOL)
        except Exception as e:
            logger.warning(f"거래소 동기화 실패: {e}")
    
    def start(self):
        """봇 시작"""
        if self.is_running:
            logger.warning("봇이 이미 실행 중입니다")
            return
        
        if not self.client:
            if not self.initialize():
                logger.error("초기화 실패로 봇을 시작할 수 없습니다")
                return
        
        self.is_running = True
        self.bot_state.is_running = True
        self.bot_state.start_time = datetime.now().isoformat()
        
        logger.info("봇 시작!")
        
        # 실시간 스트림 시작
        self.data_manager.start_stream(on_candle_close=self._on_candle_close)
        
        # 메인 루프
        try:
            while self.is_running:
                self._main_loop()
                time.sleep(1)
        except Exception as e:
            logger.error(f"메인 루프 오류: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _main_loop(self):
        """메인 루프 (1초마다 실행)"""
        current_time = time.time()
        
        # 상태 저장 (주기적)
        if current_time - self._last_state_save >= STATE_SAVE_INTERVAL:
            self._save_state()
            self._last_state_save = current_time
        
        # 연결 상태 체크
        if not self.client.is_connected():
            logger.warning("WebSocket 연결 끊김, 재연결 대기 중...")
            time.sleep(5)
            
            # 재연결 후 데이터 동기화
            if self.client.is_connected():
                self.data_manager.sync_with_exchange()
    
    def _on_candle_close(self, df: pd.DataFrame, current_index: int):
        """
        캔들 완성 시 호출되는 콜백
        
        Args:
            df: 캔들 데이터프레임
            current_index: 현재 캔들 인덱스
        """
        try:
            row = df.iloc[current_index]
            timestamp = row['timestamp']
            close_price = row['close']
            
            logger.info(f"캔들 완성: {timestamp} | Close: {close_price:.2f}")
            
            # Safe mode 체크
            if self.safe_mode:
                logger.warning("Safe mode 활성화 - 신규 진입 중단")
                # 청산만 체크
                self._check_exits(df, current_index)
                return
            
            # 일일 손실 한도 체크
            if self._check_daily_loss_limit():
                logger.warning("일일 손실 한도 도달 - 신규 진입 중단")
                self._check_exits(df, current_index)
                return
            
            # 1. 기존 포지션 청산 체크
            self._check_exits(df, current_index)
            
            # 2. 신규 진입 체크
            self._check_entries(df, current_index)
            
            # 상태 업데이트
            self.bot_state.last_candle_time = int(timestamp.timestamp() * 1000) if hasattr(timestamp, 'timestamp') else timestamp
            
        except Exception as e:
            logger.error(f"캔들 처리 오류: {e}", exc_info=True)
            self._enter_safe_mode("캔들 처리 오류")
    
    def _check_exits(self, df: pd.DataFrame, current_index: int):
        """청산 체크"""
        try:
            closed_trades = self.position_manager.check_exits(df, current_index)
            
            for trade in closed_trades:
                pnl = trade.get('pnl', 0)
                self.bot_state.current_capital += pnl
                
                if pnl < 0:
                    self.bot_state.daily_loss_count += 1
                
                logger.info(f"거래 완료: {trade.get('strategy')} | "
                           f"PnL: ${pnl:.2f} | "
                           f"사유: {trade.get('exit_reason')}")
                
        except Exception as e:
            logger.error(f"청산 체크 오류: {e}", exc_info=True)
    
    def _check_entries(self, df: pd.DataFrame, current_index: int):
        """진입 체크"""
        if current_index < 200:
            return
        
        row = df.iloc[current_index]
        current_price = row['close']
        atr = row.get('atr', 0)
        
        if atr <= 0:
            return
        
        # 동시 포지션 수 체크
        if self.position_manager.get_position_count() >= MAX_CONCURRENT_POSITIONS:
            return
        
        for strategy_name, strategy in self.strategies.items():
            # 이미 포지션 있으면 스킵
            if self.position_manager.has_position(strategy_name):
                continue
            
            # 진입 신호 체크
            try:
                if strategy.check_entry(df, current_index):
                    self._execute_entry(strategy, df, current_index)
            except Exception as e:
                logger.error(f"{strategy_name} 진입 체크 오류: {e}")
    
    def _execute_entry(self, strategy, df: pd.DataFrame, current_index: int):
        """진입 실행"""
        row = df.iloc[current_index]
        current_price = row['close']
        atr = row.get('atr', 0)
        
        # 손절폭 계산
        sl_dist = strategy.get_stop_loss_dist(row)
        if strategy.direction == 'SHORT':
            stop_loss = current_price + sl_dist
        else:
            stop_loss = current_price - sl_dist
        
        # 포지션 크기 계산
        risk_amount = min(MAX_POSITION_USDT, self.bot_state.current_capital * 0.01)
        quantity = self.order_manager.calculate_quantity(risk_amount, current_price)
        
        if quantity <= 0:
            logger.warning(f"{strategy.name} 수량 계산 실패")
            return
        
        # 주문 유효성 검사
        if not self.order_manager.validate_order(quantity, current_price):
            logger.warning(f"{strategy.name} 주문 유효성 실패")
            return
        
        logger.info(f"진입 시도: {strategy.name} | 가격: {current_price:.2f} | "
                   f"수량: {quantity} | SL: {stop_loss:.2f}")
        
        if DRY_RUN_MODE:
            logger.info("[DRY RUN] 실제 주문 실행 안함")
            return
        
        # 포지션 열기
        position = self.position_manager.open_position(
            strategy_name=strategy.name,
            entry_price=current_price,
            quantity=quantity,
            stop_loss=stop_loss,
            entry_index=current_index,
            direction=strategy.direction
        )
        
        if position:
            logger.info(f"진입 성공: {strategy.name}")
            
            # 전략 상태 초기화
            if hasattr(strategy, 'reset_partial_tp'):
                strategy.reset_partial_tp(position.entry_time)
    
    def _check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 체크"""
        if self.bot_state.daily_high_watermark <= 0:
            return False
        
        current_dd = (self.bot_state.daily_high_watermark - self.bot_state.current_capital) / self.bot_state.daily_high_watermark
        
        return current_dd >= DAILY_LOSS_LIMIT_PCT
    
    def _enter_safe_mode(self, reason: str):
        """Safe mode 진입"""
        if not self.safe_mode:
            self.safe_mode = True
            self.bot_state.safe_mode = True
            logger.warning(f"Safe mode 진입: {reason}")
    
    def _save_state(self):
        """상태 저장"""
        try:
            self.bot_state.update_from_position_manager(self.position_manager)
            self.bot_state.update_daily_tracking(self.bot_state.current_capital)
            
            self.state_manager.save_state(self.bot_state.to_dict())
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")
    
    def stop(self):
        """봇 중지"""
        logger.info("봇 중지 요청...")
        self.is_running = False
        self.bot_state.is_running = False
    
    def _cleanup(self):
        """정리 작업"""
        logger.info("정리 작업 시작...")
        
        # 상태 저장
        self._save_state()
        
        # WebSocket 종료
        if self.data_manager:
            self.data_manager.stop_stream()
        
        # 열린 포지션 경고
        open_positions = self.position_manager.get_all_positions()
        if open_positions:
            logger.warning(f"열린 포지션 {len(open_positions)}개가 있습니다!")
            for name, pos in open_positions.items():
                logger.warning(f"  - {name}: {pos.remaining_quantity} @ {pos.entry_price}")
        
        # 거래 내역 저장 및 시각화
        self._save_trading_report()
        
        logger.info("봇 종료")
    
    def _save_trading_report(self):
        """거래 내역 저장 및 시각화"""
        trade_history = self.position_manager.get_trade_history()
        
        if not trade_history:
            logger.info("저장할 거래 내역이 없습니다")
            return
        
        try:
            import os
            from datetime import datetime
            
            # 출력 폴더 생성
            report_dir = 'output/live_reports'
            os.makedirs(report_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 1. CSV로 저장
            trades_df = pd.DataFrame(trade_history)
            csv_path = f"{report_dir}/live_trades_{timestamp}.csv"
            trades_df.to_csv(csv_path, index=False)
            logger.info(f"거래 내역 CSV 저장: {csv_path}")
            
            # 2. 요약 통계 출력
            total_trades = len(trades_df)
            wins = trades_df[trades_df['pnl'] > 0]
            losses = trades_df[trades_df['pnl'] <= 0]
            
            total_pnl = trades_df['pnl'].sum()
            win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
            
            logger.info("=" * 50)
            logger.info("거래 요약")
            logger.info("=" * 50)
            logger.info(f"총 거래 수: {total_trades}")
            logger.info(f"승리: {len(wins)} | 패배: {len(losses)}")
            logger.info(f"승률: {win_rate:.1f}%")
            logger.info(f"총 손익: ${total_pnl:.2f}")
            
            if not wins.empty:
                logger.info(f"평균 수익: ${wins['pnl'].mean():.2f}")
            if not losses.empty:
                logger.info(f"평균 손실: ${losses['pnl'].mean():.2f}")
            
            # 3. 전략별 성과
            logger.info("\n전략별 성과:")
            for strategy in trades_df['strategy'].unique():
                strat_trades = trades_df[trades_df['strategy'] == strategy]
                strat_pnl = strat_trades['pnl'].sum()
                strat_count = len(strat_trades)
                logger.info(f"  {strategy}: {strat_count}회, ${strat_pnl:.2f}")
            
            logger.info("=" * 50)
            
            # 4. 차트 생성 (캔들 데이터가 있는 경우)
            if self.data_manager:
                self._generate_trade_chart(trades_df, timestamp, report_dir)
                
        except Exception as e:
            logger.error(f"거래 내역 저장 실패: {e}")
    
    def _generate_trade_chart(self, trades_df, timestamp, report_dir):
        """거래 차트 생성"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            df = self.data_manager.get_dataframe()
            if df is None or df.empty:
                return
            
            # 최근 데이터만 사용 (차트 성능)
            df = df.tail(500)
            
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3]
            )
            
            # 캔들차트
            fig.add_trace(go.Candlestick(
                x=df['timestamp'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'
            ), row=1, col=1)
            
            # 거래 마커 추가
            for _, trade in trades_df.iterrows():
                entry_time = trade.get('entry_time')
                exit_time = trade.get('exit_time')
                entry_price = trade.get('entry_price', 0)
                exit_price = trade.get('exit_price', 0)
                pnl = trade.get('pnl', 0)
                
                # 진입 마커
                if entry_time and entry_price:
                    fig.add_annotation(
                        x=entry_time, y=entry_price,
                        text="Buy", showarrow=True, arrowhead=2,
                        arrowcolor="#2962FF", arrowsize=1, ax=0, ay=30,
                        bgcolor="#2962FF", font=dict(color="white", size=9),
                        row=1, col=1
                    )
                
                # 청산 마커
                if exit_time and exit_price:
                    color = "#00C853" if pnl > 0 else "#D50000"
                    text = f"{'Win' if pnl > 0 else 'Loss'}"
                    fig.add_annotation(
                        x=exit_time, y=exit_price,
                        text=text, showarrow=True, arrowhead=2,
                        arrowcolor=color, arrowsize=1, ax=0, ay=-30,
                        bgcolor=color, font=dict(color="white", size=9),
                        row=1, col=1
                    )
            
            # 거래량
            fig.add_trace(go.Bar(
                x=df['timestamp'],
                y=df['volume'],
                name='Volume',
                marker_color='lightgrey'
            ), row=2, col=1)
            
            # 레이아웃
            fig.update_layout(
                title=f"Live Trading Result - {timestamp}",
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                height=900,
                width=1600
            )
            
            # 저장
            html_path = f"{report_dir}/live_chart_{timestamp}.html"
            fig.write_html(html_path)
            logger.info(f"거래 차트 저장: {html_path}")
            
            # PNG 저장 시도
            try:
                png_path = f"{report_dir}/live_chart_{timestamp}.png"
                fig.write_image(png_path, scale=2)
                logger.info(f"차트 이미지 저장: {png_path}")
            except Exception:
                pass  # kaleido 없으면 스킵
                
        except Exception as e:
            logger.error(f"차트 생성 실패: {e}")
    
    def emergency_stop(self):
        """긴급 중지 및 전체 청산"""
        logger.warning("긴급 중지!")
        
        # 전체 포지션 청산
        self.position_manager.emergency_close_all()
        
        # 봇 중지
        self.stop()


def main():
    """메인 진입점"""
    print("=" * 60)
    print("  BTC/USDT 자동매매 봇")
    print("  Binance Futures (USDT-M)")
    print("=" * 60)
    print()
    
    # 환경 확인
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        print("오류: Binance API 키가 설정되지 않았습니다.")
        print(".env 파일에 BINANCE_API_KEY와 BINANCE_API_SECRET을 설정하세요.")
        return
    
    # 드라이런 모드 확인
    if DRY_RUN_MODE:
        print("주의: DRY RUN 모드 - 실제 주문이 실행되지 않습니다.")
        print()
    
    # 봇 생성 및 실행
    bot = TradingBot()
    
    if bot.initialize():
        try:
            bot.start()
        except KeyboardInterrupt:
            print("\n중지 요청...")
            bot.stop()
    else:
        print("봇 초기화 실패")


if __name__ == "__main__":
    main()
