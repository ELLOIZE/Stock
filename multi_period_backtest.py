# =========================================================
# Walk-Forward 백테스트 실행 스크립트
# =========================================================

import warnings
from tqdm import tqdm

warnings.filterwarnings("ignore")

from config.settings import (
    INITIAL_CAPITAL, DATA_FILE, STRATEGY_WEIGHTS,
    BACKTEST_WINDOW_SIZE, WALK_FORWARD_CONFIG
)
from data.fetcher import load_data
from data.features import compute_indicators
from strategies import BreakoutStrategy, MeanReversionStrategy
from engine import PortfolioManager
from analysis.stats import calculate_stats, aggregate_results, print_aggregated_stats


def generate_walk_forward_periods(total_candles, config):
    """
    Walk-Forward 기간 생성 (비중첩 테스트 기간)

    Args:
        total_candles: 전체 캔들 수
        config: WALK_FORWARD_CONFIG 딕셔너리

    Returns:
        list of dict: [{'in_sample': (start, end), 'out_sample': (start, end), 'period_name': str}, ...]
    """
    periods = []

    window_size = config['min_window_candles']
    in_sample_size = int(window_size * config['in_sample_ratio'])
    out_sample_size = int(window_size * config['out_sample_ratio'])
    step_size = config['step_candles']
    anchored = config['anchored']

    if anchored:
        # Anchored Walk-Forward: 시작점 고정, 점점 더 많은 in-sample 데이터 사용
        current_end = window_size
        period_num = 1
        while current_end + out_sample_size <= total_candles:
            in_start = 0
            in_end = current_end
            out_start = current_end
            out_end = min(current_end + out_sample_size, total_candles)

            periods.append({
                'in_sample': (in_start, in_end),
                'out_sample': (out_start, out_end),
                'period_name': f"WF_{period_num:03d}"
            })
            current_end += step_size
            period_num += 1
    else:
        # Rolling Walk-Forward: 윈도우가 이동 (비중첩)
        current_start = 0
        period_num = 1
        while current_start + in_sample_size + out_sample_size <= total_candles:
            in_start = current_start
            in_end = current_start + in_sample_size
            out_start = in_end
            out_end = in_end + out_sample_size

            periods.append({
                'in_sample': (in_start, in_end),
                'out_sample': (out_start, out_end),
                'period_name': f"WF_{period_num:03d}"
            })
            current_start += step_size
            period_num += 1

    return periods


def run_backtest_on_period(df_period, initial_capital):
    """
    단일 기간에 대한 백테스트 실행

    Args:
        df_period: 기간 데이터 DataFrame
        initial_capital: 초기 자본

    Returns:
        tuple: (trades_df, equity_curve_df, final_capital)
    """
    manager = PortfolioManager(initial_capital=initial_capital)

    manager.add_strategy(
        BreakoutStrategy("BREAKOUT"),
        weight=STRATEGY_WEIGHTS['BREAKOUT']
    )
    manager.add_strategy(
        MeanReversionStrategy("MEAN_REV"),
        weight=STRATEGY_WEIGHTS['MEAN_REV']
    )

    trades, equity_curve = manager.run_backtest(df_period)
    return trades, equity_curve, manager.current_capital


