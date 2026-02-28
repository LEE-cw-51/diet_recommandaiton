"""
공공 API 조회 결과를 최종 DB(final_nutrition_db.csv)에 반영
결측 영양성분이 있는 항목을 자동으로 채워줌
"""

import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings
from api.nutrition_api_client import NutritionAPIClient
from api.api_cache import cached_search

NUTRITION_COLS = ["calories", "protein", "fat", "carbs", "sodium", "sugars", "saturated_fat"]
DB_PATH = os.path.join(settings.DATA_PROCESSED, "final_nutrition_db.csv")


def fill_missing_nutrition(db_path: str = DB_PATH) -> pd.DataFrame:
    """
    DB에서 영양성분 결측치가 있는 항목을 API로 보완

    Args:
        db_path: final_nutrition_db.csv 경로

    Returns:
        보완된 DataFrame
    """
    df = pd.read_csv(db_path, encoding="utf-8-sig")
    client = NutritionAPIClient()

    missing_mask = df[NUTRITION_COLS].isnull().any(axis=1)
    missing_rows = df[missing_mask]

    print(f"결측 영양성분 항목: {len(missing_rows)}개")

    filled_count = 0
    for idx, row in missing_rows.iterrows():
        food_name = row.get("menu_name", "")
        if not food_name:
            continue

        result = cached_search(food_name, client)
        if result is None:
            continue

        for col in NUTRITION_COLS:
            if pd.isnull(df.at[idx, col]) and col in result:
                df.at[idx, col] = result[col]

        filled_count += 1
        if filled_count % 10 == 0:
            print(f"  진행: {filled_count}/{len(missing_rows)}")

    print(f"API로 보완 완료: {filled_count}개")
    df.to_csv(db_path, index=False, encoding="utf-8-sig")
    print(f"저장: {db_path}")

    return df


if __name__ == "__main__":
    fill_missing_nutrition()
