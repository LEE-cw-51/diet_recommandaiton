"""FoodDataLoader — 실험용 데이터 로더.

프로덕션 DailyDietOptimizer와 달리 price > 500 필터를 적용하지 않음.
price=0인 항목은 목적함수에서 자연 도태됨.

food_master.allergens 컬럼은 JSONB {"알레르겐명": bool, ...} 형식.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# 프로젝트 루트를 sys.path에 추가 (db.client import 용)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ALLERGEN_22 = [
    "난류", "우유", "메밀", "땅콩", "대두", "밀", "고등어", "게", "새우",
    "돼지고기", "복숭아", "토마토", "아황산류", "호두", "닭고기", "쇠고기",
    "오징어", "조개류", "잣", "굴", "전복", "홍합",
]

_SELECT_COLS = (
    "id,product_name,brand_name,category_type,"
    "calories,protein,carbs,fat,sugar,sodium,price,allergens"
)
_NUMERIC_COLS = ["calories", "protein", "carbs", "fat", "sugar", "sodium", "price"]

# category_type 값 → 실험용 버킷 매핑 (SOUP은 SIDE_SOUP으로 병합)
_CATEGORY_BUCKET: dict[str, str] = {
    "MAIN":  "MAIN",
    "SIDE":  "SIDE_SOUP",
    "SOUP":  "SIDE_SOUP",
    "DRINK": "DRINK",
    "SNACK": "SNACK",
}


class FoodDataLoader:
    """Supabase 또는 CSV에서 food_master를 로딩해 실험에 사용할 카테고리 목록을 제공."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.menu_items: list[dict] = df.to_dict("records")

    # ------------------------------------------------------------------
    # 생성자
    # ------------------------------------------------------------------

    @classmethod
    def from_supabase(cls, cal_min: float = 10.0) -> "FoodDataLoader":
        """Supabase food_master 테이블에서 전체 데이터를 pagination으로 로딩.

        PostgREST 기본 limit=1,000 → range(offset, offset+999) 루프 사용.
        price IS NULL → fillna(0) (price > 500 필터 미적용).
        """
        from db.client import get_client

        print("📦 [FoodDataLoader] Supabase에서 food_master 로딩 중...")
        sb = get_client()
        rows: list[dict] = []
        offset = 0
        while True:
            resp = (
                sb.table("food_master")
                .select(_SELECT_COLS)
                .range(offset, offset + 999)
                .execute()
            )
            batch = resp.data
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

        print(f"  총 {len(rows)}행 로딩 완료")
        df = cls._prepare_df(pd.DataFrame(rows), cal_min)
        return cls(df)

    @classmethod
    def from_csv(cls, path: str, cal_min: float = 10.0) -> "FoodDataLoader":
        """CSV에서 로딩 (오프라인 테스트용)."""
        df = pd.DataFrame(pd.read_csv(path))
        df = cls._prepare_df(df, cal_min)
        return cls(df)

    # ------------------------------------------------------------------
    # 내부 준비
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare_df(df: pd.DataFrame, cal_min: float) -> pd.DataFrame:
        for col in _NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # price: NULL → 0 (가격 미확인 품목)
        df["price"] = df["price"].fillna(0)
        # 영양소 NULL → 0 (NaN 전파로 f1=NaN 되는 것 방지)
        for col in ["calories", "protein", "carbs", "fat", "sugar", "sodium"]:
            if col in df.columns:
                df[col] = df[col].fillna(0)
        df = df[df["calories"] > cal_min].copy()

        # allergens 정규화: JSONB dict 또는 None → {}
        if "allergens" in df.columns:
            df["allergens"] = df["allergens"].apply(
                lambda v: v if isinstance(v, dict) else {}
            )
        else:
            df["allergens"] = [{}] * len(df)

        # category_type 정규화
        if "category_type" in df.columns:
            df["category_type"] = df["category_type"].fillna("SIDE").str.upper()
        else:
            df["category_type"] = "SIDE"

        return df

    # ------------------------------------------------------------------
    # 카테고리 목록 반환
    # ------------------------------------------------------------------

    def get_category_lists(
        self, allergens_to_avoid: list[str] | None = None
    ) -> dict[str, list[dict]]:
        """알레르겐 필터링 후 카테고리별 식품 목록 반환.

        Returns:
            {
                "MAIN":      [...],   # MAIN 카테고리
                "SIDE_SOUP": [...],   # SIDE + SOUP 병합
                "DRINK":     [...],   # DRINK
                "SNACK":     [...],   # SNACK (현재 실험에서 미사용)
            }
        """
        buckets: dict[str, list[dict]] = {
            "MAIN": [], "SIDE_SOUP": [], "DRINK": [], "SNACK": []
        }

        avoid_set: set[str] = set(allergens_to_avoid or [])

        for item in self.menu_items:
            # 알레르겐 필터
            if avoid_set:
                allergens: dict = item.get("allergens", {})
                if any(allergens.get(a, False) for a in avoid_set):
                    continue

            cat = item.get("category_type", "SIDE")
            bucket = _CATEGORY_BUCKET.get(cat, "SIDE_SOUP")
            # 실험용 카테고리 이름을 아이템에도 기록 (KG 구성 시 사용)
            item["category"] = bucket
            buckets[bucket].append(item)

        return buckets

    # ------------------------------------------------------------------
    # 통계 출력
    # ------------------------------------------------------------------

    def summary(self) -> None:
        print(f"[FoodDataLoader] 총 {len(self.menu_items)}개 메뉴")
        for cat, count in self.df["category_type"].value_counts().items():
            print(f"  {cat}: {count}")
