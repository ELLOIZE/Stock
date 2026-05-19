# =========================================================
# 통계 분석 모듈
# =========================================================

import numpy as np


def calculate_max_drawdown(equity_curve):
    """
    최대 낙폭 (Maximum Drawdown) 계산

    Args:
        equity_curve: DataFrame with 'equity' column

    Returns:
        dict: {max_drawdown_pct, max_drawdown_abs, peak_equity, trough_equity}
    """
    if equity_curve is None or equity_curve.empty or 'equity' not in equity_curve.columns:
        return {'max_drawdown_pct': 0.0, 'max_drawdown_abs': 0.0, 'peak_equity': 0.0, 'trough_equity': 0.0}

    equity = equity_curve['equity'].values

    # Running maximum (high water mark)
    running_max = np.maximum.accumulate(equity)

    # Drawdown at each point
    drawdown = (running_max - equity) / running_max

    # Find maximum drawdown
    max_dd_idx = np.argmax(drawdown)
    max_dd_pct = drawdown[max_dd_idx] * 100

    # Find peak before max drawdown
    peak_idx = np.argmax(equity[:max_dd_idx + 1]) if max_dd_idx > 0 else 0

    return {
        'max_drawdown_pct': max_dd_pct,
        'max_drawdown_abs': running_max[max_dd_idx] - equity[max_dd_idx],
        'peak_equity': equity[peak_idx],
        'trough_equity': equity[max_dd_idx]
    }


def calculate_sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=105120):
    """
    샤프 비율 계산 (연율화)

    Args:
        returns: 수익률 배열 (각 기간의 수익률)
        risk_free_rate: 무위험 수익률 (연율화, 기본값 0)
        periods_per_year: 연간 기간 수 (5분봉: 365*24*12 = 105,120)

    Returns:
        float: 연율화된 샤프 비율
    """
    if len(returns) < 2:
        return 0.0

    returns = np.array(returns)
    excess_returns = returns - (risk_free_rate / periods_per_year)

    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return 0.0

    # Annualize
    sharpe = (mean_excess / std_excess) * np.sqrt(periods_per_year)
    return sharpe


def calculate_sortino_ratio(returns, risk_free_rate=0.0, periods_per_year=105120):
    """
    소르티노 비율 계산 (하방 리스크만 고려, 연율화)

    Args:
        returns: 수익률 배열
        risk_free_rate: 무위험 수익률 (연율화)
        periods_per_year: 연간 기간 수

    Returns:
        float: 연율화된 소르티노 비율
    """
    if len(returns) < 2:
        return 0.0

    returns = np.array(returns)
    excess_returns = returns - (risk_free_rate / periods_per_year)

    mean_excess = np.mean(excess_returns)

    # Downside deviation (only negative returns)
    negative_returns = excess_returns[excess_returns < 0]
    if len(negative_returns) == 0:
        return float('inf') if mean_excess > 0 else 0.0

    downside_std = np.sqrt(np.mean(negative_returns ** 2))

    if downside_std == 0:
        return 0.0

    # Annualize
    sortino = (mean_excess / downside_std) * np.sqrt(periods_per_year)
    return sortino


def _position_level_trades(trades_df):
    """Collapse partial exits and final exits into one row per opened position."""
    required_cols = {'entry_time', 'type', 'direction', 'net_pnl'}
    if not required_cols.issubset(trades_df.columns):
        return trades_df

    position_rows = []
    group_cols = ['entry_time', 'type', 'direction']
    for _, group in trades_df.groupby(group_cols, sort=False):
        row = group.iloc[-1].copy()
        row['net_pnl'] = group['net_pnl'].astype(float).sum()
        if 'size' in group.columns:
            row['size'] = group['size'].astype(float).sum()
        if 'is_partial' in group.columns:
            row['is_partial'] = False
        position_rows.append(row)

    return trades_df.__class__(position_rows).reset_index(drop=True)


