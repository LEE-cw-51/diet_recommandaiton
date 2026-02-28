"""
공공데이터포털 식품영양성분 API 클라이언트
https://www.data.go.kr/data/15057298/openapi.do

사용 전 config/settings.py의 NUTRITION_API_KEY에 발급받은 API 키 입력 필요
"""

import requests
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings


class NutritionAPIClient:
    """공공 식품영양성분 API 클라이언트"""

    def __init__(self):
        self.api_key = settings.NUTRITION_API_KEY
        self.base_url = settings.NUTRITION_API_URL
        self.page_size = settings.NUTRITION_API_PAGE_SIZE

    def search(self, food_name: str, page: int = 1) -> list[dict]:
        """
        식품명으로 영양성분 검색

        Args:
            food_name: 검색할 식품명 (예: "삼각김밥")
            page: 페이지 번호 (기본값 1)

        Returns:
            영양성분 데이터 리스트
        """
        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": self.page_size,
            "type": "json",
            "FOOD_NM_KR": food_name,
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            items = data.get("body", {}).get("items", [])
            return items if isinstance(items, list) else []

        except requests.RequestException as e:
            print(f"API 요청 실패 ({food_name}): {e}")
            return []
        except (KeyError, ValueError) as e:
            print(f"API 응답 파싱 실패 ({food_name}): {e}")
            return []

    def get_nutrition(self, food_name: str) -> dict | None:
        """
        식품명으로 영양성분 조회 (첫 번째 결과 반환)

        Returns:
            {calories, protein, fat, carbs, sodium, sugars, saturated_fat} 또는 None
        """
        items = self.search(food_name)
        if not items:
            return None

        item = items[0]
        return {
            "calories":      float(item.get("NUTR_CONT1", 0) or 0),  # 에너지(kcal)
            "carbs":         float(item.get("NUTR_CONT2", 0) or 0),  # 탄수화물(g)
            "protein":       float(item.get("NUTR_CONT3", 0) or 0),  # 단백질(g)
            "fat":           float(item.get("NUTR_CONT4", 0) or 0),  # 지방(g)
            "sugars":        float(item.get("NUTR_CONT5", 0) or 0),  # 당류(g)
            "sodium":        float(item.get("NUTR_CONT6", 0) or 0),  # 나트륨(mg)
            "saturated_fat": float(item.get("NUTR_CONT8", 0) or 0),  # 포화지방(g)
            "api_food_name": item.get("FOOD_NM_KR", ""),
        }


if __name__ == "__main__":
    # 테스트 실행
    client = NutritionAPIClient()
    result = client.get_nutrition("삼각김밥")
    if result:
        print("검색 결과:", result)
    else:
        print("결과 없음 (API 키 확인 필요)")
