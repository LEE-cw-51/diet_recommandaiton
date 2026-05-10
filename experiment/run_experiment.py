"""실험 CLI 진입점.

사용법:
  # 실험 1 (2목적) — 기본 설정
  python experiment/run_experiment.py \\
      --config experiment/config/exp1_nsga2.yaml \\
      --cal_star 2000 --price_star 8000

  # 실험 2 (3목적) — 알레르겐 필터
  python experiment/run_experiment.py \\
      --config experiment/config/exp2_nsga2.yaml \\
      --cal_star 2000 --price_star 8000 \\
      --allergens 난류 우유

  # 빠른 검증 (테스트 모드: pop=10, gen=5, n_runs=2)
  python experiment/run_experiment.py \\
      --config experiment/config/exp1_nsga2.yaml \\
      --cal_star 2000 --price_star 8000 --test

  # 민감도 분석 (탄수화물 상한)
  python experiment/run_experiment.py \\
      --config experiment/config/exp1_nsga2_high_carb.yaml \\
      --cal_star 2000 --price_star 8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 스크립트를 직접 실행해도(`python experiment/run_experiment.py ...`)
# `experiment` 패키지 import가 가능하도록, 현재 파일 위치를 기준으로
# 프로젝트 루트를 먼저 계산해 sys.path에 추가한다.
_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

from experiment import _PROJECT_ROOT

# 패키지에서 정의한 프로젝트 루트를 다시 한번 보장
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="Diet Recommendation — 다목적 최적화 실험 실행기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", required=True,
        help="YAML 설정 파일 경로 (예: experiment/config/exp1_nsga2.yaml)",
    )
    parser.add_argument(
        "--cal_star", type=float, required=True,
        help="목표 칼로리 (kcal, 예: 2000)",
    )
    parser.add_argument(
        "--price_star", type=float, required=True,
        help="목표 가격 (원, 예: 8000)",
    )
    parser.add_argument(
        "--allergens", nargs="*", default=None,
        help="회피할 알레르겐 목록 (예: 난류 우유 땅콩)",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="테스트 모드: pop=10, gen=5, n_runs=2로 빠른 검증",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        # 프로젝트 루트 기준으로 재시도
        config_path = _PROJECT_ROOT / args.config
        if not config_path.exists():
            print(f"❌ 설정 파일을 찾을 수 없음: {args.config}")
            sys.exit(1)

    print(f"🔧 설정 파일: {config_path}")
    print(f"   Cal*: {args.cal_star} kcal | Price*: {args.price_star:,.0f}원")
    if args.allergens:
        print(f"   알레르겐 회피: {args.allergens}")

    from experiment.core.runner import run_experiment

    run_experiment(
        config_path=str(config_path),
        cal_star=args.cal_star,
        price_star=args.price_star,
        allergens=args.allergens,
        test_mode=args.test,
    )


if __name__ == "__main__":
    main()