def _average_pnl_pct(trades_df):
    if trades_df.empty or 'entry_price' not in trades_df.columns or 'size' not in trades_df.columns:
        return 0.0

    entry_notional = trades_df['entry_price'].astype(float) * trades_df['size'].astype(float)
    valid = entry_notional != 0
    if not valid.any():
        return 0.0

    pnl_pct = trades_df.loc[valid, 'net_pnl'].astype(float) / entry_notional[valid]
    return pnl_pct.mean() * 100


def calculate_stats(trades_df, initial, final, equity_curve=None):
    """
    백테스트 결과 통계 계산
    
    Args:
        trades_df: 거래 기록 DataFrame
        initial: 초기 자본
        final: 최종 자본
    
    Returns:
        dict: 통계 정보
    """
    if trades_df.empty:
        return {
            "final_equity": final,
            "total_return": 0,
            "num_trades": 0,
            "win_rate": 0,
            "pf": 0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0
        }
    
    position_trades = _position_level_trades(trades_df)
    wins = position_trades[position_trades['net_pnl'] > 0]
    losses = position_trades[position_trades['net_pnl'] <= 0]
    
    win_rate = len(wins) / len(position_trades) * 100
    profit_factor = wins['net_pnl'].sum() / -losses['net_pnl'].sum() if not losses.empty and losses['net_pnl'].sum() != 0 else 0
    
    # Win/Loss 평균 손익 계산 (수수료 포함)
    avg_win = wins['net_pnl'].mean() if not wins.empty else 0.0
    avg_loss = losses['net_pnl'].mean() if not losses.empty else 0.0
    
    # Win/Loss 평균 수익률/손실률 계산 (%)
    avg_win_pct = _average_pnl_pct(wins)
    avg_loss_pct = _average_pnl_pct(losses)

    partial_exits = 0
    if 'is_partial' in trades_df.columns:
        partial_exits = (trades_df['is_partial'].astype(str).str.lower() == 'true').sum()

    # 리스크 지표 계산
    if equity_curve is not None and len(equity_curve) > 1:
        equity_values = equity_curve['equity'].values
        period_returns = np.diff(equity_values) / equity_values[:-1]

        dd_stats = calculate_max_drawdown(equity_curve)
        sharpe = calculate_sharpe_ratio(period_returns)
        sortino = calculate_sortino_ratio(period_returns)
    else:
        dd_stats = {'max_drawdown_pct': 0.0, 'max_drawdown_abs': 0.0}
        sharpe = 0.0
        sortino = 0.0

    return {
        "final_equity": final,
        "total_return": (final / initial - 1) * 100,
        "num_trades": len(position_trades),
        "exit_rows": len(trades_df),
        "partial_exits": int(partial_exits),
        "win_rate": win_rate,
        "pf": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "max_drawdown_pct": dd_stats['max_drawdown_pct'],
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "by_type": position_trades.groupby('type')['net_pnl'].agg(['count', 'sum', 'mean'])
    }


def print_stats(stats):
    """통계 출력"""
    print("\n========== [포트폴리오 통합 결과] ==========")
    print(f"최종 자산: ${stats['final_equity']:.2f} ({stats['total_return']:.2f}%)")
    print(f"총 매매 횟수: {stats['num_trades']}회")
    print(f"통합 승률: {stats['win_rate']:.2f}%")
    print(f"수익 팩터: {stats['pf']:.2f}")
    
    # Win/Loss 평균 손익 출력
    if 'avg_win' in stats:
        print(f"평균 Win: ${stats['avg_win']:.2f} ({stats['avg_win_pct']:.2f}%)")
        print(f"평균 Loss: ${stats['avg_loss']:.2f} ({stats['avg_loss_pct']:.2f}%)")

    # 리스크 지표 출력
    if 'max_drawdown_pct' in stats:
        print(f"\n--- 리스크 지표 ---")
        print(f"최대 낙폭 (MDD): {stats['max_drawdown_pct']:.2f}%")
        print(f"샤프 비율: {stats['sharpe_ratio']:.2f}")
        print(f"소르티노 비율: {stats['sortino_ratio']:.2f}")

    if 'by_type' in stats:
        print("\n--- 전략별 성과 ---")
        by_type = stats['by_type'].copy()
        # 컬럼명 변경 및 포맷팅
        by_type.columns = ['거래 횟수', '총 손익 ($)', '평균 손익 ($)']
        # 숫자 포맷팅
        by_type['총 손익 ($)'] = by_type['총 손익 ($)'].apply(lambda x: f"${x:.2f}")
        by_type['평균 손익 ($)'] = by_type['평균 손익 ($)'].apply(lambda x: f"${x:.2f}")
        print(by_type)