def run_walk_forward_backtest():
    """Walk-Forward 백테스트 실행 (메인 함수)"""
    print("=" * 60)
    print("Walk-Forward 백테스트 시작")
    print("=" * 60)

    # 1. 데이터 로드
    try:
        df = load_data(DATA_FILE)
        print(f"데이터 로드 완료: {len(df):,} 캔들")

        mem_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
        print(f"데이터 메모리 사용량: {mem_mb:.2f} MB")
    except Exception as e:
        print(f"{DATA_FILE} 파일이 없습니다. fetch_data.py를 먼저 실행하세요.")
        print(f"에러: {e}")
        return None

    # 2. 지표 계산 (전체 데이터에 대해 한 번만 계산)
    print(f"지표 계산 중...")
    df_ind = compute_indicators(df)
    print(f"지표 계산 완료: {len(df_ind):,} 캔들")

    # 3. Walk-Forward 기간 생성
    total_candles = len(df_ind)
    periods = generate_walk_forward_periods(total_candles, WALK_FORWARD_CONFIG)

    if not periods:
        print(f"오류: 데이터가 부족하여 Walk-Forward 기간을 생성할 수 없습니다.")
        print(f"  - 전체 캔들: {total_candles:,}")
        print(f"  - 필요한 최소 캔들: {WALK_FORWARD_CONFIG['min_window_candles'] + int(WALK_FORWARD_CONFIG['min_window_candles'] * WALK_FORWARD_CONFIG['out_sample_ratio']):,}")
        return None

    # Walk-Forward 설정 출력
    print(f"\n{'='*60}")
    print(f"Walk-Forward 설정:")
    print(f"  - 모드: {'Anchored (확장 윈도우)' if WALK_FORWARD_CONFIG['anchored'] else 'Rolling (이동 윈도우)'}")
    print(f"  - In-sample 비율: {WALK_FORWARD_CONFIG['in_sample_ratio']*100:.0f}%")
    print(f"  - Out-sample 비율: {WALK_FORWARD_CONFIG['out_sample_ratio']*100:.0f}%")
    print(f"  - 윈도우 크기: {WALK_FORWARD_CONFIG['min_window_candles']:,} 캔들 (~{WALK_FORWARD_CONFIG['min_window_candles'] * 5 / 60 / 24:.1f}일)")
    print(f"  - 스텝 크기: {WALK_FORWARD_CONFIG['step_candles']:,} 캔들 (~{WALK_FORWARD_CONFIG['step_candles'] * 5 / 60 / 24:.1f}일)")
    print(f"  - 생성된 기간 수: {len(periods)}")
    print(f"{'='*60}\n")

    # 4. 각 기간별 백테스트 실행 (Out-of-Sample 결과만 수집)
    results = []

    for i, period in enumerate(tqdm(periods, desc="Walk-Forward 진행")):
        period_name = period['period_name']
        out_start, out_end = period['out_sample']

        # Out-of-Sample 데이터로 백테스트
        out_sample_df = df_ind.iloc[out_start:out_end].reset_index(drop=True)

        trades, equity_curve, final_capital = run_backtest_on_period(
            out_sample_df,
            INITIAL_CAPITAL
        )

        # 통계 계산
        stats = calculate_stats(trades, INITIAL_CAPITAL, final_capital, equity_curve=equity_curve)
        stats['period_index'] = i + 1
        stats['period_name'] = period_name
        stats['out_sample_start'] = out_start
        stats['out_sample_end'] = out_end
        stats['in_sample_start'] = period['in_sample'][0]
        stats['in_sample_end'] = period['in_sample'][1]

        results.append(stats)

    # 5. 결과 집계
    aggregated = aggregate_results(results)

    # 6. 결과 출력
    window_size = WALK_FORWARD_CONFIG['min_window_candles']
    out_sample_size = int(window_size * WALK_FORWARD_CONFIG['out_sample_ratio'])
    print_aggregated_stats(aggregated, out_sample_size)

    # Walk-Forward 특화 요약
    print("\n" + "=" * 60)
    print("Walk-Forward 분석 요약")
    print("=" * 60)

    # 데이터 스누핑 방지 확인
    print(f"\n✓ 비중첩 Out-of-Sample 테스트: {len(periods)}개 기간")
    print(f"✓ 총 Out-of-Sample 캔들: {sum(p['out_sample'][1] - p['out_sample'][0] for p in periods):,}")
    print(f"✓ 테스트 커버리지: {sum(p['out_sample'][1] - p['out_sample'][0] for p in periods) / total_candles * 100:.1f}%")

    # 일관성 분석
    returns = aggregated['returns']['all_values']
    positive_periods = sum(1 for r in returns if r > 0)
    consistency_rate = positive_periods / len(returns) * 100
    print(f"\n일관성 분석:")
    print(f"  - 수익 기간: {positive_periods}/{len(returns)} ({consistency_rate:.1f}%)")
    print(f"  - 연속 손실 최대: {max_consecutive_negative(returns)}기간")

    return aggregated


def max_consecutive_negative(values):
    """연속 음수 값의 최대 개수 계산"""
    max_count = 0
    current_count = 0
    for v in values:
        if v < 0:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0
    return max_count


# 하위 호환성을 위한 별칭
run_multi_period_backtest = run_walk_forward_backtest


if __name__ == "__main__":
    aggregated_results = run_walk_forward_backtest()
