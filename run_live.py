#!/usr/bin/env python
# =========================================================
# 라이브 트레이딩 봇 실행 스크립트
# =========================================================

"""
BTC/USDT 자동매매 봇 실행

사용법:
    python run_live.py              # 일반 실행
    python run_live.py --dry-run    # 드라이런 모드 (실제 주문 안함)
    python run_live.py --status     # 현재 상태 확인
    python run_live.py --close-all  # 모든 포지션 청산
"""

import sys
import os
import argparse

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_environment():
    """환경 확인"""
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET
    
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        print("=" * 50)
        print("오류: Binance API 키가 설정되지 않았습니다!")
        print("=" * 50)
        print()
        print("1. .env 파일을 생성하세요:")
        print("   Copy-Item .env.example .env")
        print()
        print("2. .env 파일에 API 키를 입력하세요:")
        print("   BINANCE_API_KEY=your_api_key")
        print("   BINANCE_API_SECRET=your_api_secret")
        print()
        print("Binance API 키 발급:")
        print("  https://www.binance.com/en/my/settings/api-management")
        print()
        return False
    
    return True


def show_status():
    """현재 상태 표시"""
    from live.state import StateManager
    from live.client import BinanceFuturesClient
    from config.live_settings import LIVE_SYMBOL
    
    print("=" * 50)
    print("현재 상태 확인")
    print("=" * 50)
    
    # 저장된 상태 확인
    state_manager = StateManager()
    if state_manager.state_exists():
        state = state_manager.load_state()
        print(f"\n저장된 상태:")
        print(f"  - 저장 시간: {state.get('saved_at', 'N/A')}")
        print(f"  - 포지션 수: {len(state.get('positions', {}))}")
        print(f"  - 자본: ${state.get('current_capital', 0):.2f}")
    else:
        print("\n저장된 상태 없음")
    
    # 거래소 상태 확인
    try:
        client = BinanceFuturesClient()
        
        if client.ping():
            print(f"\nBinance API 연결: OK")
            
            balance = client.get_usdt_balance()
            print(f"USDT 잔고: ${balance:.2f}")
            
            position = client.get_open_position(LIVE_SYMBOL)
            if position and float(position['positionAmt']) != 0:
                print(f"\n열린 포지션:")
                print(f"  - 심볼: {position['symbol']}")
                print(f"  - 수량: {position['positionAmt']}")
                print(f"  - 진입가: {position['entryPrice']}")
                print(f"  - 미실현 PnL: ${float(position['unRealizedProfit']):.2f}")
            else:
                print(f"\n열린 포지션: 없음")
        else:
            print(f"\nBinance API 연결: 실패")
            
    except Exception as e:
        print(f"\n거래소 상태 확인 실패: {e}")


def close_all_positions():
    """모든 포지션 청산"""
    from live.client import BinanceFuturesClient
    from live.order_manager import OrderManager
    from config.live_settings import LIVE_SYMBOL
    
    print("=" * 50)
    print("모든 포지션 청산")
    print("=" * 50)
    
    try:
        client = BinanceFuturesClient()
        order_manager = OrderManager(client, LIVE_SYMBOL)
        
        result = order_manager.close_all_positions()
        
        if result:
            print(f"\n청산 완료:")
            print(f"  - 수량: {result.get('quantity', 0)}")
            print(f"  - 가격: {result.get('avg_price', 0):.2f}")
        else:
            print("\n청산할 포지션이 없습니다")
            
    except Exception as e:
        print(f"\n청산 실패: {e}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='BTC/USDT 자동매매 봇')
    parser.add_argument('--dry-run', action='store_true', 
                        help='드라이런 모드 (실제 주문 안함)')
    parser.add_argument('--status', action='store_true',
                        help='현재 상태 확인')
    parser.add_argument('--close-all', action='store_true',
                        help='모든 포지션 청산')
    
    args = parser.parse_args()
    
    # 환경 확인
    if not check_environment():
        return
    
    # 상태 확인
    if args.status:
        show_status()
        return
    
    # 포지션 청산
    if args.close_all:
        confirm = input("정말 모든 포지션을 청산하시겠습니까? (yes/no): ")
        if confirm.lower() == 'yes':
            close_all_positions()
        else:
            print("취소됨")
        return
    
    # 드라이런 모드 설정
    if args.dry_run:
        import config.live_settings as settings
        settings.DRY_RUN_MODE = True
        print("드라이런 모드 활성화")
    
    # 봇 실행
    from live.bot import TradingBot
    
    bot = TradingBot()
    
    if bot.initialize():
        try:
            bot.start()
        except KeyboardInterrupt:
            print("\n중지 요청...")
            bot.stop()
    else:
        print("봇 초기화 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
