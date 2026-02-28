"""
API 응답 캐시 관리
- database/nutrition_raw_data.json 파일에 결과를 저장해 중복 API 호출 방지
"""

import json
import os

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "nutrition_raw_data.json"
)


def load_cache() -> dict:
    """캐시 파일 로드"""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    """캐시 파일 저장"""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get(food_name: str) -> dict | None:
    """캐시에서 식품명으로 조회"""
    cache = load_cache()
    return cache.get(food_name)


def set(food_name: str, nutrition_data: dict) -> None:
    """캐시에 결과 저장"""
    cache = load_cache()
    cache[food_name] = nutrition_data
    save_cache(cache)


def cached_search(food_name: str, api_client) -> dict | None:
    """
    캐시 확인 후 없으면 API 호출

    Args:
        food_name: 식품명
        api_client: NutritionAPIClient 인스턴스

    Returns:
        영양성분 데이터 또는 None
    """
    cached = get(food_name)
    if cached is not None:
        return cached

    result = api_client.get_nutrition(food_name)
    if result:
        set(food_name, result)
    return result
