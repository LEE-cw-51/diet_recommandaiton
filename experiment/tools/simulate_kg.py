"""7일 식단 시뮬레이션 — KG 기반 개인화·다양성 검증.

목적:
  DailyExp3Problem + KGManager의 시간 감쇠·선호도 로직이
  의도대로 동작하는지 가상 사용자 시나리오로 검증한다.

검증 포인트:
  1. 선호 카테고리가 일관되게 식단에 포함되는가 (Hit Rate)
  2. 어제 먹은 메뉴가 오늘 식단에서 밀려나는가 (Time Decay 작동)
  3. 7일 동안 영양 오차(f1, f2)가 허용 범위(10%) 이내인가
  4. 카테고리가 특정 메뉴로 편중되지 않는가 (Diversity)

사용법:
  python -X utf8 -m experiment.tools.simulate_kg --days 7 --cal_star 2000 --price_star 8000
  python -X utf8 -m experiment.tools.simulate_kg --days 7 --cal_star 2000 --price_star 8000 --test
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from experiment import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ──────────────────────────────────────────────────────────────────────────────
# 가상 사용자 페르소나 정의
# ──────────────────────────────────────────────────────────────────────────────

PERSONAS = {
    "한식_매니아": {
        "description": "MAIN 카테고리 선호, DRINK 비선호",
        "preferences": {
            "MAIN": 1.5,
            "SIDE_SOUP": 1.2,
            "DRINK": 0.5,
            "SNACK": 0.8,
        },
    },
    "가성비_추구": {
        "description": "SNACK·DRINK 선호, MAIN 보통",
        "preferences": {
            "MAIN": 1.0,
            "SIDE_SOUP": 0.9,
            "DRINK": 1.3,
            "SNACK": 1.4,
        },
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 단일 날짜 최적화
# ──────────────────────────────────────────────────────────────────────────────

def _run_one_day(
    problem,
    pop_size: int,
    n_gen: int,
    seed: int,
    ref_points: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """R-NSGA-II 단일 실행 → (best_F, best_X) 반환."""
    from pymoo.algorithms.moo.rnsga2 import RNSGA2
    from pymoo.operators.crossover.pntx import PointCrossover
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import IntegerRandomSampling
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination

    algo = RNSGA2(
        ref_points=ref_points,
        pop_size=pop_size,
        epsilon=0.001,
        normalization="front",
        sampling=IntegerRandomSampling(),
        crossover=PointCrossover(n_points=2, prob=0.9),
        mutation=PM(prob=max(0.01, 1.0 / problem.n_var), eta=20),
        eliminate_duplicates=True,
    )
    res = minimize(problem, algo, get_termination("n_gen", n_gen),
                   seed=seed, verbose=False)

    if res is None or res.F is None or len(res.F) == 0:
        return None, None

    feasible = np.all(res.G <= 0, axis=1) if res.G is not None else np.ones(len(res.F), dtype=bool)
    F = res.F[feasible]
    X = res.X[feasible]
    if len(F) == 0:
        return None, None

    # 참조점 [0,0,0,0] 기준 L2 거리 최소 해 선택 (4목적 균형)
    ref = np.zeros(F.shape[1])
    dist = np.linalg.norm(F - ref, axis=1)
    best_idx = int(np.argmin(dist))
    return F[best_idx], X[best_idx].astype(int)


# ──────────────────────────────────────────────────────────────────────────────
# 결과 분석 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

def _category_hit_rate(daily_logs: list[dict], preferred_cats: list[str]) -> float:
    """선호 카테고리가 포함된 날의 비율."""
    hits = sum(
        1 for log in daily_logs
        if any(cat in preferred_cats for cat in log["categories"])
    )
    return hits / len(daily_logs) if daily_logs else 0.0


def _repeat_rate(daily_logs: list[dict]) -> float:
    """전체 추천 메뉴 중 중복 등장 비율."""
    all_menus: list[str] = []
    for log in daily_logs:
        all_menus.extend(log["menu_names"])
    if not all_menus:
        return 0.0
    counts = Counter(all_menus)
    repeated = sum(v - 1 for v in counts.values() if v > 1)
    return repeated / len(all_menus)


def _avg_f_error(daily_logs: list[dict], f_idx: int) -> float:
    vals = [log["F"][f_idx] for log in daily_logs if log["F"] is not None]
    return float(np.mean(vals)) if vals else float("nan")


# ──────────────────────────────────────────────────────────────────────────────
# 메인 시뮬레이션
# ──────────────────────────────────────────────────────────────────────────────

def simulate(
    persona_name: str,
    cal_star: float,
    price_star: float,
    n_days: int,
    pop_size: int,
    n_gen: int,
    allergens: list[str] | None = None,
    base_date: datetime | None = None,
    seed_start: int = 42,
) -> list[dict]:
    from experiment.core.loader import FoodDataLoader
    from experiment.core.kg_manager import KGManager, make_menu_id
    from experiment.core.nutrition import NutritionProfile
    from experiment.core.daily_exp3_problem import DailyExp3Problem

    persona = PERSONAS[persona_name]
    print(f"\n{'='*60}")
    print(f"  페르소나: {persona_name} — {persona['description']}")
    print(f"  Cal*={cal_star} kcal | Price*={price_star:,}원/끼니 | {n_days}일 시뮬레이션")
    print(f"{'='*60}")

    # ── 데이터 로딩 ──────────────────────────────────────────────
    loader = FoodDataLoader.from_supabase()
    cats = loader.get_category_lists(allergens_to_avoid=allergens)
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks

    print(f"  MAIN:{len(mains)} SIDE_SOUP:{len(sides_soup)} DRINK:{len(drinks)} SNACK:{len(snacks)}")

    # ── KGManager 초기화 — make_menu_id()로 ID 규칙 통일 ──────────
    kg = KGManager()
    user_id = f"user_{persona_name}"
    for item in all_foods:
        mid = make_menu_id(item)
        cat = item.get("category", "UNKNOWN")
        if mid:
            kg.add_menu(mid, cat)
    for target, weight in persona["preferences"].items():
        kg.set_preference(user_id, target, weight)

    # ── 프로필·참조점 ─────────────────────────────────────────────
    profile = NutritionProfile(
        label="base_50_20_30", r_C=0.5, r_P=0.2, r_F=0.3
    )
    ref_points = np.array([[0.0, 0.0, 0.0, 0.0],
                            [0.1, 0.1, 0.1, 0.0]], dtype=float)

    if base_date is None:
        base_date = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

    daily_logs: list[dict] = []

    for day in range(1, n_days + 1):
        today = base_date + timedelta(days=day - 1)
        seed  = seed_start + day

        print(f"\n  ── Day {day} ({today.strftime('%Y-%m-%d')}) ──────────────────")
        print(f"     max_score = {kg.max_possible_score(user_id):.3f}")

        # ── Problem 인스턴스화 (날마다 KG 상태 + 가상 시각 반영) ─
        problem = DailyExp3Problem(
            mains=mains,
            sides_soup=sides_soup,
            drinks=drinks,
            snacks=snacks,
            n_meals=3,
            include_snack=False,
            cal_star=cal_star,
            price_per_meal_star=price_star,
            profile=profile,
            kg_manager=kg,
            user_id=user_id,
            lambda_decay=0.5,
            sim_now=today,   # 가상 현재 시각: ATE 타임스탬프와 동일 시계 사용
        )

        best_F, best_X = _run_one_day(problem, pop_size, n_gen, seed, ref_points)

        if best_F is None:
            print("     ⚠ 실행 가능한 해 없음, 건너뜀")
            daily_logs.append({
                "day": day, "date": today.strftime("%Y-%m-%d"),
                "F": None, "menu_names": [], "categories": [],
            })
            continue

        # ── 식단 디코딩 ───────────────────────────────────────────
        combo   = problem.decode(best_X)
        meals   = problem.decode_meals(best_X)
        totals  = problem.totals(combo)

        menu_names = [
            str(item.get("product_name") or item.get("menu_name") or "")
            for item in combo
        ]
        categories = [item.get("category", "UNKNOWN") for item in combo]
        cat_counts = Counter(categories)

        f1, f2, f3, f4 = best_F
        print(f"     f1(칼로리오차)={f1:.4f}  f2(매크로)={f2:.4f}  "
              f"f3(가격오차)={f3:.4f}  f4(KG오차율)={f4:.4f}")
        print(f"     칼로리={totals['calories']:.0f}kcal  "
              f"가격={totals['price']:.0f}원  "
              f"카테고리분포={dict(cat_counts)}")
        for m_idx, meal in enumerate(meals, 1):
            meal_str = " + ".join(
                str(it.get("product_name") or it.get("menu_name") or "")
                for it in meal
            )
            print(f"     끼니{m_idx}: {meal_str}")

        # ── 섭취 이력 업데이트 — make_menu_id()로 add_menu와 동일 ID 사용 ──
        for item in combo:
            mid = make_menu_id(item)
            if mid:
                kg.record_eating(user_id, mid, today)

        daily_logs.append({
            "day": day,
            "date": today.strftime("%Y-%m-%d"),
            "F": best_F.tolist(),
            "f1": float(f1), "f2": float(f2), "f3": float(f3), "f4": float(f4),
            "calories": totals["calories"],
            "price": totals["price"],
            "menu_names": menu_names,
            "categories": categories,
            "cat_counts": dict(cat_counts),
        })

    return daily_logs


# ──────────────────────────────────────────────────────────────────────────────
# 분석 요약 출력 + CSV 저장
# ──────────────────────────────────────────────────────────────────────────────

def _print_summary(persona_name: str, daily_logs: list[dict]) -> None:
    persona = PERSONAS[persona_name]
    preferred_cats = [k for k, v in persona["preferences"].items() if v >= 1.2]

    valid = [log for log in daily_logs if log["F"] is not None]
    if not valid:
        print("\n⚠ 유효한 결과 없음")
        return

    hit_rate   = _category_hit_rate(valid, preferred_cats)
    repeat     = _repeat_rate(valid)
    avg_f1     = _avg_f_error(valid, 0)
    avg_f4     = _avg_f_error(valid, 3)

    # 전체 카테고리 분포
    all_cats: list[str] = []
    for log in valid:
        all_cats.extend(log["categories"])
    cat_dist = Counter(all_cats)

    print(f"\n{'='*60}")
    print(f"  📊 시뮬레이션 결과 요약 — {persona_name}")
    print(f"{'='*60}")
    print(f"  선호 카테고리 Hit Rate : {hit_rate:.1%}  (기준: {preferred_cats})")
    print(f"  메뉴 중복률           : {repeat:.1%}  (낮을수록 다양성↑)")
    print(f"  평균 f1(칼로리오차)   : {avg_f1:.4f}  (기준: ≤0.10)")
    print(f"  평균 f4(KG오차율)     : {avg_f4:.4f}  (0에 가까울수록 선호도↑)")
    print(f"  7일 카테고리 분포     : {dict(cat_dist)}")

    # 판정
    passed = []
    failed = []
    (passed if hit_rate >= 0.8 else failed).append(
        f"Hit Rate {hit_rate:.1%} {'≥' if hit_rate >= 0.8 else '<'} 80%"
    )
    (passed if repeat <= 0.3 else failed).append(
        f"중복률 {repeat:.1%} {'≤' if repeat <= 0.3 else '>'} 30%"
    )
    (passed if avg_f1 <= 0.1 else failed).append(
        f"평균 f1 {avg_f1:.4f} {'≤' if avg_f1 <= 0.1 else '>'} 0.10"
    )

    print(f"\n  ✅ 통과: {len(passed)}개")
    for s in passed:
        print(f"     • {s}")
    if failed:
        print(f"  ❌ 미통과: {len(failed)}개")
        for s in failed:
            print(f"     • {s}")


def _save_csv(persona_name: str, daily_logs: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"sim_{persona_name}.csv"
    fieldnames = ["day", "date", "f1", "f2", "f3", "f4",
                  "calories", "price", "menu_names", "categories"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for log in daily_logs:
            row = {k: log.get(k, "") for k in fieldnames}
            row["menu_names"] = " | ".join(log.get("menu_names", []))
            row["categories"] = " | ".join(log.get("categories", []))
            writer.writerow(row)
    print(f"\n  💾 CSV 저장: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KG 기반 4목적 최적화 7일 시뮬레이션",
    )
    parser.add_argument("--days",       type=int,   default=7)
    parser.add_argument("--cal_star",   type=float, required=True)
    parser.add_argument("--price_star", type=float, required=True)
    parser.add_argument("--allergens",  nargs="*",  default=None)
    parser.add_argument("--personas",   nargs="*",
                        default=list(PERSONAS.keys()),
                        help=f"시뮬레이션할 페르소나 목록 (기본: 전체). "
                             f"선택지: {list(PERSONAS.keys())}")
    parser.add_argument("--test",       action="store_true",
                        help="테스트 모드: pop=10, gen=5, days=2")
    parser.add_argument("--out_dir",    default="experiment/results/simulation")
    args = parser.parse_args()

    pop_size = 10 if args.test else 100
    n_gen    = 5  if args.test else 100
    n_days   = 2  if args.test else args.days

    if args.test:
        print("⚡ [TEST MODE] pop=10, gen=5, days=2")

    out_dir = PROJECT_ROOT / args.out_dir

    for persona_name in args.personas:
        if persona_name not in PERSONAS:
            print(f"⚠ 알 수 없는 페르소나: {persona_name}. 건너뜀.")
            continue

        logs = simulate(
            persona_name=persona_name,
            cal_star=args.cal_star,
            price_star=args.price_star,
            n_days=n_days,
            pop_size=pop_size,
            n_gen=n_gen,
            allergens=args.allergens,
        )
        _print_summary(persona_name, logs)
        _save_csv(persona_name, logs, out_dir)


if __name__ == "__main__":
    main()
