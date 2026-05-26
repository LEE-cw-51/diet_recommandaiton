"""Cold Start 해결 검증 — Cuisine 기반 초기 KG 하이브리드 초기화 Loop B.

기존 Loop B (KG_PREFERENCES = 비빔밥 4★, 된장찌개 3★):
  -> f4 = 0.2500 고정 (coldstart 문제)

이 스크립트 (cuisine_type = '한식' 전체에 pref=1.3):
  -> f4가 동적으로 변하는지 검증 (감쇠 후 회복 패턴 기대)

산출물: experiment/results/step1_coldstart/
  daily_f4_trend_coldstart.csv  : before/after 비교 CSV
  plot_coldstart_comparison.png : f4 추이 비교 플롯

사용법:
  python -X utf8 -m experiment.simulation.run_step1_coldstart
  python -X utf8 -m experiment.simulation.run_step1_coldstart --cuisine 한식 --weight 1.3
  python -X utf8 -m experiment.simulation.run_step1_coldstart --test
"""

from __future__ import annotations

import argparse
import csv
import sys
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

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1_coldstart"

# ──────────────────────────────────────────────────────────────────────────────
# 실험 상수 — 재현성 상수는 models.variants 단일 출처에서 가져옴
# ──────────────────────────────────────────────────────────────────────────────

from experiment.models.variants import (  # noqa: E402
    N_MEALS,
    REF_G3 as _REF_G3,
    SEED_START,
    TEST_USER,
)

BASE_DATE = datetime(2026, 5, 7, 12, 0, 0)

# 기존 coldstart 결과 (run_step1.py Loop B에서 측정)
COLDSTART_F4 = [0.2500] * 7


# ──────────────────────────────────────────────────────────────────────────────
# KG 초기화 — cuisine 기반 하이브리드
# ──────────────────────────────────────────────────────────────────────────────

def _build_kg_with_cuisine(
    all_foods: list[dict],
    cuisine: str,
    weight: float,
) -> "KGManager":  # noqa: F821
    """cuisine_type 기반으로 초기 KG를 대량 초기화.

    모든 메뉴 노드를 category + cuisine 정보와 함께 등록한 뒤,
    지정 cuisine에 속한 메뉴 전체에 선호도 weight를 부여한다.
    """
    from experiment.core.kg_manager import KGManager, make_menu_id

    kg = KGManager()

    for item in all_foods:
        mid = make_menu_id(item)
        if not mid:
            continue
        cat     = item.get("category_type", item.get("category", "UNKNOWN"))
        cuisine_val = item.get("cuisine_type")
        kg.add_menu(mid, category=cat, cuisine=cuisine_val)

    count = kg.set_cuisine_preference(TEST_USER, cuisine, weight)
    print(f"  [{cuisine}] {count}개 메뉴에 초기 선호도 {weight} 부여")
    return kg


# ──────────────────────────────────────────────────────────────────────────────
# Loop B — 7일 시뮬레이션
# ──────────────────────────────────────────────────────────────────────────────

def run_loop_b_coldstart(
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
    from experiment.simulation.simulate_kg import _run_one_day
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.core.nutrition import NutritionProfile

    kg      = _build_kg_with_cuisine(all_foods, cuisine, weight)
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
                "duplication_rate": np.nan,
            })
            print(f"  [Day {day}] 해 없음")
            prev_combo = None
            continue

        combo = problem.decode(best_X)
        menu_names = [
            str(item.get("product_name") or item.get("menu_name") or "")
            for item in combo
        ]
        f1, f2, f3, f4 = best_F

        prev_combo = combo
        menu_history.extend(menu_names)
        cnt = Counter(menu_history)
        repeated = sum(v - 1 for v in cnt.values() if v > 1)
        dup_rate = repeated / len(menu_history) if menu_history else 0.0

        import math
        menu_ids_today = [make_menu_id(item) for item in combo if make_menu_id(item)]
        kg_scores = []
        for mid in menu_ids_today:
            edata = kg.G.get_edge_data(TEST_USER, mid, default={})
            pref = float(edata.get("pref", 1.0))
            last_ate = edata.get("last_ate")
            decay = 0.0
            if last_ate is not None:
                delta_days = max(0.0, (today - last_ate).total_seconds() / 86400.0)
                decay = min(1.0, math.exp(-0.5 * delta_days))
            kg_scores.append(pref * (1 - decay))

        avg_kg = float(np.mean(kg_scores)) if kg_scores else 0.0
        max_s  = kg.max_possible_score(TEST_USER)

        daily_logs.append({
            "day": day, "date": today.strftime("%Y-%m-%d"),
            "f1": float(f1), "f2": float(f2),
            "f3": float(f3), "f4": float(f4),
            "duplication_rate": float(dup_rate),
        })

        print(f"  [Day {day}] f4={f4:.4f}  f1={f1:.4f}  중복률={dup_rate:.1%}"
              f"  avg_kg={avg_kg:.3f}  max_s={max_s:.3f}")

    return daily_logs


