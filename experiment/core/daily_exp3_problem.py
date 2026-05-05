"""DailyExp3Problem — 하루 식사 4목적 최적화 (KG 기반 개인화 추가).

목적함수:
  f1 = |총칼로리(x) - Cal*| / Cal*
  f2 = sqrt((r_C-r_C*)^2 + (r_P-r_P*)^2 + (r_F-r_F*)^2)
  f3 = |끼니당평균가격(x) - Price_per_meal*| / Price_per_meal*
  f4 = (max_score - avg_score) / max_score   ← KG 오차율, 0에 수렴할수록 좋음

  max_score : 사용자의 최대 PREFERS 가중치 (감쇠 없음 기준)
  avg_score : 하루 식단 아이템별 KG 추천 점수의 평균

제약조건:
  g1 ≤ 0: allergen 안전 (데이터 로딩 시 사전 필터링 완료 → 항상 -1.0)

[DailyExp2와의 차이]
  DailyExp2: 3목적 (f1, f2, f3)
  DailyExp3: 4목적 — f4(KG 기반 개인화 오차율) 추가, R-NSGA-II로 탐색
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from .base_daily_problem import BaseDailyDietProblem
from .kg_manager import KGManager, make_menu_id
from .nutrition import NutritionProfile


class DailyExp3Problem(BaseDailyDietProblem):
    """하루 4목적: 칼로리 오차 / 매크로 비율 / 가격 오차 / KG 개인화 오차율."""

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
        kg_manager: KGManager | None = None,
        user_id: str = "user_0",
        lambda_decay: float = 0.5,
        sim_now: datetime | None = None,
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
            n_obj=4,
            n_constr=1,
        )
        self.kg_manager = kg_manager if kg_manager is not None else KGManager()
        self.user_id = user_id
        self.lambda_decay = lambda_decay
        # 시뮬레이션용 기준 현재 시각.
        # sim_now가 주어지지 않으면 생성 시점의 현재 시각을 한 번만 캡처해
        # 모든 평가에서 동일하게 사용하여 목적함수 재현성을 보장한다.
        self.sim_now = sim_now if sim_now is not None else datetime.now()

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

        # f4: KG 오차율 = (max_score - avg_score) / max_score  ∈ [0, 1]
        max_s = self.kg_manager.max_possible_score(self.user_id)
        max_s = max(1e-9, max_s)  # ZeroDivisionError 방어
        scores = [
            self.kg_manager.get_score(
                self.user_id,
                make_menu_id(item),  # kg_manager.make_menu_id()와 동일 규칙으로 ID 생성
                self.lambda_decay,
                now=self.sim_now,   # 시뮬레이션 시 가상 시각, None이면 datetime.now()
            )
            for item in combo
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        f4 = float(np.clip((max_s - avg_score) / max_s, 0.0, 1.0))

        out["F"] = [f1, f2, f3, f4]
        out["G"] = [self._allergen_g(combo)]
