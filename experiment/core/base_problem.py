"""BaseDietProblem — 결정변수 레이아웃·decode·totals·allergen 제약 공통 기반.

결정변수 4개 (정수):
  x[0] = main_idx    → MAIN 목록 인덱스
  x[1] = side1_idx   → SIDE_SOUP 목록 인덱스 (== len이면 skip)
  x[2] = side2_idx   → SIDE_SOUP 목록 인덱스 (== len이면 skip)
  x[3] = drink_idx   → DRINK 목록 인덱스 (== len이면 skip)

제약조건: 알레르겐 위반 여부 (g <= 0 = 실행 가능)
  g1 > 0: 콤보 내 알레르겐 위반 항목 존재
  g1 ≤ 0: 안전

서브클래스는 _evaluate()만 구현하면 됨.
"""

from __future__ import annotations

import numpy as np
from pymoo.core.problem import ElementwiseProblem

from .nutrition import NutritionProfile, compute_macro_ratios


class BaseDietProblem(ElementwiseProblem):
    """공통 결정변수 구조 및 헬퍼 메서드."""

    def __init__(
        self,
        mains: list[dict],
        sides_soup: list[dict],
        drinks: list[dict],
        cal_star: float,
        price_star: float,
        profile: NutritionProfile,
        n_obj: int,
        n_constr: int = 1,
        **kwargs,
    ):
        self.mains = mains
        self.sides_soup = sides_soup
        self.drinks = drinks
        self.cal_star = max(cal_star, 1.0)
        self.price_star = max(price_star, 1.0)
        self.profile = profile

        # 상한: len(list)이면 "선택 안함"으로 skip
        xl = np.array([0, 0, 0, 0], dtype=int)
        xu = np.array([
            max(0, len(mains) - 1),
            len(sides_soup),      # == len → side1 skip
            len(sides_soup),      # == len → side2 skip
            len(drinks),          # == len → drink skip
        ], dtype=int)

        super().__init__(
            n_var=4, n_obj=n_obj, n_constr=n_constr,
            xl=xl, xu=xu, type_var=int,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def decode(self, x: np.ndarray) -> list[dict]:
        """정수 결정변수 벡터 → 식품 콤보 목록."""
        x = x.astype(int)
        combo: list[dict] = [self.mains[int(np.clip(x[0], 0, len(self.mains) - 1))]]
        if x[1] < len(self.sides_soup):
            combo.append(self.sides_soup[x[1]])
        if x[2] < len(self.sides_soup):
            combo.append(self.sides_soup[x[2]])
        if x[3] < len(self.drinks):
            combo.append(self.drinks[x[3]])
        return combo

    def totals(self, combo: list[dict]) -> dict:
        """콤보의 영양소·가격 합산."""
        # NOTE: DB 컬럼명은 단수형 'sugar' (loader.py 기준). 'sugars'로 두면 silent 0 합계.
        keys = ["calories", "protein", "carbs", "fat", "sugar", "sodium", "price"]
        return {k: float(sum(item.get(k, 0) or 0 for item in combo)) for k in keys}

    def macro_ratios(self, t: dict) -> tuple[float, float, float]:
        """실제 매크로 비율 (r_C, r_P, r_F). 구현은 nutrition.compute_macro_ratios 참조."""
        return compute_macro_ratios(t)

    def _allergen_g(self, combo: list[dict]) -> float:
        """알레르겐 제약 값. > 0이면 위반(infeasible), ≤ 0이면 안전."""
        # 이 클래스는 allergen 필터링이 사전에 된 리스트를 받으므로
        # 항상 안전 (-1.0 반환). 서브클래스에서 필요 시 오버라이드 가능.
        return -1.0
