# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BTC/USDT 5분봉 데이터를 사용한 다중 전략 백테스트 시스템. Python 기반 암호화폐 트레이딩 전략 백테스팅 프레임워크.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Fetch data from Binance (creates test.json with ~300K candles)
python fetch_data.py

# Run single-period backtest
python main.py

# Run multi-period backtest (100 random periods, 5000 candles each)
python multi_period_backtest.py
```

Output files are generated in `output/reports/` (Excel, CSV) and `output/charts/` (HTML, PNG).

## Architecture

### Layer Structure

```
config/settings.py     - Centralized configuration (capital, fees, indicator params)
data/fetcher.py        - Binance API integration with retry/backoff
data/features.py       - Technical indicators (EMA, ATR, RSI, BB, ADX) + Support/Resistance
strategies/base.py     - Abstract Strategy class (template pattern)
strategies/breakout.py - Trend-following strategy (60% allocation)
strategies/mean_reversion.py - Counter-trend strategy (40% allocation)
engine/portfolio.py    - PortfolioManager orchestrates strategies, position tracking
analysis/stats.py      - Statistics calculation and multi-period aggregation
analysis/visualizer.py - Plotly candlestick charts with trade markers
```

### Execution Flow

```
main.py → load_data(test.json) → compute_indicators() → PortfolioManager
        → add_strategy(Breakout, MeanReversion)
        → run_backtest() [iterates candles: _check_exits → _check_entries]
        → calculate_stats() → ResultVisualizer (Excel/CSV + charts)
```

### Strategy Implementation

Extend `Strategy` base class and implement three methods:
- `check_entry(df, i)` → bool: Entry signal
- `check_exit(row, entry_price, entry_sl, atr)` → (new_sl, exit_reason): Exit logic
- `get_stop_loss_dist(row)` → float: Stop loss distance

## Code Style

- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants
- **Private methods**: `_prefix` (e.g., `_check_exits`)
- **Imports**: standard library → external packages → internal modules (absolute imports)
- **Docstrings**: Google-style with Args/Returns sections
- **Section dividers**: `# =========================================================`
- **Warnings**: Suppress globally with `warnings.filterwarnings("ignore")`

## Key Configuration (config/settings.py)

- `INITIAL_CAPITAL`: 10000.0
- `RISK_PER_TRADE`: 0.01 (1% per trade)
- `MAX_HOLD_CANDLES`: 288 (24h in 5m candles, time-based forced exit)
- `STRATEGY_WEIGHTS`: {'BREAKOUT': 0.6, 'MEAN_REV': 0.4}
- `BACKTEST_WINDOW_SIZE`: 5000 candles per period (~17 days)
- `NUM_PERIODS`: 100 random periods for multi-period testing

## Technical Notes

- Long positions only (no shorting)
- ATR-based stop loss and trailing stops
- Data format: JSON with OHLCV floats, string-encoded resistance levels
- No automated test framework configured