# =========================================================
# 멀티 기간 백테스트 통계 함수
# =========================================================

def aggregate_results(results_list):
    """
    여러 백테스트 기간의 결과 집계
    
    Args:
        results_list: 각 기간의 통계 딕셔너리 리스트
    
    Returns:
        dict: 집계된 통계 (평균, 최소, 최대 등)
    """
    if not results_list:
        return {}
    
    returns = [r['total_return'] for r in results_list]
    win_rates = [r['win_rate'] for r in results_list]
    profit_factors = [r['pf'] for r in results_list]
    num_trades = [r['num_trades'] for r in results_list]
    max_drawdowns = [r.get('max_drawdown_pct', 0) for r in results_list]
    sharpe_ratios = [r.get('sharpe_ratio', 0) for r in results_list]
    sortino_ratios = [r.get('sortino_ratio', 0) for r in results_list]

    aggregated = {
        'num_periods': len(results_list),
        'returns': {
            'avg': np.mean(returns),
            'min': np.min(returns),
            'max': np.max(returns),
            'std': np.std(returns),
            'median': np.median(returns),
            'all_values': returns
        },
        'win_rates': {
            'avg': np.mean(win_rates),
            'min': np.min(win_rates),
            'max': np.max(win_rates),
            'std': np.std(win_rates),
            'median': np.median(win_rates),
            'all_values': win_rates
        },
        'profit_factors': {
            'avg': np.mean(profit_factors),
            'min': np.min(profit_factors),
            'max': np.max(profit_factors),
            'std': np.std(profit_factors),
            'median': np.median(profit_factors),
            'all_values': profit_factors
        },
        'num_trades': {
            'avg': np.mean(num_trades),
            'min': np.min(num_trades),
            'max': np.max(num_trades),
            'median': np.median(num_trades)
        },
        'max_drawdowns': {
            'avg': np.mean(max_drawdowns),
            'min': np.min(max_drawdowns),
            'max': np.max(max_drawdowns),
            'std': np.std(max_drawdowns),
            'median': np.median(max_drawdowns),
            'all_values': max_drawdowns
        },
        'sharpe_ratios': {
            'avg': np.mean(sharpe_ratios),
            'min': np.min(sharpe_ratios),
            'max': np.max(sharpe_ratios),
            'std': np.std(sharpe_ratios),
            'median': np.median(sharpe_ratios),
            'all_values': sharpe_ratios
        },
        'sortino_ratios': {
            'avg': np.mean(sortino_ratios),
            'min': np.min(sortino_ratios),
            'max': np.max(sortino_ratios),
            'std': np.std(sortino_ratios),
            'median': np.median(sortino_ratios),
            'all_values': sortino_ratios
        },
        'detailed_results': results_list
    }
    
    return aggregated


