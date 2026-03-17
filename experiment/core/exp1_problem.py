"""Exp1Problem — 실험 1: 2목적 최적화.

목적함수:
  f1 = |Cal(x)-Cal*|/Cal*
       + w_C*|r_C(x)-r_C*| + w_P*|r_P(x)-r_P*| + w_F*|r_F(x)-r_F*|
  f2 = |Price(x)-Price*| / Price*

  r_m(x) = macro_m_kcal / (carbs*4 + prot*4 + fat*9)  ← 실제 매크로 비율
  r_C*, r_P*, r_F*, w_C, w_P, w_F ← NutritionProfile에서 주입

제약조건:
  g1 ≤ 0: allergen 안전 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)
"""

from __future__ import annotations

import numpy as np

from .base_problem import BaseDietProblem
from .nutrition import NutritionProfile


class Exp1Problem(BaseDietProblem):
    """2목적: (영양+칼로리 복합 오차) vs (가격 오차)."""

    def __init__(
        self,
        mains: list[dict],
        sides_soup: list[dict],
        drinks: list[dict],
        cal_star: float,
        price_star: float,
        profile: NutritionProfile,
    ):
        super().__init__(
            mains=mains,
            sides_soup=sides_soup,
            drinks=drinks,
            cal_star=cal_star,
            price_star=price_star,
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

        # f2: 가격 오차
        f2 = abs(t["price"] - self.price_star) / self.price_star

        out["F"] = [f1, f2]
        out["G"] = [self._allergen_g(combo)]
