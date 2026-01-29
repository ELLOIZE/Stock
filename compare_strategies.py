# =========================================================
# 전략별 개별 성과 비교 스크립트
# =========================================================

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from tqdm import tqdm

from config.settings import (
    INITIAL_CAPITAL, DATA_FILE, STRATEGY_WEIGHTS,
    WALK_FORWARD_CONFIG
)
from data.fetcher import load_data
from data.features import compute_indicators
from strategies import BreakoutStrategy, MeanReversionStrategy, MomentumStrategy
from engine import PortfolioManager
from analysis.stats import calculate_stats
from multi_period_backtest import generate_walk_forward_periods


def run_single_strategy_backtest(df_period, strategy_cls, strategy_name, weight=1.0):
    """단일 전략만으로 백테스트 실행"""
    manager = PortfolioManager(initial_capital=INITIAL_CAPITAL)
    manager.add_strategy(strategy_cls(strategy_name), weight=weight)
    trades, equity_curve = manager.run_backtest(df_period)
    stats = calculate_stats(trades, INITIAL_CAPITAL, manager.current_capital, equity_curve=equity_curve)
    return stats, trades, equity_curve


def run_combined_backtest(df_period):
    """3전략 통합 백테스트 실행"""
    manager = PortfolioManager(initial_capital=INITIAL_CAPITAL)
    manager.add_strategy(BreakoutStrategy("BREAKOUT"), weight=STRATEGY_WEIGHTS['BREAKOUT'])
    manager.add_strategy(MeanReversionStrategy("MEAN_REV"), weight=STRATEGY_WEIGHTS['MEAN_REV'])
    manager.add_strategy(MomentumStrategy("MOMENTUM"), weight=STRATEGY_WEIGHTS['MOMENTUM'])
    trades, equity_curve = manager.run_backtest(df_period)
    stats = calculate_stats(trades, INITIAL_CAPITAL, manager.current_capital, equity_curve=equity_curve)
    return stats


STRATEGIES = [
    ("BREAKOUT", BreakoutStrategy, STRATEGY_WEIGHTS['BREAKOUT']),
    ("MEAN_REV", MeanReversionStrategy, STRATEGY_WEIGHTS['MEAN_REV']),
    ("MOMENTUM", MomentumStrategy, STRATEGY_WEIGHTS['MOMENTUM']),
]


def compare_single_period(df_ind):
    """단일 기간 (전체 데이터) 전략 비교"""
    print("=" * 70)
    print("  단일 기간 전략별 비교 (전체 데이터)")
    print("=" * 70)

    results = {}

    for name, cls, weight in STRATEGIES:
        stats, trades, eq = run_single_strategy_backtest(df_ind, cls, name, weight)
        results[name] = stats

    # 통합
    combined = run_combined_backtest(df_ind)
    results["COMBINED"] = combined

    # 출력
    header = f"{'지표':<20} {'BREAKOUT':>12} {'MEAN_REV':>12} {'MOMENTUM':>12} {'COMBINED':>12}"
    print("\n" + header)
    print("-" * len(header))

    rows = [
        ("수익률 (%)", "total_return", ".2f"),
        ("거래 횟수", "num_trades", "d"),
        ("승률 (%)", "win_rate", ".1f"),
        ("Profit Factor", "pf", ".2f"),
        ("평균 Win ($)", "avg_win", ".2f"),
        ("평균 Loss ($)", "avg_loss", ".2f"),
        ("MDD (%)", "max_drawdown_pct", ".2f"),
        ("Sharpe", "sharpe_ratio", ".2f"),
        ("Sortino", "sortino_ratio", ".2f"),
    ]

    for label, key, fmt in rows:
        vals = []
        for sname in ["BREAKOUT", "MEAN_REV", "MOMENTUM", "COMBINED"]:
            v = results[sname].get(key, 0)
            if fmt == "d":
                vals.append(f"{int(v):>12}")
            else:
                vals.append(f"{v:>12{fmt}}")
        print(f"{label:<20} {''.join(vals)}")

    print()
    return results


