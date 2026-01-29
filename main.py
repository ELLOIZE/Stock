# =========================================================
# 백테스트 실행 메인 스크립트
# =========================================================

import warnings
warnings.filterwarnings("ignore")

from config.settings import INITIAL_CAPITAL, DATA_FILE, STRATEGY_WEIGHTS
from data.fetcher import load_data
from data.features import compute_indicators
from strategies import BreakoutStrategy, MeanReversionStrategy, MomentumStrategy
from engine import PortfolioManager
from analysis import calculate_stats, ResultVisualizer
from analysis.stats import print_stats


def main():
    # 1. 데이터 로드
    try:
        df = load_data(DATA_FILE)
    except Exception as e:
        print(f"{DATA_FILE} 파일이 없습니다. fetch_data.py를 먼저 실행하세요.")
        print(f"에러: {e}")
        return
    
    # 2. 지표 계산
    df_ind = compute_indicators(df)
    
    # 3. 관제탑 생성
    manager = PortfolioManager(initial_capital=INITIAL_CAPITAL)
    
    # 4. 전략 등록
    manager.add_strategy(
        BreakoutStrategy("BREAKOUT"), 
        weight=STRATEGY_WEIGHTS['BREAKOUT']
    )
    manager.add_strategy(
        MeanReversionStrategy("MEAN_REV"),
        weight=STRATEGY_WEIGHTS['MEAN_REV']
    )
    manager.add_strategy(
        MomentumStrategy("MOMENTUM"),
        weight=STRATEGY_WEIGHTS['MOMENTUM']
    )
    
    # 5. 백테스팅 실행
    trades, eq_curve = manager.run_backtest(df_ind)
    
    # 6. 결과 분석
    stats = calculate_stats(trades, manager.initial_capital, manager.current_capital, equity_curve=eq_curve)
    print_stats(stats)
    
    # 7. 리포트 생성
    if not trades.empty:
        vis = ResultVisualizer(df_ind, trades)
        vis.generate_all(equity_df=eq_curve)
    else:
        print("매매 기록이 없어 리포트를 생성하지 않습니다.")


if __name__ == "__main__":
    main()
