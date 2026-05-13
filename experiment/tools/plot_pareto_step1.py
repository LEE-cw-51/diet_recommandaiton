"""G1/G2/G3 Pareto Front 2D 투영 시각화.

run_simulation_step1.py의 _run_once / _build_kg / _make_* 를 재사용해
5 runs(기본) 실행 후 각 알고리즘의 머지 Pareto Front를 2D 투영 scatter로 시각화.

목적함수 차원:
  G1, G2: 3목적 (f1, f2, f3)        → f4 관련 페어에는 마커 표시 안 됨
  G3:     4목적 (f1, f2, f3, f4)    → 6개 페어 모두 표시

2×3 subplot — C(4,2)=6쌍:
  (f1,f2) (f1,f3) (f1,f4) (f2,f3) (f2,f4) (f3,f4)

사용법:
  python -X utf8 -m experiment.tools.plot_pareto_step1          # 본실행 (5 runs, ~3분)
  python -X utf8 -m experiment.tools.plot_pareto_step1 --test   # 빠른 검증 (2 runs)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("⚠ matplotlib 미설치 — pip install matplotlib")

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1"

# run_simulation_step1에서 상수 및 헬퍼 재사용
from experiment.tools.run_simulation_step1 import (  # noqa: E402
    _REF_G2, _REF_G3,
    _build_kg, _make_nsga2, _make_rnsga2, _run_once,
    SEED_START, TEST_USER,
)


def _collect_pareto(
    problem,
    algo_factory,
    n_runs: int,
    n_gen: int,
) -> np.ndarray:
    """n_runs회 실행 후 모든 feasible F를 vstack → 비지배 해 추출."""
    from experiment.core.metrics import compute_reference_pf

    all_F_list = []
    for i in range(n_runs):
        seed = SEED_START + i
        algo = algo_factory()
        F, _, _ = _run_once(problem, algo, n_gen, seed)
        if len(F) > 0:
            all_F_list.append(F)

    if not all_F_list:
        return np.empty((0, problem.n_obj))

    all_F = np.vstack(all_F_list)
    return compute_reference_pf(all_F)


def plot_pareto_scatter(
    g1_pf: np.ndarray,
    g2_pf: np.ndarray,
    g3_pf: np.ndarray,
    ref_front: np.ndarray,
    out_dir: Path,
) -> None:
    """G1/G2/G3 Pareto Front 2D 투영 — 1×3 subplot."""
    if not HAS_MPL:
        print("⚠ matplotlib 없음 — 그래프 생략")
        return

    # 목적함수 인덱스 (0-based) — 4목적 전체 조합 C(4,2)=6
    PAIRS = [
        (0, 1, "f1 (Calorie Error)",  "f2 (Macro Ratio Error)"),
        (0, 2, "f1 (Calorie Error)",  "f3 (Price Error)"),
        (0, 3, "f1 (Calorie Error)",  "f4 (KG Error Rate)"),
        (1, 2, "f2 (Macro Ratio Error)", "f3 (Price Error)"),
        (1, 3, "f2 (Macro Ratio Error)", "f4 (KG Error Rate)"),
        (2, 3, "f3 (Price Error)",    "f4 (KG Error Rate)"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()
    fig.suptitle("Pareto Front Projection: G1 vs G2 vs G3 (All 6 Pairs)", fontsize=13)

    styles = {
        "G1 (NSGA-II, 3-obj)":      (g1_pf,    "gray",   "x",  60, 0.7),
        "G2 (R-NSGA-II, 3-obj)":    (g2_pf,    "#4477AA","^",  50, 0.75),
        "G3 (R-NSGA-II + KG, 4-obj)":(g3_pf,   "#EE6677","o",  55, 0.85),
        "Reference Front (4D from G3)":(ref_front, "black",  "*",  80, 1.0),
    }

    for ax, (xi, yi, xlabel, ylabel) in zip(axes, PAIRS):
        for label, (pf, color, marker, size, alpha) in styles.items():
            if len(pf) == 0:
                continue
            # 그룹의 PF 차원이 인덱스(xi, yi)를 커버하지 못하면 누락 (G1/G2의 f4 페어)
            if pf.shape[1] <= max(xi, yi):
                continue
            ax.scatter(
                pf[:, xi], pf[:, yi],
                label=label, color=color, marker=marker,
                s=size, alpha=alpha, linewidths=0.8,
            )
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.4)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="lower center", ncol=4,
        fontsize=9, bbox_to_anchor=(0.5, -0.08),
        frameon=True,
    )

    plt.tight_layout()
    out_path = out_dir / "plot_pareto_scatter.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  🖼  plot_pareto_scatter.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="G1/G2/G3 Pareto Front 시각화")
    parser.add_argument("--cal_star",   type=float, default=2000.0)
    parser.add_argument("--price_star", type=float, default=8000.0)
    parser.add_argument("--test",       action="store_true",
                        help="빠른 검증 모드 (pop=10, gen=20, runs=2)")
    args = parser.parse_args()

    pop_size = 200
    n_gen    = 200
    n_runs   = 5

    if args.test:
        pop_size = 10
        n_gen    = 20
        n_runs   = 2
        print("⚡ [TEST MODE] pop=10, gen=20, runs=2")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 데이터 로딩 ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  📦 Supabase 데이터 로딩")
    from experiment.core.loader import FoodDataLoader
    loader = FoodDataLoader.from_supabase()
    cats = loader.get_category_lists(allergens_to_avoid=None)
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks
    print(f"  총 {len(all_foods)}개 음식 로딩 완료")

    # ── KG 초기화 (고정) ─────────────────────────────────────────────────────
    kg_base = _build_kg(all_foods)
    print(f"  🔗 KG 초기화: nodes={kg_base.G.number_of_nodes()}  edges={kg_base.G.number_of_edges()}")

    # ── Problem 생성 ─────────────────────────────────────────────────────────
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.nutrition import NutritionProfile

    profile = NutritionProfile.who2025()

    # G1/G2: 3목적 problem / G3: 4목적 problem
    problem_3obj = DailyExp3Problem(
        mains=mains, sides_soup=sides_soup, drinks=drinks, snacks=snacks,
        n_meals=3, include_snack=False,
        cal_star=args.cal_star, price_per_meal_star=args.price_star,
        profile=profile,
        kg_manager=kg_base,
        user_id=TEST_USER,
        lambda_decay=0.5,
        use_f4=False,
    )
    problem_4obj = DailyExp3Problem(
        mains=mains, sides_soup=sides_soup, drinks=drinks, snacks=snacks,
        n_meals=3, include_snack=False,
        cal_star=args.cal_star, price_per_meal_star=args.price_star,
        profile=profile,
        kg_manager=kg_base,
        user_id=TEST_USER,
        lambda_decay=0.5,
        use_f4=True,
    )

    # ── G1/G2/G3 각 n_runs회 실행 → 머지 Pareto ────────────────────────────
    print(f"\n  🚀 Pareto 수집 ({n_runs}runs × 3 groups, pop={pop_size}, gen={n_gen})")
    print("=" * 60)

    from experiment.core.metrics import compute_reference_pf

    print("  [G1] NSGA-II (3-obj) ...")
    g1_pf = _collect_pareto(
        problem_3obj,
        lambda: _make_nsga2(pop_size),
        n_runs, n_gen,
    )
    print(f"    → {len(g1_pf)}해")

    print("  [G2] R-NSGA-II (3-obj, no KG) ...")
    g2_pf = _collect_pareto(
        problem_3obj,
        lambda: _make_rnsga2(pop_size, _REF_G2),
        n_runs, n_gen,
    )
    print(f"    → {len(g2_pf)}해")

    print("  [G3] R-NSGA-II + KG (4-obj) ...")
    g3_pf = _collect_pareto(
        problem_4obj,
        lambda: _make_rnsga2(pop_size, _REF_G3),
        n_runs, n_gen,
    )
    print(f"    → {len(g3_pf)}해")

    # ── Reference Front (G3 4D 단독 — 차원 다른 G1/G2와 머지 불가) ─────────
    if len(g3_pf) == 0 and len(g1_pf) == 0 and len(g2_pf) == 0:
        print("⚠ 모든 그룹에서 실행 가능한 해 없음. 종료.")
        return

    if len(g3_pf) > 0:
        ref_front = compute_reference_pf(g3_pf)
        print(f"\n  📐 Reference Front (4D from G3): {len(ref_front)}해")
    else:
        ref_front = np.empty((0, 4))
        print("\n  ⚠ G3 PF 없음 — Reference Front 빈 배열")

    # ── 시각화 ───────────────────────────────────────────────────────────────
    print("\n  🖼  그래프 생성")
    plot_pareto_scatter(g1_pf, g2_pf, g3_pf, ref_front, _OUT_DIR)

    print(f"\n✅ 완료! → {_OUT_DIR}")


if __name__ == "__main__":
    main()
