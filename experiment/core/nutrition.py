"""NutritionProfile — 영양소 목표 비율 설정.

실험 간 영양소 비율을 독립적으로 교체할 수 있도록 분리.
민감도 분석 시 YAML의 nutrition_profile 블록만 변경하면 됨.

기본값 (r_C + r_P + r_F = 1.0):
  탄수화물: 50.0%  (범위 50–65%)
  단백질:   20.0%  (범위 10–20%)
  지방:     30.0%  (범위 15–30%)

민감도 시나리오도 모두 합산 100% 유지.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NutritionProfile:
    """영양소 목표 비율 및 가중치.

    Attributes:
        label:  식별용 레이블 (결과 폴더명에 포함됨)
        r_C:    탄수화물 목표 비율 (0~1)
        r_P:    단백질 목표 비율
        r_F:    지방 목표 비율
        w_C:    Exp1의 f1 내 탄수화물 오차 가중치
        w_P:    Exp1의 f1 내 단백질 오차 가중치
        w_F:    Exp1의 f1 내 지방 오차 가중치
    """
    label: str
    r_C: float
    r_P: float
    r_F: float
    w_C: float = field(default=1 / 3)
    w_P: float = field(default=1 / 3)
    w_F: float = field(default=1 / 3)

    def __post_init__(self):
        self.validate()

    def validate(self):
        total = self.r_C + self.r_P + self.r_F
        assert abs(total - 1.0) < 0.01, (
            f"NutritionProfile '{self.label}': r_C+r_P+r_F = {total:.4f} (1.0 이어야 함)"
        )

    @classmethod
    def from_dict(cls, d: dict) -> "NutritionProfile":
        return cls(
            label=d["label"],
            r_C=float(d["r_C"]),
            r_P=float(d["r_P"]),
            r_F=float(d["r_F"]),
            w_C=float(d.get("w_C", 1 / 3)),
            w_P=float(d.get("w_P", 1 / 3)),
            w_F=float(d.get("w_F", 1 / 3)),
        )

    @classmethod
    def who2025(cls) -> "NutritionProfile":
        """기본 프로파일: 탄 50% / 단 20% / 지 30% (합산 100%)."""
        return cls(label="base_50_20_30", r_C=0.50, r_P=0.20, r_F=0.30)


def compute_macro_ratios(t: dict) -> tuple[float, float, float]:
    """totals 딕셔너리로부터 실제 매크로 비율 (r_C, r_P, r_F) 계산.

    매크로 칼로리 = carbs*4 + protein*4 + fat*9
    각 비율 = 해당 매크로 kcal / 매크로 총 kcal

    매크로 kcal이 0 이하이면 (0.0, 0.0, 0.0) 반환.
    """
    macro_kcal = t["carbs"] * 4 + t["protein"] * 4 + t["fat"] * 9
    if macro_kcal <= 0:
        return 0.0, 0.0, 0.0
    return (
        (t["carbs"] * 4) / macro_kcal,
        (t["protein"] * 4) / macro_kcal,
        (t["fat"] * 9) / macro_kcal,
    )


# 사전 정의된 민감도 분석 시나리오 (모두 r_C + r_P + r_F = 1.0)
#
#  시나리오          탄    단    지    합계   설명
#  base_50_20_30   50%   20%   30%  100%  기본값 (탄 하한·단 상한·지 상한)
#  high_carb       65%   10%   25%  100%  탄수화물 상한 시나리오
#  mid_balanced    57%   15%   28%  100%  범위 내 중간값 근사
#  low_fat         65%   20%   15%  100%  지방 하한 시나리오
#  low_protein     60%   10%   30%  100%  단백질 하한 시나리오
SENSITIVITY_PROFILES: dict[str, NutritionProfile] = {
    "base_50_20_30": NutritionProfile(label="base_50_20_30", r_C=0.500, r_P=0.200, r_F=0.300),
    "high_carb":     NutritionProfile(label="high_carb",     r_C=0.650, r_P=0.100, r_F=0.250),
    "mid_balanced":  NutritionProfile(label="mid_balanced",  r_C=0.570, r_P=0.150, r_F=0.280),
    "low_fat":       NutritionProfile(label="low_fat",       r_C=0.650, r_P=0.200, r_F=0.150),
    "low_protein":   NutritionProfile(label="low_protein",   r_C=0.600, r_P=0.100, r_F=0.300),
}