def compare_walk_forward(df_ind):
    """Walk-Forward 멀티 기간 전략별 비교"""
    print("=" * 70)
    print("  Walk-Forward 멀티 기간 전략별 비교")
    print("=" * 70)

    total_candles = len(df_ind)
    periods = generate_walk_forward_periods(total_candles, WALK_FORWARD_CONFIG)
    print(f"  기간 수: {len(periods)}, Out-of-sample 캔들: {int(WALK_FORWARD_CONFIG['min_window_candles'] * WALK_FORWARD_CONFIG['out_sample_ratio'])}\n")

    # 전략별 결과 수집
    all_results = {name: [] for name, _, _ in STRATEGIES}
    all_results["COMBINED"] = []

    for period in tqdm(periods, desc="Walk-Forward 비교"):
        out_start, out_end = period['out_sample']
        out_df = df_ind.iloc[out_start:out_end].reset_index(drop=True)

        for name, cls, weight in STRATEGIES:
            stats, _, _ = run_single_strategy_backtest(out_df, cls, name, weight)
            all_results[name].append(stats)

        combined = run_combined_backtest(out_df)
        all_results["COMBINED"].append(combined)

    # 집계 및 출력
    def agg(stats_list, key):
        vals = [s.get(key, 0) for s in stats_list]
        return {
            'avg': np.mean(vals),
            'median': np.median(vals),
            'std': np.std(vals),
            'min': np.min(vals),
            'max': np.max(vals),
            'positive_pct': sum(1 for v in vals if v > 0) / len(vals) * 100 if vals else 0,
        }

    metrics = [
        ("수익률 (%)", "total_return"),
        ("거래 횟수", "num_trades"),
        ("승률 (%)", "win_rate"),
        ("Profit Factor", "pf"),
        ("MDD (%)", "max_drawdown_pct"),
        ("Sharpe", "sharpe_ratio"),
        ("Sortino", "sortino_ratio"),
    ]

    strat_names = ["BREAKOUT", "MEAN_REV", "MOMENTUM", "COMBINED"]

    for metric_label, metric_key in metrics:
        print(f"\n{'─' * 70}")
        print(f"  {metric_label}")
        print(f"{'─' * 70}")
        header = f"  {'통계':<10} {' '.join(f'{s:>12}' for s in strat_names)}"
        print(header)

        aggs = {s: agg(all_results[s], metric_key) for s in strat_names}

        for stat_name in ['avg', 'median', 'std', 'min', 'max']:
            row = f"  {stat_name:<10}"
            for s in strat_names:
                row += f" {aggs[s][stat_name]:>12.2f}"
            print(row)

        if metric_key == "total_return":
            row = f"  {'수익기간%':<10}"
            for s in strat_names:
                row += f" {aggs[s]['positive_pct']:>11.1f}%"
            print(row)

    # 최종 요약
    print(f"\n{'=' * 70}")
    print("  최종 요약: 평균 수익률 순위")
    print(f"{'=' * 70}")

    avg_returns = [(s, np.mean([r.get('total_return', 0) for r in all_results[s]])) for s in strat_names]
    avg_returns.sort(key=lambda x: x[1], reverse=True)

    for rank, (name, ret) in enumerate(avg_returns, 1):
        avg_wr = np.mean([r.get('win_rate', 0) for r in all_results[name]])
        avg_pf = np.mean([r.get('pf', 0) for r in all_results[name]])
        avg_mdd = np.mean([r.get('max_drawdown_pct', 0) for r in all_results[name]])
        print(f"  {rank}. {name:<12} 수익률: {ret:>7.2f}% | 승률: {avg_wr:>5.1f}% | PF: {avg_pf:>5.2f} | MDD: {avg_mdd:>5.2f}%")

    return all_results


if __name__ == "__main__":
    # 데이터 로드
    try:
        df = load_data(DATA_FILE)
        print(f"데이터 로드 완료: {len(df):,} 캔들")
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        exit(1)

    df_ind = compute_indicators(df)
    print(f"지표 계산 완료: {len(df_ind):,} 캔들\n")

    # 1. 단일 기간 비교
    single_results = compare_single_period(df_ind)

    # 2. Walk-Forward 멀티 기간 비교
    wf_results = compare_walk_forward(df_ind)
