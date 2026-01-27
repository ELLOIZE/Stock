# =========================================================
# 데이터 수집 모듈
# =========================================================

import time
import json
import pandas as pd
import ccxt
from tqdm import tqdm
from binance.client import Client

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    validate_api_credentials,
    TIMEFRAME,
    MAX_CANDLES
)


def get_binance_client():
    validate_api_credentials()
    return Client(BINANCE_API_KEY, BINANCE_API_SECRET)


def get_historical_data_single(symbol="BTC/USDT", max_rows=None):
    """
    바이낸스에서 5분봉 데이터 수집
    
    Args:
        symbol: 심볼 (예: "BTC/USDT")
        max_rows: 수집할 캔들 개수 (기본값: config에서 설정)
    
    Returns:
        DataFrame: OHLCV 데이터
    """
    if max_rows is None:
        max_rows = MAX_CANDLES
        
    binance = ccxt.binance()
    
    timeframe = TIMEFRAME
    limit_per_call = 1000  # 바이낸스 최대 요청 개수
    
    # 시작 시간 계산 (현재 시간 - max_rows개 캔들 시간)
    duration_ms = max_rows * 5 * 60 * 1000
    now = binance.milliseconds()
    since = now - duration_ms
    
    all_ohlcv = []
    
    print(f"[{symbol}] 데이터 수집 시작 ({max_rows}개 목표)...")
    
    pbar = tqdm(total=max_rows)
    
    retry_count = 0
    max_retries = 5
    
    while len(all_ohlcv) < max_rows:
        try:
            remaining = max_rows - len(all_ohlcv)
            limit = min(remaining, limit_per_call)
            
            ohlcv = binance.fetch_ohlcv(symbol, timeframe, since=since, limit=limit_per_call)
            
            if not ohlcv:
                print("더 이상 가져올 데이터가 없습니다.")
                break
            
            all_ohlcv.extend(ohlcv)
            pbar.update(len(ohlcv))
            
            # 다음 요청을 위해 'since' 업데이트
            last_timestamp = ohlcv[-1][0]
            since = last_timestamp + 1
            
            time.sleep(0.2)  # 속도 제한 증가
            
            if len(ohlcv) < limit_per_call and len(all_ohlcv) < max_rows:
                break
            
            retry_count = 0  # 성공 시 리셋
                
        except Exception as e:
            retry_count += 1
            print(f"데이터 수집 중 에러 발생 (시도 {retry_count}/{max_retries}): {e}")
            
            if retry_count >= max_retries:
                print("최대 재시도 횟수 도달. 데이터 수집 중단.")
                break
            
            wait_time = min(retry_count * 2, 10)  # 점진적으로 대기 시간 증가
            print(f"{wait_time}초 후 재시도...")
            time.sleep(wait_time)
            
    pbar.close()
    
    # 데이터프레임 변환
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # 중복 제거 및 정렬
    df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    # 정확히 max_rows 개수만큼 자르기
    if len(df) > max_rows:
        df = df.iloc[-max_rows:].reset_index(drop=True)
        
    print(f"최종 수집 완료: {len(df)}개")
    return df


def load_data(filepath):
    """저장된 JSON 데이터 로드"""
    return pd.read_json(filepath)


def save_data(data, filepath):
    """데이터를 JSON으로 저장"""
    with open(filepath, 'w') as f:
        json.dump(data, f)
    print(f"완료! {filepath} 저장됨. (데이터 개수: {len(data)})")