def print_aggregated_stats(aggregated, window_size):
    """
    집계된 결과 출력
    
    Args:
        aggregated: aggregate_results()에서 반환된 딕셔너리
        window_size: 각 기간의 캔들 수
    """
    print("\n" + "=" * 50)
    print("========== [멀티 기간 백테스트 결과] ==========")
    print("=" * 50)
    print(f"테스트 기간 수: {aggregated['num_periods']}")
    print(f"창 크기: {window_size} 캔들 (~{window_size * 5 / 60 / 24:.1f} days)")
    
    print("\n--- 수익률 통계 (Return) ---")
    print(f"평균 수익률: {aggregated['returns']['avg']:.2f}%")
    print(f"최소 수익률: {aggregated['returns']['min']:.2f}%")
    print(f"최대 수익률: {aggregated['returns']['max']:.2f}%")
    print(f"표준편차:     {aggregated['returns']['std']:.2f}%")
    print(f"중앙값:       {aggregated['returns']['median']:.2f}%")
    
    print("\n--- 승률 통계 (Win Rate) ---")
    print(f"평균 승률:   {aggregated['win_rates']['avg']:.2f}%")
    print(f"최소 승률:   {aggregated['win_rates']['min']:.2f}%")
    print(f"최대 승률:   {aggregated['win_rates']['max']:.2f}%")
    print(f"표준편차:     {aggregated['win_rates']['std']:.2f}%")
    print(f"중앙값:       {aggregated['win_rates']['median']:.2f}%")
    
    print("\n--- 수익 팩터 통계 (Profit Factor) ---")
    print(f"평균 PF:     {aggregated['profit_factors']['avg']:.2f}")
    print(f"최소 PF:     {aggregated['profit_factors']['min']:.2f}")
    print(f"최대 PF:     {aggregated['profit_factors']['max']:.2f}")
    print(f"표준편차:     {aggregated['profit_factors']['std']:.2f}")
    print(f"중앙값:       {aggregated['profit_factors']['median']:.2f}")
    
    print("\n--- 거래 횟수 통계 ---")
    print(f"평균 거래수: {aggregated['num_trades']['avg']:.0f}")
    print(f"최소 거래수: {aggregated['num_trades']['min']:.0f}")
    print(f"최대 거래수: {aggregated['num_trades']['max']:.0f}")
    print(f"중앙값:       {aggregated['num_trades']['median']:.0f}")

    print("\n--- 최대 낙폭 (MDD) 통계 ---")
    print(f"평균 MDD:    {aggregated['max_drawdowns']['avg']:.2f}%")
    print(f"최소 MDD:    {aggregated['max_drawdowns']['min']:.2f}%")
    print(f"최대 MDD:    {aggregated['max_drawdowns']['max']:.2f}%")
    print(f"중앙값:       {aggregated['max_drawdowns']['median']:.2f}%")

    print("\n--- 샤프 비율 통계 ---")
    print(f"평균 Sharpe: {aggregated['sharpe_ratios']['avg']:.2f}")
    print(f"최소 Sharpe: {aggregated['sharpe_ratios']['min']:.2f}")
    print(f"최대 Sharpe: {aggregated['sharpe_ratios']['max']:.2f}")
    print(f"중앙값:       {aggregated['sharpe_ratios']['median']:.2f}")

    print("\n--- 소르티노 비율 통계 ---")
    print(f"평균 Sortino:{aggregated['sortino_ratios']['avg']:.2f}")
    print(f"최소 Sortino:{aggregated['sortino_ratios']['min']:.2f}")
    print(f"최대 Sortino:{aggregated['sortino_ratios']['max']:.2f}")
    print(f"중앙값:       {aggregated['sortino_ratios']['median']:.2f}")

    # Top 5 / Bottom 5 기간 출력
    print("\n--- 상위 5 기간 (Best Periods) ---")
    sorted_indices = np.argsort(aggregated['returns']['all_values'])[::-1]
    for i, idx in enumerate(sorted_indices[:5], 1):
        r = aggregated['detailed_results'][idx]
        print(f"[기간 {idx:3d}] 수익: {r['total_return']:6.2f}% | 승률: {r['win_rate']:5.1f}% | PF: {r['pf']:5.2f}")
    
    print("\n--- 하위 5 기간 (Worst Periods) ---")
    for i, idx in enumerate(sorted_indices[-5:][::-1], 1):
        r = aggregated['detailed_results'][idx]
        print(f"[기간 {idx:3d}] 수익: {r['total_return']:6.2f}% | 승률: {r['win_rate']:5.1f}% | PF: {r['pf']:5.2f}")
    
    print("=" * 50)
