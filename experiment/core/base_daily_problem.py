"""BaseDailyDietProblem — 하루 식사 다목적 최적화 기반 클래스.

결정변수 레이아웃 (n_meals=3, include_snack=False 예시):
  x[0..3]  = 아침 [main_idx, side1_idx, side2_idx, drink_idx]
  x[4..7]  = 점심 [main_idx, side1_idx, side2_idx, drink_idx]
  x[8..11] = 저녁 [main_idx, side1_idx, side2_idx, drink_idx]

include_snack=True 시:
  x[12] = snack_idx  (== len(snacks) 이면 간식 skip)

칼로리/가격은 끼니별로 자유 배분 (끼니 간 균등 제약 없음).
서브클래스는 _evaluate()만 구현하면 됨.
"""

from __future__ import annotations

import numpy as np
from pymoo.core.problem import ElementwiseProblem

from .nutrition import NutritionProfile, compute_macro_ratios


class BaseDailyDietProblem(ElementwiseProblem):
    """하루 n_meals끼 식사 공통 기반."""

    def __init__(
        self,
        mains: list[dict],
        sides_soup: list[dict],
        drinks: list[dict],
        snacks: list[dict],
        n_meals: int,
        include_snack: bool,
        cal_star: float,
        price_per_meal_star: float,
        profile: NutritionProfile,
        n_obj: int,
        n_constr: int = 1,
        **kwargs,
    ):
        self.mains = mains
        self.sides_soup = sides_soup
        self.drinks = drinks
        self.snacks = snacks
        self.n_meals = n_meals
        self.include_snack = include_snack
        self.cal_star = max(cal_star, 1.0)
        self.price_per_meal_star = max(price_per_meal_star, 1.0)
        self.profile = profile

        # 결정변수 범위 구성
        # 끼니마다: [main, side1, side2, drink] 4개
        # side/drink: == len 이면 "선택 안함" (skip)
        xl_list: list[int] = []
        xu_list: list[int] = []
        for _ in range(n_meals):
            xl_list += [0, 0, 0, 0]
            xu_list += [
                max(0, len(mains) - 1),
                len(sides_soup),   # == len → skip
                len(sides_soup),   # == len → skip
                len(drinks),       # == len → skip
            ]
        if include_snack:
            xl_list += [0]
            xu_list += [len(snacks)]  # == len → skip

        super().__init__(
            n_var=len(xl_list),
            n_obj=n_obj,
            n_constr=n_constr,
            xl=np.array(xl_list, dtype=int),
            xu=np.array(xu_list, dtype=int),
            type_var=int,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def decode_meals(self, x: np.ndarray) -> list[list[dict]]:
        """끼니별 식품 목록 반환. 간식은 마지막 원소(단일 아이템 리스트)."""
        x = x.astype(int)
        meals: list[list[dict]] = []
        for i in range(self.n_meals):
            base = i * 4
            meal: list[dict] = [
                self.mains[int(np.clip(x[base], 0, len(self.mains) - 1))]
            ]
            if x[base + 1] < len(self.sides_soup):
                meal.append(self.sides_soup[x[base + 1]])
            if x[base + 2] < len(self.sides_soup):
                meal.append(self.sides_soup[x[base + 2]])
            if x[base + 3] < len(self.drinks):
                meal.append(self.drinks[x[base + 3]])
            meals.append(meal)

        if self.include_snack:
            snack_i = x[4 * self.n_meals]
            if snack_i < len(self.snacks):
                meals.append([self.snacks[snack_i]])

        return meals

    def decode(self, x: np.ndarray) -> list[dict]:
        """정수 결정변수 → 하루 전체 식품 목록 (끼니 구분 없이 flatten)."""
        return [item for meal in self.decode_meals(x) for item in meal]

    def totals(self, combo: list[dict]) -> dict:
        """콤보의 영양소·가격 합산."""
        keys = ["calories", "protein", "carbs", "fat", "sugar", "sodium", "price"]
        return {k: float(sum(item.get(k, 0) or 0 for item in combo)) for k in keys}

    def macro_ratios(self, t: dict) -> tuple[float, float, float]:
        """실제 매크로 비율 (r_C, r_P, r_F). 구현은 nutrition.compute_macro_ratios 참조."""
        return compute_macro_ratios(t)

    def _allergen_g(self, combo: list[dict]) -> float:
        """알레르겐 제약 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)."""
        return -1.0
