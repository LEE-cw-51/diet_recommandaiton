"""Step 2: 식문화별 G1/G2/G3 알고리즘 비교 실험.

5개 식문화(한식/양식/분식/중식/일식) 선호 유저 시나리오에서 G1/G2/G3 비교.
각 식문화 전체 메뉴에 pref=1.3 초기화 → cold-start 없는 현실적 비교.

G1/G2/G3 구성:
  G1: NSGA-II,         f1/f2/f3 (3목적, KG 미사용)
  G2: R-NSGA-II,       f1/f2/f3 (3목적, KG 미사용)
  G3: R-NSGA-II + KG,  f1/f2/f3/f4 (4목적, KG f4 사용)

식문화별 KG 초기화는 G3의 f4 목적함수에만 영향.

산출물: experiment/results/step2_cuisine/
  {cuisine}/metrics_comparison.csv
  {cuisine}/daily_f4_trend.csv
  {cuisine}/daily_duplication.csv
  {cuisine}/plot_convergence.png
  {cuisine}/plot_metrics_boxplot.png
  {cuisine}/plot_metrics_bar.png
  {cuisine}/plot_7days_f4.png
  cuisine_summary.csv               (식문화별 G3 지표 요약)
  plot_cuisine_f4_comparison.png    (5개 식문화 f4 추이 비교)

사용법:
  python -X utf8 -m experiment.simulation.run_step2_cuisine --test
  python -X utf8 -m experiment.simulation.run_step2_cuisine --cuisines 한식 양식
  python -X utf8 -m experiment.simulation.run_step2_cuisine
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
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

# ── 계산 로직 재사용 (simulation.run_step1) ─────────────────────────────────
from experiment.simulation.run_step1 import (  # noqa: E402
    run_loop_a,
    compute_loop_a_metrics,
    compute_wilcoxon,
    save_metrics_csv,
    save_perrun_metrics_csv,
    save_daily_csvs,
    print_summary,
)
# ── 시각화 함수 재사용 (visualization.plot_step1 — 데이터 인자 직접 수용) ────
from experiment.visualization.plot_step1 import (  # noqa: E402
    plot_convergence,
    plot_7days_f4,
    plot_metrics_boxplot,
    plot_metrics_bar,
)
# ── 모델 변형 상수 (models.variants 단일 출처) ──────────────────────────────
from experiment.models.variants import (  # noqa: E402
    N_MEALS,
    REF_G3 as _REF_G3,
    SEED_START,
    TEST_USER,
)

# ── 상수 ───────────────────────────────────────────────────────────────────────
CUISINES       = ["한식", "양식", "분식", "중식", "일식"]
CUISINE_WEIGHT = 1.3
BASE_DATE      = datetime(2026, 5, 7, 12, 0, 0)

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step2_cuisine"

_CUISINE_COLORS = {
    "한식": "#e74c3c",
    "양식": "#2980b9",
    "분식": "#27ae60",
    "중식": "#f39c12",
    "일식": "#8e44ad",
}


# ──────────────────────────────────────────────────────────────────────────────
# Cuisine 기반 KG 초기화
# ──────────────────────────────────────────────────────────────────────────────

def _build_kg_cuisine(
    all_foods: list[dict],
    cuisine: str,
    weight: float,
) -> "KGManager":  # noqa: F821
    """식문화 기반 KG 초기화: 해당 cuisine의 모든 메뉴에 pref=weight 부여."""
    from experiment.core.kg_manager import KGManager, make_menu_id

    kg = KGManager()
    for item in all_foods:
        mid = make_menu_id(item)
        if not mid:
            continue
        cat         = item.get("category_type", item.get("category", "UNKNOWN"))
        cuisine_val = item.get("cuisine_type")
        kg.add_menu(mid, category=cat, cuisine=cuisine_val)

    count = kg.set_cuisine_preference(TEST_USER, cuisine, weight)
    print(f"  [{cuisine}] {count}개 메뉴에 pref={weight} 부여  "
          f"(max_score={kg.max_possible_score(TEST_USER):.3f})")
    return kg


# ──────────────────────────────────────────────────────────────────────────────
# Loop B — cuisine KG 기반 7일 시뮬레이션
# ──────────────────────────────────────────────────────────────────────────────

def run_loop_b_cuisine(
    mains: list[dict],
    sides_soup: list[dict],
    drinks: list[dict],
    snacks: list[dict],
    all_foods: list[dict],
    cal_star: float,
    price_star: float,
    n_days: int,
    pop_size: int,
    n_gen: int,
    cuisine: str,
    weight: float,
) -> list[dict]:
    """G3 n_days일 시뮬레이션 (cuisine KG 기반).

    run_simulation_step1.run_loop_b와 동일하나, KG 초기화를 cuisine 기반으로 변경.
    """
    from experiment.simulation.simulate_kg import _run_one_day
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.core.nutrition import NutritionProfile

    kg      = _build_kg_cuisine(all_foods, cuisine, weight)
    profile = NutritionProfile.who2025()

    daily_logs: list[dict] = []
    menu_history: list[str] = []
    prev_combo = None

    for day in range(1, n_days + 1):
        today = BASE_DATE + timedelta(days=day - 1)
        seed  = SEED_START + day

        if prev_combo is not None:
            for item in prev_combo:
                mid = make_menu_id(item)
                if mid:
                    kg.record_eating(TEST_USER, mid, today)

        problem = DailyExp3Problem(
            mains=mains, sides_soup=sides_soup,
            drinks=drinks, snacks=snacks,
            n_meals=N_MEALS, include_snack=False,
            cal_star=cal_star, price_per_meal_star=price_star,
            profile=profile,
            kg_manager=kg,
            user_id=TEST_USER,
            lambda_decay=0.5,
            sim_now=today,
        )

        best_F, best_X = _run_one_day(problem, pop_size, n_gen, seed, _REF_G3)

        if best_F is None:
            daily_logs.append({
                "day": day, "date": today.strftime("%Y-%m-%d"),
                "f1": np.nan, "f2": np.nan, "f3": np.nan, "f4": np.nan,
                "menu_names": [], "categories": [], "duplication_rate": np.nan,
            })
            print(f"  [Loop B][{cuisine}] Day {day}: 해 없음")
            prev_combo = None
            continue

        combo      = problem.decode(best_X)
        menu_names = [
            str(item.get("product_name") or item.get("menu_name") or "")
            for item in combo
        ]
        categories = [item.get("category", "UNKNOWN") for item in combo]
        f1, f2, f3, f4 = best_F

        prev_combo = combo
        menu_history.extend(menu_names)
        cnt      = Counter(menu_history)
        repeated = sum(v - 1 for v in cnt.values() if v > 1)
        dup_rate = repeated / len(menu_history) if menu_history else 0.0

        menu_ids_today = [make_menu_id(item) for item in combo if make_menu_id(item)]
        kg_scores = []
        for mid in menu_ids_today:
            edata    = kg.G.get_edge_data(TEST_USER, mid, default={})
            pref     = float(edata.get("pref", 1.0))
            last_ate = kg._get_last_ate(TEST_USER, mid)
            if last_ate is not None:
                delta_days = max(0.0, (today - last_ate).total_seconds() / 86400.0)
                decay = min(1.0, math.exp(-0.5 * delta_days))
            else:
                decay = 0.0
            kg_scores.append(pref * (1 - decay))

        avg_kg = float(np.mean(kg_scores)) if kg_scores else 0.0
        max_s  = kg.max_possible_score(TEST_USER)

        daily_logs.append({
            "day": day, "date": today.strftime("%Y-%m-%d"),
            "f1": float(f1), "f2": float(f2),
            "f3": float(f3), "f4": float(f4),
            "menu_names": menu_names, "categories": categories,
            "menu_ids": menu_ids_today,
            "duplication_rate": float(dup_rate),
        })

        print(f"  [Loop B][{cuisine}] Day {day}: "
              f"f4={f4:.4f}  f1={f1:.4f}  중복률={dup_rate:.1%}  "
              f"avg_kg={avg_kg:.3f}  max_s={max_s:.3f}")

    return daily_logs


# ──────────────────────────────────────────────────────────────────────────────
# 식문화간 비교 저장 / 시각화
# ──────────────────────────────────────────────────────────────────────────────

def save_kg_eaten_sequence(out_dir: Path, daily_logs: list[dict]) -> None:
    """Loop B 일별 섭취 메뉴 시퀀스를 JSON으로 저장 (시각화 Figure 3 재생용).

    plot_step2.plot_kg_visualization 이 이 파일을 재생해 Day7 KG를 재구성하므로,
    시각화 단계에서 최적화를 재실행하지 않아도 된다.
    """
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "kg_eaten_sequence.json"
    seq = [
        {
            "day":      log["day"],
            "date":     log["date"],
            "menu_ids": log.get("menu_ids", []),
        }
        for log in daily_logs
        if log.get("menu_ids")
    ]
    with path.open("w", encoding="utf-8") as f:
        json.dump(seq, f, ensure_ascii=False, indent=2)
    print(f"  JSON saved: {path.name}")


def save_cuisine_summary_csv(out_dir: Path, summary_rows: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cuisine_summary.csv"
    if not summary_rows:
        return
    fieldnames = list(summary_rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(summary_rows)
    print(f"  CSV saved: {path.name}")


def plot_cuisine_f4_comparison(
    out_dir: Path,
    cuisine_logs: dict[str, list[dict]],
) -> None:
    """5개 식문화 × 7일 f4 추이를 한 그래프에 오버레이."""
    if not HAS_MPL or not cuisine_logs:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))

    for cuisine, logs in cuisine_logs.items():
        valid = [lg for lg in logs if not np.isnan(lg.get("f4", np.nan))]
        if not valid:
            continue
        days = [lg["day"] for lg in valid]
        f4   = [lg["f4"]  for lg in valid]
        color = _CUISINE_COLORS.get(cuisine, "gray")
        ax.plot(days, f4, "o-", color=color, linewidth=2, label=cuisine)

    ax.set_xlabel("Day", fontsize=12)
    ax.set_ylabel("f4 (KG Error Rate)", fontsize=12)
    ax.set_title("Loop B: f4 Trend by Cuisine Preference", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = out_dir / "plot_cuisine_f4_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved: {path.name}")


def plot_cuisine_loop_a_summary(
    out_dir: Path,
    cuisine_metrics: dict[str, dict],
) -> None:
    """5개 식문화별 G3 Loop A 지표(HV/GD+/IGD+) 바 차트."""
    if not HAS_MPL or not cuisine_metrics:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    cuisines = list(cuisine_metrics.keys())
    n = len(cuisines)

    metric_defs = [("hv", "HV (↑)"), ("gdp", "GD+ (↓)"), ("igdp", "IGD+ (↓)")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle("Loop A (G3): Metric Comparison by Cuisine", fontsize=13)

    for ax, (mkey, mlabel) in zip(axes, metric_defs):
        means = []
        stds  = []
        colors = []
        for c in cuisines:
            vals = [x for x in cuisine_metrics[c].get(mkey, []) if not np.isnan(x)]
            means.append(float(np.nanmean(vals)) if vals else 0.0)
            stds.append(float(np.nanstd(vals)) if vals else 0.0)
            colors.append(_CUISINE_COLORS.get(c, "gray"))

        x = np.arange(n)
        bars = ax.bar(x, means, yerr=stds, capsize=4,
                      color=colors, alpha=0.8,
                      error_kw=dict(elinewidth=1.2, ecolor="gray"))
        for bar, mean in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(stds + [0]) * 0.1,
                    f"{mean:.3f}", ha="center", va="bottom", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels(cuisines, fontsize=9)
        ax.set_title(mlabel, fontsize=11)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    plt.tight_layout()
    path = out_dir / "plot_cuisine_loop_a_summary.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved: {path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="식문화별 G1/G2/G3 알고리즘 비교 실험")
    parser.add_argument("--cuisines",    nargs="*", default=CUISINES,
                        help=f"실험할 식문화 목록 (default: {CUISINES})")
    parser.add_argument("--weight",      type=float, default=CUISINE_WEIGHT)
    parser.add_argument("--cal_star",    type=float, default=2000.0)
    parser.add_argument("--price_star",  type=float, default=8000.0)
    parser.add_argument("--n_runs",      type=int,   default=30)
    parser.add_argument("--n_days",      type=int,   default=7)
    parser.add_argument("--pop_size",    type=int,   default=200)
    parser.add_argument("--n_gen",       type=int,   default=200)
    parser.add_argument("--test",        action="store_true",
                        help="빠른 테스트 (pop=10, gen=20, runs=3, days=2)")
    parser.add_argument("--skip_loop_b", action="store_true")
    args = parser.parse_args()

    if args.test:
        args.pop_size, args.n_gen = 10, 20
        args.n_runs,   args.n_days = 3, 2
        print("[TEST MODE] pop=10, gen=20, runs=3, days=2")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 데이터 로딩 (공통) ────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  Supabase 데이터 로딩")
    from experiment.core.loader import FoodDataLoader
    from experiment.core.metrics import compute_reference_pf

    loader     = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks
    print(f"  MAIN:{len(mains)} SIDE_SOUP:{len(sides_soup)} "
          f"DRINK:{len(drinks)} SNACK:{len(snacks)}")

    # ── 식문화별 실험 루프 ────────────────────────────────────────────────────
    all_cuisine_summaries: list[dict] = []
    cuisine_logs_for_plot: dict[str, list[dict]] = {}
    cuisine_g3_metrics: dict[str, dict] = {}

    for cuisine in args.cuisines:
        print(f"\n{'='*65}")
        print(f"  [{cuisine}] 실험 시작  (pop={args.pop_size}, gen={args.n_gen})")
        print("=" * 65)

        out_dir = _OUT_DIR / cuisine
        out_dir.mkdir(parents=True, exist_ok=True)

        # KG 초기화
        kg_base = _build_kg_cuisine(all_foods, cuisine, args.weight)

        # ── Loop A ───────────────────────────────────────────────────────────
        print(f"\n  Loop A: G1/G2/G3 x {args.n_runs}회 독립 실행 [{cuisine}]")
        groups = run_loop_a(
            mains, sides_soup, drinks, snacks, kg_base,
            args.cal_star, args.price_star,
            args.n_runs, args.pop_size, args.n_gen,
        )

        # Reference Front & Nadir
        F_3d_list = [F for g in ("G1", "G2") for F in groups[g]["F_list"] if len(F) > 0]
        F_4d_list = [F for F in groups["G3"]["F_list"] if len(F) > 0]

        if not F_3d_list or not F_4d_list:
            print(f"  [{cuisine}] 유효한 해 없음 — 건너뜀")
            continue

        all_F_3d  = np.vstack(F_3d_list)
        ref_3d    = compute_reference_pf(all_F_3d)
        nadir_3d  = all_F_3d.max(axis=0) * 1.1

        all_F_4d  = np.vstack(F_4d_list)
        ref_4d    = compute_reference_pf(all_F_4d)
        nadir_4d  = all_F_4d.max(axis=0) * 1.1

        ref_map   = {"G1": ref_3d,   "G2": ref_3d,   "G3": ref_4d}
        nadir_map = {"G1": nadir_3d, "G2": nadir_3d, "G3": nadir_4d}

        metrics = compute_loop_a_metrics(groups, ref_map, nadir_map)
        p_vals  = compute_wilcoxon(metrics)
        print_summary(metrics, p_vals)

        save_metrics_csv(out_dir, metrics, p_vals, args.n_runs)
        save_perrun_metrics_csv(out_dir, metrics)

        if HAS_MPL:
            plot_convergence(out_dir, groups, nadir_map, args.n_gen)
            plot_metrics_boxplot(out_dir, metrics, p_vals)
            plot_metrics_bar(out_dir, metrics, p_vals)

        # G3 지표 수집 (식문화간 비교용)
        cuisine_g3_metrics[cuisine] = metrics.get("G3", {})

        # ── Loop B ───────────────────────────────────────────────────────────
        daily_logs: list[dict] = []
        if not args.skip_loop_b:
            print(f"\n  Loop B: G3 {args.n_days}일 시뮬레이션 [{cuisine}]")
            daily_logs = run_loop_b_cuisine(
                mains, sides_soup, drinks, snacks, all_foods,
                args.cal_star, args.price_star,
                args.n_days, args.pop_size, args.n_gen,
                cuisine=cuisine, weight=args.weight,
            )
            save_daily_csvs(out_dir, daily_logs)
            save_kg_eaten_sequence(out_dir, daily_logs)
            if HAS_MPL:
                plot_7days_f4(out_dir, daily_logs)

        cuisine_logs_for_plot[cuisine] = daily_logs

        # 요약 수집
        g3 = metrics.get("G3", {})
        valid_f4 = [lg["f4"] for lg in daily_logs if not np.isnan(lg.get("f4", np.nan))]
        valid_dr = [lg["duplication_rate"] for lg in daily_logs
                    if not np.isnan(lg.get("duplication_rate", np.nan))]
        all_cuisine_summaries.append({
            "cuisine":                cuisine,
            "kg_menu_count":          kg_base.G.number_of_edges(),
            "loop_a_g3_hv_mean":      f"{float(np.nanmean(g3.get('hv', [np.nan]))):.6f}",
            "loop_a_g3_hv_std":       f"{float(np.nanstd(g3.get('hv', [np.nan]))):.6f}",
            "loop_a_g3_gdp_mean":     f"{float(np.nanmean(g3.get('gdp', [np.nan]))):.6f}",
            "loop_a_g3_igdp_mean":    f"{float(np.nanmean(g3.get('igdp', [np.nan]))):.6f}",
            "loop_a_g3_time_mean":    f"{float(np.nanmean(g3.get('times', [np.nan]))):.3f}",
            "loop_b_f4_mean":         f"{float(np.mean(valid_f4)):.6f}"  if valid_f4 else "nan",
            "loop_b_f4_std":          f"{float(np.std(valid_f4)):.6f}"   if valid_f4 else "nan",
            "loop_b_dup_rate_mean":   f"{float(np.mean(valid_dr)):.6f}"  if valid_dr else "nan",
        })

        print(f"\n  [{cuisine}] 완료 -> {out_dir}")

    # ── 식문화간 요약 ─────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  식문화간 비교 요약")
    print("=" * 65)

    save_cuisine_summary_csv(_OUT_DIR, all_cuisine_summaries)

    if HAS_MPL:
        if not args.skip_loop_b:
            plot_cuisine_f4_comparison(_OUT_DIR, cuisine_logs_for_plot)
        plot_cuisine_loop_a_summary(_OUT_DIR, cuisine_g3_metrics)

    # 요약 출력
    print(f"\n  {'Cuisine':8s}  {'KG메뉴':>6s}  {'G3 HV':>10s}  "
          f"{'G3 GD+':>10s}  {'f4 평균':>10s}  {'중복률':>8s}")
    for row in all_cuisine_summaries:
        print(f"  {row['cuisine']:8s}  {row['kg_menu_count']:>6d}  "
              f"{row['loop_a_g3_hv_mean']:>10s}  {row['loop_a_g3_gdp_mean']:>10s}  "
              f"{row['loop_b_f4_mean']:>10s}  {row['loop_b_dup_rate_mean']:>8s}")

    print(f"\n완료. 결과 저장: {_OUT_DIR}")


if __name__ == "__main__":
    main()
