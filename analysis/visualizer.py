# =========================================================
# 결과 시각화 모듈
# =========================================================

import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import OUTPUT_DIR


class ResultVisualizer:
    """백테스트 결과 시각화 클래스"""
    
    def __init__(self, df_market, df_trades):
        """
        Args:
            df_market: 지표가 계산된 전체 차트 데이터
            df_trades: 매매 기록 데이터프레임
        """
        self.df = df_market
        self.trades = df_trades
        
        # 출력 폴더 생성
        os.makedirs(f"{OUTPUT_DIR}/charts", exist_ok=True)
        os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)

    def save_to_excel(self, filename=None):
        """매매 기록을 엑셀로 저장"""
        if self.trades.empty:
            print("매매 기록이 없어 엑셀을 저장하지 않습니다.")
            return

        if filename is None:
            filename = f"{OUTPUT_DIR}/reports/trades_result.xlsx"

        try:
            output_df = self.trades.copy()
            output_df.to_excel(filename, index=False)
            print(f"[저장 완료] 엑셀 리포트: {filename}")
        except Exception as e:
            print(f"[오류] 엑셀 저장 실패: {e}")

    def save_to_csv(self, trades_file=None, equity_file=None, equity_df=None):
        """CSV로 저장"""
        if trades_file is None:
            trades_file = f"{OUTPUT_DIR}/reports/trades_result.csv"
        if equity_file is None:
            equity_file = f"{OUTPUT_DIR}/reports/equity_curve.csv"
            
        self.trades.to_csv(trades_file, index=False)
        if equity_df is not None:
            equity_df.to_csv(equity_file, index=False)

    def generate_charts(self):
        """전략별로 HTML 및 이미지 차트 생성"""
        if self.trades.empty:
            print("매매 기록이 없어 차트를 생성하지 않습니다.")
            return

        strategies = self.trades['type'].unique()
        
        for strat_name in strategies:
            print(f"[{strat_name}] 차트 생성 중...")
            
            strat_trades = self.trades[self.trades['type'] == strat_name]
            
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True,
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3]
            )

            # 캔들차트
            fig.add_trace(go.Candlestick(
                x=self.df['timestamp'],
                open=self.df['open'], 
                high=self.df['high'], 
                low=self.df['low'], 
                close=self.df['close'],
                name='Price'
            ), row=1, col=1)

            # 보조지표
            if 'ema200' in self.df.columns:
                fig.add_trace(go.Scatter(
                    x=self.df['timestamp'], 
                    y=self.df['ema200'], 
                    mode='lines', 
                    name='EMA 200', 
                    line=dict(color='orange', width=1)
                ), row=1, col=1)
            
            # 볼린저 밴드
            if 'upperBB' in self.df.columns:
                fig.add_trace(go.Scatter(
                    x=self.df['timestamp'], 
                    y=self.df['upperBB'], 
                    mode='lines', 
                    name='Upper BB', 
                    line=dict(color='gray', dash='dot', width=1)
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=self.df['timestamp'], 
                    y=self.df['lowerBB'], 
                    mode='lines', 
                    name='Lower BB', 
                    line=dict(color='gray', dash='dot', width=1)
                ), row=1, col=1)

            # 매매 포인트 마커
            for _, trade in strat_trades.iterrows():
                # 매수 (진입)
                fig.add_annotation(
                    x=trade['entry_time'], y=trade['entry_price'],
                    text="Buy", showarrow=True, arrowhead=2,
                    arrowcolor="#2962FF", arrowsize=1, ax=0, ay=30,
                    bgcolor="#2962FF", font=dict(color="white", size=9),
                    row=1, col=1
                )

                # 매도 (청산)
                is_win = trade['net_pnl'] > 0
                color = "#00C853" if is_win else "#D50000"
                text = f"{'Win' if is_win else 'Loss'}"
                
                fig.add_annotation(
                    x=trade['exit_time'], y=trade['exit_price'],
                    text=text, showarrow=True, arrowhead=2,
                    arrowcolor=color, arrowsize=1, ax=0, ay=-30,
                    bgcolor=color, font=dict(color="white", size=9),
                    row=1, col=1
                )

            # 거래량
            fig.add_trace(go.Bar(
                x=self.df['timestamp'], 
                y=self.df['volume'], 
                name='Volume', 
                marker_color='lightgrey'
            ), row=2, col=1)

            # 레이아웃
            fig.update_layout(
                title=f"Backtest Result: {strat_name}",
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                height=900,
                width=1600
            )

            # 파일 저장
            file_base = f"{OUTPUT_DIR}/charts/result_{strat_name}"
            
            # HTML 저장
            fig.write_html(f"{file_base}.html")
            
            # 이미지 저장
            try:
                fig.write_image(f"{file_base}.png", scale=2)
                print(f"  -> 저장 완료: {file_base}.png, {file_base}.html")
            except Exception:
                print(f"  -> HTML 저장 완료 (이미지 저장을 위해서는 'pip install -U kaleido' 필요)")

    def generate_all(self, equity_df=None):
        """모든 리포트 생성"""
        print("\n========== [리포트 생성 중] ==========")
        self.save_to_excel()
        self.save_to_csv(equity_df=equity_df)
        self.generate_charts()
