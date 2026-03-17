"""DailyExp1Problem — 하루 식사 2목적 최적화.

목적함수:
  f1 = |총칼로리(x) - Cal*| / Cal*
       + w_C*|r_C(x)-r_C*| + w_P*|r_P(x)-r_P*| + w_F*|r_F(x)-r_F*|
  f2 = |끼니당평균가격(x) - Price_per_meal*| / Price_per_meal*

  총칼로리 = 하루 전체 끼니(+ 간식) 칼로리 합산
  끼니당평균가격 = 하루 전체 가격 / n_meals

제약조건:
  g1 ≤ 0: allergen 안전 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)
"""

from __future__ import annotations

from .base_daily_problem import BaseDailyDietProblem
from .nutrition import NutritionProfile


class DailyExp1Problem(BaseDailyDietProblem):
    """하루 2목적: (영양+칼로리 복합 오차) vs (끼니당 평균 가격 오차)."""

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
            n_obj=2,
            n_constr=1,
        )

    def _evaluate(self, x, out, *args, **kwargs):
        combo = self.decode(x)
        t = self.totals(combo)
        r_C, r_P, r_F = self.macro_ratios(t)
        p = self.profile

        # f1: 칼로리 오차 + 가중치 적용 매크로 비율 오차 합산
        cal_err = abs(t["calories"] - self.cal_star) / self.cal_star
        macro_err = (
            p.w_C * abs(r_C - p.r_C)
            + p.w_P * abs(r_P - p.r_P)
            + p.w_F * abs(r_F - p.r_F)
        )
        f1 = cal_err + macro_err

        # f2: 끼니당 평균 가격 오차
        avg_price = t["price"] / self.n_meals
        f2 = abs(avg_price - self.price_per_meal_star) / self.price_per_meal_star

        out["F"] = [f1, f2]
        out["G"] = [self._allergen_g(combo)]
