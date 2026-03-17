"""DailyExp2Problem — 하루 식사 3목적 최적화.

목적함수:
  f1 = |총칼로리(x) - Cal*| / Cal*
  f2 = sqrt((r_C(x)-r_C*)^2 + (r_P(x)-r_P*)^2 + (r_F(x)-r_F*)^2)
  f3 = |끼니당평균가격(x) - Price_per_meal*| / Price_per_meal*

  총칼로리 = 하루 전체 끼니(+ 간식) 칼로리 합산
  끼니당평균가격 = 하루 전체 가격 / n_meals

제약조건:
  g1 ≤ 0: allergen 안전 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)

[DailyExp1과의 차이]
  DailyExp1: 칼로리+매크로 오차를 f1에 합산 (2목적)
  DailyExp2: 칼로리(f1), 매크로 비율(f2), 가격(f3)으로 분리 (3목적)
"""

from __future__ import annotations

import numpy as np

from .base_daily_problem import BaseDailyDietProblem
from .nutrition import NutritionProfile


class DailyExp2Problem(BaseDailyDietProblem):
    """하루 3목적: 칼로리 오차 vs 매크로 비율 유클리드 거리 vs 끼니당 가격 오차."""

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
    ):
        super().__init__(
            mains=mains,
            sides_soup=sides_soup,
            drinks=drinks,
            snacks=snacks,
            n_meals=n_meals,
            include_snack=include_snack,
            cal_star=cal_star,
            price_per_meal_star=price_per_meal_star,
            profile=profile,
            n_obj=3,
            n_constr=1,
        )

    def _evaluate(self, x, out, *args, **kwargs):
        combo = self.decode(x)
        t = self.totals(combo)
        r_C, r_P, r_F = self.macro_ratios(t)
        p = self.profile

        # f1: 하루 총칼로리 오차
        f1 = abs(t["calories"] - self.cal_star) / self.cal_star

        # f2: 매크로 비율 유클리드 거리
        f2 = float(np.sqrt(
            (r_C - p.r_C) ** 2
            + (r_P - p.r_P) ** 2
            + (r_F - p.r_F) ** 2
        ))

        # f3: 끼니당 평균 가격 오차
        avg_price = t["price"] / self.n_meals
        f3 = abs(avg_price - self.price_per_meal_star) / self.price_per_meal_star

        out["F"] = [f1, f2, f3]
        out["G"] = [self._allergen_g(combo)]
