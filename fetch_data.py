# =========================================================
# 데이터 수집 실행 스크립트
# =========================================================

import warnings
warnings.filterwarnings("ignore")

from config.settings import DEFAULT_SYMBOL, DATA_FILE
from data.fetcher import get_historical_data_single, save_data
from data.features import build_features


def main(symbol=None, outfile=None):
    """
    바이낸스에서 데이터 수집 및 피처 생성
    
    Args:
        symbol: 심볼 (기본값: config에서 설정)
        outfile: 출력 파일 (기본값: config에서 설정)
    """
    if symbol is None:
        symbol = DEFAULT_SYMBOL
    if outfile is None:
        outfile = DATA_FILE
    
    # 1. 데이터 수집
    df = get_historical_data_single(symbol)
    
    if df.empty:
        print("데이터 수집 실패")
        return
    
    # 2. 피처 생성
    final_data = build_features(df)
    
    # 3. 저장
    save_data(final_data, outfile)


if __name__ == "__main__":
    main()
