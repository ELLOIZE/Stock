# =========================================================
# 피처 엔지니어링 모듈
# =========================================================

import json
import numpy as np
import pandas as pd
from tqdm import tqdm

from config.settings import (
    EMA_PERIODS,
    ATR_PERIOD,
    RSI_PERIOD,
    BB_PERIOD,
    BB_STD,
    REGIME_ADX_TREND,
    REGIME_ADX_RANGE,
    # Enhanced regime detection
    REGIME_RSI_BULLISH,
    REGIME_RSI_BEARISH,
    REGIME_RSI_OVERBOUGHT,
    REGIME_RSI_OVERSOLD,
    REGIME_BB_LOW_PCTL,
    REGIME_BB_HIGH_PCTL,
    REGIME_BB_LOOKBACK,
    REGIME_VOL_HIGH_MULT,
    REGIME_VOL_LOW_MULT,
    REGIME_EARLY_TREND_RSI_MIN,
    REGIME_EARLY_TREND_ADX_MIN,
)


def _classify_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enhanced market regime classification.

    Returns df with:
    - regime: Primary regime (TREND_UP, TREND_DOWN, RANGING, WEAK_TREND)
    - regime_phase: Detailed phase (EARLY_BULL, MATURE_BULL, etc.)
    - regime_momentum: Momentum state (BULLISH, BEARISH, NEUTRAL)
    - regime_volatility: Volatility state (HIGH, NORMAL, LOW)
    - regime_volume: Volume state (HIGH, NORMAL, LOW)
    - regime_strength: ADX value clipped to 0-100 (preserved)

    Note on ADX thresholds:
    - ADX < 20 (REGIME_ADX_RANGE): RANGING
    - ADX >= 18 (REGIME_EARLY_TREND_ADX_MIN): eligible for early trend
    - ADX overlap zone (18-20): classified by EMA/price/RSI conditions
    """
    ema21 = df['ema21']
    ema50 = df['ema50']
    ema200 = df['ema200']
    adx = df['adx']
    rsi = df['rsi']
    price = df['close']
    bb_width = df['bb_width']
    volume = df['volume']
    vol_ma = df['vol_ma20']

    # === Primary Regime (backward compatible) ===
    # Mature trends (original strict definition)
    mature_bull = (ema21 > ema50) & (ema50 > ema200) & (adx > REGIME_ADX_TREND) & (price > ema50)
    mature_bear = (ema21 < ema50) & (ema50 < ema200) & (adx > REGIME_ADX_TREND) & (price < ema50)

    # Early trends (new - more permissive)
    early_bull = (
        (ema21 > ema50) &
        (price > ema21) &
        (adx > REGIME_EARLY_TREND_ADX_MIN) &
        (rsi > REGIME_EARLY_TREND_RSI_MIN) &
        ~mature_bull  # Not already mature
    )
    early_bear = (
        (ema21 < ema50) &
        (price < ema21) &
        (adx > REGIME_EARLY_TREND_ADX_MIN) &
        (rsi < (100 - REGIME_EARLY_TREND_RSI_MIN)) &
        ~mature_bear  # Not already mature
    )

    ranging = adx < REGIME_ADX_RANGE

    df['regime'] = 'WEAK_TREND'
    df.loc[mature_bull | early_bull, 'regime'] = 'TREND_UP'
    df.loc[mature_bear | early_bear, 'regime'] = 'TREND_DOWN'
    df.loc[ranging, 'regime'] = 'RANGING'

    # Preserve regime_strength (ADX clipped 0-100)
    df['regime_strength'] = adx.clip(0, 100)

    # === Regime Phase (new detailed classification) ===
    # Compute BB width percentile (rolling)
    # Performance note: This uses a rolling lambda which is slower than vectorized ops.
    bb_pctl = bb_width.rolling(REGIME_BB_LOOKBACK, min_periods=20).apply(
        lambda x: (x.iloc[-1] <= x).mean() * 100, raw=False
    )

    df['regime_phase'] = 'NEUTRAL'

    # Bull phases
    df.loc[early_bull, 'regime_phase'] = 'EARLY_BULL'
    df.loc[mature_bull, 'regime_phase'] = 'MATURE_BULL'
    df.loc[mature_bull & (rsi > REGIME_RSI_OVERBOUGHT), 'regime_phase'] = 'LATE_BULL'

    # Bear phases
    df.loc[early_bear, 'regime_phase'] = 'EARLY_BEAR'
    df.loc[mature_bear, 'regime_phase'] = 'MATURE_BEAR'
    df.loc[mature_bear & (rsi < REGIME_RSI_OVERSOLD), 'regime_phase'] = 'LATE_BEAR'

    # Range phases
    consolidation = ranging & (bb_pctl < REGIME_BB_LOW_PCTL)
    volatile_range = ranging & (bb_pctl > REGIME_BB_HIGH_PCTL)
    df.loc[consolidation, 'regime_phase'] = 'CONSOLIDATION'
    df.loc[volatile_range, 'regime_phase'] = 'VOLATILE_RANGE'

    # === Momentum Classification ===
    df['regime_momentum'] = 'NEUTRAL'
    df.loc[rsi > REGIME_RSI_BULLISH, 'regime_momentum'] = 'BULLISH'
    df.loc[rsi < REGIME_RSI_BEARISH, 'regime_momentum'] = 'BEARISH'

    # === Volatility Classification ===
    df['regime_volatility'] = 'NORMAL'
    df.loc[bb_pctl < REGIME_BB_LOW_PCTL, 'regime_volatility'] = 'LOW'
    df.loc[bb_pctl > REGIME_BB_HIGH_PCTL, 'regime_volatility'] = 'HIGH'

    # === Volume Classification ===
    # Handle NaN in vol_ma (first 19 rows have NaN from rolling(20))
    vol_ratio = volume / vol_ma.replace(0, np.nan)
    df['regime_volume'] = 'NORMAL'
    df.loc[vol_ratio > REGIME_VOL_HIGH_MULT, 'regime_volume'] = 'HIGH'
    df.loc[vol_ratio < REGIME_VOL_LOW_MULT, 'regime_volume'] = 'LOW'

    # === NaN Handling (CRITICAL) ===
    # Fill NaN values with sensible defaults for all new columns
    df['regime'] = df['regime'].fillna('WEAK_TREND')
    df['regime_strength'] = df['regime_strength'].fillna(0)
    df['regime_phase'] = df['regime_phase'].fillna('NEUTRAL')
    df['regime_momentum'] = df['regime_momentum'].fillna('NEUTRAL')
    df['regime_volatility'] = df['regime_volatility'].fillna('NORMAL')
    df['regime_volume'] = df['regime_volume'].fillna('NORMAL')

    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    기술적 지표 계산

    Args:
        df: OHLCV 데이터프레임

    Returns:
        DataFrame: 지표가 추가된 데이터프레임
    """
    df = df.copy()
    
    if 'timestamp' in df.columns and not np.issubdtype(df['timestamp'].dtype, np.datetime64):
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp').reset_index(drop=True)

    # 이평선 (EMA)
    for period in EMA_PERIODS:
        df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    
    # 거래량 이동평균
    df['vol_ma20'] = df['volume'].rolling(20).mean()

    # ATR (Average True Range)
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr = pd.concat([
        (high - low).abs(), 
        (high - prev_close).abs(), 
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(ATR_PERIOD).mean()

    # ADX (Average Directional Index)
    diff_h = high.diff()
    diff_l = low.diff()
    p_dm = np.where((diff_h > 0) & (diff_h > diff_l), diff_h, 0.0)
    m_dm = np.where((diff_l < 0) & (diff_l.abs() > diff_h), diff_l.abs(), 0.0)
    
    tr_s = tr.rolling(ATR_PERIOD).sum()
    p_dm_s = pd.Series(p_dm).rolling(ATR_PERIOD).sum()
    m_dm_s = pd.Series(m_dm).rolling(ATR_PERIOD).sum()
    
    plus_di = 100 * (p_dm_s / tr_s)
    minus_di = 100 * (m_dm_s / tr_s)
    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
    df['adx'] = dx.rolling(ATR_PERIOD).mean()

    # RSI (Relative Strength Index)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['maBB'] = df['close'].rolling(BB_PERIOD).mean()
    df['stdBB'] = df['close'].rolling(BB_PERIOD).std()
    df['upperBB'] = df['maBB'] + (df['stdBB'] * BB_STD)
    df['lowerBB'] = df['maBB'] - (df['stdBB'] * BB_STD)
    df['bb_width'] = (df['upperBB'] - df['lowerBB']) / df['maBB']

    # Enhanced market regime classification
    df = _classify_regime(df)

    return df


def find_sr_levels(df, lookback=60, range_pct=0.002, touch_threshold=2):
    """
    지지/저항 레벨 찾기 (프랙탈 기반)
    
    Args:
        df: OHLCV 데이터프레임
        lookback: 룩백 기간
        range_pct: 클러스터링 범위 (%)
        touch_threshold: 최소 터치 횟수
    
    Returns:
        list: 지지/저항 레벨 리스트
    """
    highs = df['high'].values
    lows = df['low'].values
    
    potential_levels = []
    
    # 프랙탈 고점/저점 찾기 (좌우 3개 봉 기준)
    for i in range(3, len(df) - 3):
        # Pivot High
        if all(highs[i] >= highs[i-k] for k in range(1, 4)) and \
           all(highs[i] >= highs[i+k] for k in range(1, 4)):
            potential_levels.append(highs[i])
        # Pivot Low    
        if all(lows[i] <= lows[i-k] for k in range(1, 4)) and \
           all(lows[i] <= lows[i+k] for k in range(1, 4)):
            potential_levels.append(lows[i])
            
    potential_levels.sort()
    
    if not potential_levels:
        return []

    # 클러스터링
    merged_levels = []
    if potential_levels:
        current_cluster = [potential_levels[0]]
        for i in range(1, len(potential_levels)):
            price = potential_levels[i]
            avg_price = sum(current_cluster) / len(current_cluster)
            
            if abs(price - avg_price) / avg_price <= range_pct:
                current_cluster.append(price)
            else:
                if len(current_cluster) >= touch_threshold:
                    merged_levels.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [price]
                
        if len(current_cluster) >= touch_threshold:
            merged_levels.append(sum(current_cluster) / len(current_cluster))
        
    return merged_levels


def build_features(df, window_size=60):
    """
    각 캔들에 대해 저항선 레벨 피처 생성
    
    Args:
        df: OHLCV 데이터프레임
        window_size: 룩백 윈도우 크기
    
    Returns:
        list: 피처가 포함된 딕셔너리 리스트
    """
    final_data = []
    
    print("피처 생성 중...")
    for i in tqdm(range(len(df))):
        row = df.iloc[i]
        
        # 과거 데이터 슬라이싱
        if i < window_size:
            past_df = df.iloc[:i]
        else:
            past_df = df.iloc[i-window_size:i]
            
        current_res_levels = []

        if len(past_df) > 10:
            levels = find_sr_levels(past_df, lookback=window_size, range_pct=0.002, touch_threshold=2)
            
            # 현재가보다 위에 있는 레벨만 필터링
            current_price = row['close']
            current_res_levels = [lvl for lvl in levels if lvl > current_price]
            
            # 보조: 최근 고점 추가
            local_max = past_df['high'].max()
            if local_max > current_price:
                if not any(abs(l - local_max) < local_max * 0.001 for l in current_res_levels):
                    current_res_levels.append(local_max)

        # JSON 저장용 변환
        safe_res = [float(x) for x in sorted(current_res_levels)]
        
        feature_row = {
            "timestamp": int(row['timestamp'].timestamp() * 1000),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume']),
            "resistanceLevels_5m": json.dumps(safe_res),
            "res_trend_prices": json.dumps([])
        }
        final_data.append(feature_row)
    
    return final_data
