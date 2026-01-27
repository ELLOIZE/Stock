# BTC/USDT Backtesting System Improvement Specification

**Generated:** 2026-01-26
**Status:** EXPANSION_COMPLETE

---

## Executive Summary

This specification defines improvements to the existing BTC/USDT backtesting system focusing on:
1. Security (API key management)
2. Realistic testing (fees, slippage)
3. Risk metrics (max drawdown, Sharpe/Sortino ratios)
4. Statistical rigor (walk-forward testing)
5. Code quality (deduplication, unit tests)

---

## Functional Requirements

| ID | Requirement | Priority | Effort |
|----|-------------|----------|--------|
| FR-1 | Remove hardcoded API credentials | CRITICAL | Low |
| FR-2 | Set realistic fee rate (0.04%) | HIGH | Trivial |
| FR-3 | Add slippage modeling (ATR-based) | HIGH | Medium |
| FR-4 | Implement max drawdown calculation | HIGH | Low |
| FR-5 | Implement Sharpe/Sortino ratios | HIGH | Low |
| FR-6 | Replace random periods with walk-forward | HIGH | Medium |
| FR-7 | Remove duplicate code (build_features.py) | MEDIUM | Low |

---

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-1 | All secrets via environment variables | Security |
| NFR-2 | Backtest 300K candles in < 5 minutes | Performance |
| NFR-5 | Unit test coverage > 60% on core modules | Reliability |

---

## Out of Scope (Phase 1)

- Short selling capability
- Live trading integration
- Machine learning optimization
- Multi-asset portfolio
- Interactive web dashboard
- Order book depth analysis
- Multi-timeframe strategies

---

## Technical Specification

### Phase 1: Security (FR-1, NFR-1)

**Files Affected:**
- `config/settings.py` - Add python-dotenv, environment variable loading
- `data/fetcher.py` - Add credential validation
- `.env.example` - Create template
- `.gitignore` - Add .env exclusion

**Key Changes:**
```python
# config/settings.py
import os
from dotenv import load_dotenv
load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
```

### Phase 2: Trading Realism (FR-2, FR-3)

**Files Affected:**
- `config/settings.py` - Fee rate and slippage parameters
- `engine/portfolio.py` - Slippage application logic

**Key Changes:**
```python
# config/settings.py
FEE_RATE = 0.0004  # 0.04%
SLIPPAGE_ATR_MULT = 0.05  # 5% of ATR
SLIPPAGE_MIN_PCT = 0.0001
SLIPPAGE_MAX_PCT = 0.001

# engine/portfolio.py
def _apply_slippage(self, price, atr, direction='buy'):
    slippage_amt = min(max(atr * self.slippage_atr_mult,
                          price * self.slippage_min_pct),
                       price * self.slippage_max_pct)
    return price + slippage_amt if direction == 'buy' else price - slippage_amt
```

### Phase 3: Risk Metrics (FR-4, FR-5)

**Files Affected:**
- `analysis/stats.py` - New functions for drawdown and ratios

**New Functions:**
- `calculate_max_drawdown(equity_curve)` - Returns max DD %, peak/trough timestamps
- `calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year)` - Annualized Sharpe
- `calculate_sortino_ratio(returns, risk_free_rate, periods_per_year)` - Annualized Sortino

### Phase 4: Walk-Forward Testing (FR-6)

**Files Affected:**
- `config/settings.py` - Walk-forward configuration
- `multi_period_backtest.py` - Complete rewrite

**Key Changes:**
```python
# config/settings.py
WALK_FORWARD_CONFIG = {
    'in_sample_ratio': 0.7,
    'out_sample_ratio': 0.3,
    'min_window_candles': 5000,
    'step_candles': 2500,
    'anchored': False,
}
```

### Phase 5: Code Cleanup (FR-7)

**Action:** Delete `build_features.py` (duplicates data/fetcher.py and data/features.py)

### Phase 6: Unit Tests (NFR-5)

**New Files:**
- `tests/__init__.py`
- `tests/conftest.py` - Shared fixtures
- `tests/test_stats.py` - Stats module tests
- `tests/test_portfolio.py` - Portfolio manager tests
- `tests/test_features.py` - Indicator calculation tests
- `tests/test_strategies.py` - Strategy logic tests

---

## Implementation Order

```
1. Phase 1: Security         → No dependencies
2. Phase 5: Code Cleanup     → Depends on Phase 1
3. Phase 2: Fee/Slippage     → Depends on Phase 1
4. Phase 3: Risk Metrics     → Independent
5. Phase 4: Walk-Forward     → Depends on Phase 3
6. Phase 6: Unit Tests       → Depends on Phases 1-5
```

---

## New Dependencies

```txt
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-cov>=4.0.0
```

---

## Verification Checklist

- [ ] No hardcoded API keys in source code
- [ ] `.env` in `.gitignore`
- [ ] `FEE_RATE > 0` in config
- [ ] Slippage applied to entry/exit prices
- [ ] `calculate_stats()` returns max_drawdown_pct, sharpe_ratio, sortino_ratio
- [ ] Walk-forward periods are non-overlapping
- [ ] `build_features.py` deleted
- [ ] Test coverage > 60%
