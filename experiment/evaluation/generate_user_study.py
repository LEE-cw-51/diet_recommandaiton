"""A/B 유저 스터디용 식단 사전 생성.

식문화별 N세트의 (G2 7일, G3 7일) 쌍을 생성한다.
  - G2: R-NSGA-II, use_f4=False (개인화 미적용)
  - G3: R-NSGA-II + KG, use_f4=True (개인화 적용)
  - 동일 KG 초기 상태에서 deepcopy로 독립 분리 → 알고리즘 차이만 변수
  - A/B 라벨은 랜덤 배정, meta.json에만 정답 저장 (블라인드)

사용법:
  python -X utf8 -m experiment.evaluation.generate_user_study --test
  python -X utf8 -m experiment.evaluation.generate_user_study --cuisines 한식 양식 --n_sets 5
  python -X utf8 -m experiment.evaluation.generate_user_study
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiment.models.variants import (
    N_MEALS,
    SEED_START,
    REF_G2 as _REF_G2,
    REF_G3 as _REF_G3,
    TEST_USER,
)
from experiment.simulation.simulate_kg import _run_one_day
from experiment.simulation.run_step2_cuisine import _build_kg_cuisine

# ── 상수 ────────────────────────────────────────────────────────────────────────
CUISINES       = ["한식", "중식", "일식", "양식"]
CUISINE_WEIGHT = 1.3
BASE_DATE      = datetime(2026, 5, 7, 12, 0, 0)
N_DAYS         = 7

MEAL_LABELS = ["아침", "점심", "저녁"]

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "user_study"


# ── 1일 최적화 ──────────────────────────────────────────────────────────────────

def _run_one_day_g2(problem, pop_size: int, n_gen: int, seed: int):
    """G2 전용: 3목적 R-NSGA-II."""
    return _run_one_day(problem, pop_size, n_gen, seed, _REF_G2)


def _run_one_day_g3(problem, pop_size: int, n_gen: int, seed: int):
    """G3 전용: 4목적 R-NSGA-II."""
    return _run_one_day(problem, pop_size, n_gen, seed, _REF_G3)


# ── 식단 디코딩 → CSV 행 변환 ────────────────────────────────────────────────────

def _format_meal(items: list[dict]) -> str:
    """끼니 아이템 리스트 → '메뉴1 / 메뉴2' 문자열."""
    names = [str(item.get("product_name") or item.get("menu_name") or "").strip()
             for item in items]
    return " / ".join(n for n in names if n)


def _build_day_row(
    day: int,
    date: datetime,
    meals: list[list[dict]],
    problem,
    combo: list[dict],
) -> dict:
    """하루 식단 → CSV 한 행 dict."""
    totals = problem.totals(combo)
    row = {
        "day":             day,
        "date":            date.strftime("%Y-%m-%d"),
        "breakfast":       _format_meal(meals[0]) if len(meals) > 0 else "",
        "lunch":           _format_meal(meals[1]) if len(meals) > 1 else "",
        "dinner":          _format_meal(meals[2]) if len(meals) > 2 else "",
        "total_calories":  round(totals.get("calories", 0)),
        "total_price":     round(totals.get("price", 0)),
    }
    return row


# ── 7일 시뮬레이션 ────────────────────────────────────────────────────────────────

def _run_7days(
    mains, sides_soup, drinks, snacks,
    kg,
    cal_star: float,
    price_star: float,
    pop_size: int,
    n_gen: int,
    set_idx: int,
    use_f4: bool,
) -> list[dict]:
    """G2(use_f4=False) 또는 G3(use_f4=True) 7일 시뮬레이션.

    Returns:
        list of day-row dicts (7행). 해가 없는 날은 빈 메뉴로 채움.
    """
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.core.nutrition import NutritionProfile

    profile    = NutritionProfile.who2025()
    daily_rows = []
    prev_combo = None

    for day in range(1, N_DAYS + 1):
        today = BASE_DATE + timedelta(days=day - 1)
        # 세트와 알고리즘이 달라도 같은 seed → 공정 비교 보장
        seed  = SEED_START + set_idx * 100 + day

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
            use_f4=use_f4,
        )

        run_fn  = _run_one_day_g3 if use_f4 else _run_one_day_g2
        best_F, best_X = run_fn(problem, pop_size, n_gen, seed)

        if best_F is None:
            daily_rows.append({
                "day": day, "date": today.strftime("%Y-%m-%d"),
                "breakfast": "", "lunch": "", "dinner": "",
                "total_calories": 0, "total_price": 0,
            })
            prev_combo = None
            continue

        meals  = problem.decode_meals(best_X)
        combo  = problem.decode(best_X)
        row    = _build_day_row(day, today, meals, problem, combo)
        daily_rows.append(row)
        prev_combo = combo

    return daily_rows


# ── CSV / JSON 저장 ──────────────────────────────────────────────────────────────

_CSV_FIELDS = ["day", "date", "breakfast", "lunch", "dinner",
               "total_calories", "total_price"]


def _save_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _save_meta(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ── 세트 생성 ────────────────────────────────────────────────────────────────────

def generate_sets(
    mains, sides_soup, drinks, snacks, all_foods,
    cuisine: str,
    n_sets: int,
    out_dir: Path,
    cal_star: float,
    price_star: float,
    pop_size: int,
    n_gen: int,
) -> None:
    """식문화 1개에 대해 n_sets 쌍 생성."""
    cuisine_dir = out_dir / cuisine
    cuisine_dir.mkdir(parents=True, exist_ok=True)

    for s in range(1, n_sets + 1):
        set_id = f"set_{s:02d}"
        print(f"  [{cuisine}] {set_id} 생성 중...")

        # 동일 KG 상태에서 deepcopy로 G2/G3 독립 분리
        kg_base = _build_kg_cuisine(all_foods, cuisine, CUISINE_WEIGHT)
        kg_g2   = copy.deepcopy(kg_base)
        kg_g3   = copy.deepcopy(kg_base)

        g2_rows = _run_7days(mains, sides_soup, drinks, snacks,
                             kg_g2, cal_star, price_star,
                             pop_size, n_gen, set_idx=s, use_f4=False)
        g3_rows = _run_7days(mains, sides_soup, drinks, snacks,
                             kg_g3, cal_star, price_star,
                             pop_size, n_gen, set_idx=s, use_f4=True)

        # A/B 라벨 랜덤 배정
        a_is_g2 = random.random() < 0.5
        a_rows  = g2_rows if a_is_g2 else g3_rows
        b_rows  = g3_rows if a_is_g2 else g2_rows

        _save_csv(cuisine_dir / f"{set_id}_A.csv", a_rows)
        _save_csv(cuisine_dir / f"{set_id}_B.csv", b_rows)
        _save_meta(cuisine_dir / f"{set_id}_meta.json", {
            "cuisine":       cuisine,
            "set_id":        set_id,
            "A_is":          "G2" if a_is_g2 else "G3",
            "B_is":          "G3" if a_is_g2 else "G2",
            "seed_base":     SEED_START + s * 100,
            "kg_menu_count": kg_base.G.number_of_edges(),
        })

        print(f"    -> {set_id}_A.csv ({('G2' if a_is_g2 else 'G3')}), "
              f"{set_id}_B.csv ({('G3' if a_is_g2 else 'G2')})")


# ── main ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="A/B 유저 스터디 식단 사전 생성")
    parser.add_argument("--cuisines",   nargs="*", default=CUISINES,
                        help=f"대상 식문화 (default: {CUISINES})")
    parser.add_argument("--n_sets",     type=int,   default=5,
                        help="식문화당 생성할 세트 수 (default: 5)")
    parser.add_argument("--out_dir",    type=str,   default=str(_OUT_DIR))
    parser.add_argument("--cal_star",   type=float, default=2000.0)
    parser.add_argument("--price_star", type=float, default=8000.0)
    parser.add_argument("--pop_size",   type=int,   default=200)
    parser.add_argument("--n_gen",      type=int,   default=200)
    parser.add_argument("--seed",       type=int,   default=42,
                        help="A/B 라벨 배정용 random seed")
    parser.add_argument("--test",       action="store_true",
                        help="빠른 테스트 (pop=10, gen=20, n_sets=1, n_days=2)")
    args = parser.parse_args()

    if args.test:
        args.pop_size, args.n_gen = 10, 20
        args.n_sets = 1
        global N_DAYS
        N_DAYS = 2
        print("[TEST MODE] pop=10, gen=20, n_sets=1, n_days=2")

    random.seed(args.seed)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print("  Supabase 데이터 로딩")
    print("=" * 65)
    from experiment.core.loader import FoodDataLoader

    loader     = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks
    print(f"  MAIN:{len(mains)}  SIDE_SOUP:{len(sides_soup)}  "
          f"DRINK:{len(drinks)}  SNACK:{len(snacks)}")

    total_sets = 0
    for cuisine in args.cuisines:
        print(f"\n{'='*65}")
        print(f"  [{cuisine}] {args.n_sets}세트 생성")
        print("=" * 65)
        generate_sets(
            mains, sides_soup, drinks, snacks, all_foods,
            cuisine=cuisine,
            n_sets=args.n_sets,
            out_dir=out_dir,
            cal_star=args.cal_star,
            price_star=args.price_star,
            pop_size=args.pop_size,
            n_gen=args.n_gen,
        )
        total_sets += args.n_sets

    print(f"\n{'='*65}")
    print(f"  완료: {len(args.cuisines)}개 식문화 x {args.n_sets}세트 = {total_sets}세트")
    print(f"  저장 경로: {out_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
