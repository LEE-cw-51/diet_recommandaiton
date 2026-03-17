"""Exp2Problem — 실험 2: 3목적 최적화.

목적함수:
  f1 = |Cal(x)-Cal*| / Cal*
  f2 = sqrt((r_C(x)-r_C*)^2 + (r_P(x)-r_P*)^2 + (r_F(x)-r_F*)^2)
  f3 = |Price(x)-Price*| / Price*

  r_m(x) = macro_m_kcal / (carbs*4 + prot*4 + fat*9)  ← 실제 매크로 비율
  r_C*, r_P*, r_F* ← NutritionProfile에서 주입 (Exp1과 동일한 객체 사용 가능)

제약조건:
  g1 ≤ 0: allergen 안전 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)

[Exp1과의 차이]
  Exp1: 칼로리 오차 + 매크로 오차를 f1에 합산 (2목적)
  Exp2: 칼로리 오차(f1), 매크로 비율 유클리드 거리(f2), 가격 오차(f3)로 분리 (3목적)
  두 실험 모두 동일한 NutritionProfile의 r_C*, r_P*, r_F*를 참조.
"""

from __future__ import annotations

import numpy as np

from .base_problem import BaseDietProblem
from .nutrition import NutritionProfile


class Exp2Problem(BaseDietProblem):
    """3목적: 칼로리 오차 vs 매크로 비율 유클리드 거리 vs 가격 오차."""

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
            n_obj=3,
            n_constr=1,
        )

    def _evaluate(self, x, out, *args, **kwargs):
        combo = self.decode(x)
        t = self.totals(combo)
        r_C, r_P, r_F = self.macro_ratios(t)
        p = self.profile

        # f1: 칼로리 오차
        f1 = abs(t["calories"] - self.cal_star) / self.cal_star

        # f2: 매크로 비율 유클리드 거리
        f2 = float(np.sqrt(
            (r_C - p.r_C) ** 2
            + (r_P - p.r_P) ** 2
            + (r_F - p.r_F) ** 2
        ))

        # f3: 가격 오차
        f3 = abs(t["price"] - self.price_star) / self.price_star

        out["F"] = [f1, f2, f3]
        out["G"] = [self._allergen_g(combo)]