# ──────────────────────────────────────────────────────────────────────────────
# 저장 & 시각화
# ──────────────────────────────────────────────────────────────────────────────

def save_comparison_csv(out_dir: Path, logs: list[dict], cuisine: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "daily_f4_trend_coldstart.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "date", "f4_before", "f4_after"])
        writer.writeheader()
        for log in logs:
            day = log["day"]
            writer.writerow({
                "day":      day,
                "date":     log["date"],
                "f4_before": COLDSTART_F4[day - 1] if day <= len(COLDSTART_F4) else "",
                "f4_after":  log["f4"],
            })
    print(f"  CSV saved: {path}")


def plot_comparison(out_dir: Path, logs: list[dict], cuisine: str) -> None:
    if not HAS_MPL:
        print("  matplotlib 미설치 — 플롯 생략")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    days       = [log["day"] for log in logs]
    f4_after   = [log["f4"] for log in logs]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 좌측: before (coldstart)
    ax = axes[0]
    ax.plot(range(1, 8), COLDSTART_F4[:7], marker="o", color="red", linewidth=2)
    ax.set_title("Before (Cold Start)\nf4 = 0.25 fixed", fontsize=13)
    ax.set_xlabel("Day")
    ax.set_ylabel("f4 (KG error rate)")
    ax.set_ylim(0, 0.5)
    ax.set_xticks(range(1, 8))
    ax.grid(True, alpha=0.3)

    # 우측: after (cuisine 초기화)
    ax = axes[1]
    ax.plot(days, f4_after, marker="o", color="steelblue", linewidth=2)
    ax.set_title(f"After (Hybrid Init: {cuisine} pref=1.3)\nDynamic f4", fontsize=13)
    ax.set_xlabel("Day")
    ax.set_ylabel("f4 (KG error rate)")
    ax.set_ylim(0, 0.5)
    ax.set_xticks(range(1, 8))
    ax.grid(True, alpha=0.3)

    plt.suptitle("Cold Start Problem: Before vs After", fontsize=14, y=1.02)
    plt.tight_layout()

    path = out_dir / "plot_coldstart_comparison.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cold start 해결 Loop B 재실험")
    parser.add_argument("--cuisine",    default="한식",  help="초기화할 식문화 (default: 한식)")
    parser.add_argument("--weight",     type=float, default=1.3, help="선호도 가중치 (default: 1.3)")
    parser.add_argument("--cal_star",   type=float, default=2000.0)
    parser.add_argument("--price_star", type=float, default=8000.0)
    parser.add_argument("--days",       type=int,   default=7)
    parser.add_argument("--pop",        type=int,   default=200)
    parser.add_argument("--gen",        type=int,   default=200)
    parser.add_argument("--test",       action="store_true", help="빠른 테스트 (pop=20, gen=20)")
    args = parser.parse_args()

    if args.test:
        args.pop, args.gen = 20, 20
        print("[TEST MODE] pop=20, gen=20")

    print(f"Cold Start 해결 실험: cuisine={args.cuisine}, weight={args.weight}")
    print(f"  pop={args.pop}, gen={args.gen}, days={args.days}")

    from experiment.core.loader import FoodDataLoader
    loader = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks

    print(f"\n  데이터: MAIN={len(mains)}, SIDE_SOUP={len(sides_soup)}, "
          f"DRINK={len(drinks)}, SNACK={len(snacks)}")

    print(f"\n[Loop B] {args.days}일 시뮬레이션 시작...")
    logs = run_loop_b_coldstart(
        mains=mains,
        sides_soup=sides_soup,
        drinks=drinks,
        snacks=snacks,
        all_foods=all_foods,
        cal_star=args.cal_star,
        price_star=args.price_star,
        n_days=args.days,
        pop_size=args.pop,
        n_gen=args.gen,
        cuisine=args.cuisine,
        weight=args.weight,
    )

    print("\n[결과 요약]")
    print(f"  {'Day':>4}  {'f4_before':>10}  {'f4_after':>10}  {'f1':>8}  {'중복률':>8}")
    for log in logs:
        day = log["day"]
        f4_b = COLDSTART_F4[day - 1] if day <= len(COLDSTART_F4) else float("nan")
        print(f"  {day:>4}  {f4_b:>10.4f}  {log['f4']:>10.4f}  "
              f"{log['f1']:>8.4f}  {log['duplication_rate']:>8.1%}")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_comparison_csv(_OUT_DIR, logs, args.cuisine)
    plot_comparison(_OUT_DIR, logs, args.cuisine)
    print(f"\n완료. 결과 저장: {_OUT_DIR}")


if __name__ == "__main__":
    main()
