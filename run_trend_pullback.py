# =========================================================
# Trend pullback strategy backtest runner
# =========================================================

import json
import os
import warnings
from datetime import datetime

import pandas as pd

from analysis.stats import calculate_stats
from config.settings import INITIAL_CAPITAL
from data.features import compute_indicators
from engine import PortfolioManager
from strategies import ShortTrendPullbackStrategy, TrendPullbackStrategy

warnings.filterwarnings("ignore")


SYMBOLS = ["BTC/USDT", "ETH/USDT", "XRP/USDT", "BNB/USDT"]
DATA_FILE = "multi_5m.json"


def load_data_dict(filepath=DATA_FILE):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} not found. Run python fetch_multi_5m.py first.")

    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    data_dict = {}
    for symbol, records in raw_data.items():
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        data_dict[symbol] = compute_indicators(df)

    return data_dict


def run_for_symbol(symbol, df):
    manager = PortfolioManager(initial_capital=INITIAL_CAPITAL)
    manager.add_strategy(TrendPullbackStrategy(), weight=0.5)
    manager.add_strategy(ShortTrendPullbackStrategy(), weight=0.5)

    trades, equity_curve = manager.run_backtest(df)
    stats = calculate_stats(trades, INITIAL_CAPITAL, manager.current_capital, equity_curve=equity_curve)
    stats["symbol"] = symbol
    stats["final_capital"] = manager.current_capital

    return stats, trades, equity_curve


def print_summary(results):
    print("\n" + "=" * 88)
    print("Trend Pullback Summary")
    print("=" * 88)
    print(f"{'Symbol':<12} {'Return':>10} {'WinRate':>10} {'Trades':>8} {'MDD':>10} {'PF':>8} {'Sharpe':>8}")
    print("-" * 88)

    total_return = 0.0
    total_trades = 0
    max_mdd = 0.0

    for stats in results:
        total_return += stats["total_return"]
        total_trades += stats["num_trades"]
        max_mdd = max(max_mdd, stats.get("max_drawdown_pct", 0))
        print(
            f"{stats['symbol']:<12} "
            f"{stats['total_return']:>9.2f}% "
            f"{stats['win_rate']:>9.1f}% "
            f"{stats['num_trades']:>8} "
            f"{stats.get('max_drawdown_pct', 0):>9.2f}% "
            f"{stats['pf']:>8.2f} "
            f"{stats.get('sharpe_ratio', 0):>8.2f}"
        )

    avg_return = total_return / len(results) if results else 0.0
    print("-" * 88)
    print(f"{'AVG/MAX':<12} {avg_return:>9.2f}% {'-':>10} {total_trades:>8} {max_mdd:>9.2f}%")


def main():
    print("Loading multi-symbol data and computing indicators...")
    data_dict = load_data_dict(DATA_FILE)

    results = []
    output_dir = "output/trend_pullback"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for symbol in SYMBOLS:
        if symbol not in data_dict:
            print(f"{symbol}: skipped, no data")
            continue

        print("\n" + "=" * 60)
        print(f"{symbol} trend pullback backtest")
        print("=" * 60)

        stats, trades, equity = run_for_symbol(symbol, data_dict[symbol])
        results.append(stats)

        symbol_slug = symbol.replace("/", "_")
        if not trades.empty:
            trades.to_csv(f"{output_dir}/trades_{symbol_slug}_{timestamp}.csv", index=False)
        equity.to_csv(f"{output_dir}/equity_{symbol_slug}_{timestamp}.csv", index=False)

    if results:
        print_summary(results)
        pd.DataFrame(results).to_csv(f"{output_dir}/summary_{timestamp}.csv", index=False)


if __name__ == "__main__":
    main()
