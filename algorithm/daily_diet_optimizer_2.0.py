import pandas as pd
import numpy as np
import random
import os
import sys
from collections import Counter

# -----------------------------------------------------------
# [제약 조건 상수 설정]
# -----------------------------------------------------------
ATWATER_P = 4
ATWATER_C = 4
ATWATER_F = 9
SODIUM_MAX_LIMIT = 2500
SUGAR_CAL_PERCENT = 0.10 

MACRO_GOAL_RATIOS = {
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)},
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

def calculate_macro_grams(target_cal, user_goal):
    goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
    if not goal_ratios: raise ValueError(f"❌ 잘못된 목표입니다.")
    
    P_ratio = (goal_ratios['P'][0] + goal_ratios['P'][1]) / 2
    C_ratio = (goal_ratios['C'][0] + goal_ratios['C'][1]) / 2
    F_ratio = (goal_ratios['F'][0] + goal_ratios['F'][1]) / 2
    
    target_prot = round((target_cal * P_ratio) / ATWATER_P)
    target_carbs = round((target_cal * C_ratio) / ATWATER_C)
    target_fat = round((target_cal * F_ratio) / ATWATER_F)
    return target_prot, target_carbs, target_fat

# -----------------------------------------------------------
# 🧬 [New] 다양성 관리 클래스 (Vectorization & Hamming Distance)
# -----------------------------------------------------------
class DiversityManager:
    def __init__(self):
        # 1. 브랜드 인덱스 정의
        self.brands = ['CU', 'GS25', '세븐일레븐', '이마트24']
        
        # 2. 카테고리 키워드 정의 (메뉴명에서 추출)
        self.categories = {
            'RICE': ['밥', '도시락', '김밥', '주먹밥', '비빔밥', '덮밥', '리조또', '국밥'],
            'NOODLE': ['면', '라면', '우동', '파스타', '국수', '스파게티', '짜장', '짬뽕'],
            'BREAD': ['빵', '버거', '샌드위치', '토스트', '케이크', '머핀', '핫도그', '베이글'],
            'MEAT': ['닭', '치킨', '돈까스', '불고기', '소시지', '햄', '수육', '스테이크', '제육'],
            'SEAFOOD': ['참치', '게맛살', '새우', '오징어', '어묵'],
            'SALAD': ['샐러드', '채소', '과일', '야채'],
            'DAIRY': ['우유', '치즈', '요거트', '유산균', '라떼'],
            'DRINK': ['음료', '워터', '주스', '티', '커피', '아메리카노']
        }
        self.cat_keys = list(self.categories.keys())

    def create_vector(self, item):
        """
        개별 아이템을 이진 벡터(List[int])로 변환합니다.
        구조: [Brand_OneHot(4)] + [Category_OneHot(8)] = 총 12비트
        """
        vector = []
        
        # 1. Brand Vector (4 bit)
        store = item.get('store_name', item.get('제조사명', 'Unknown'))
        for b in self.brands:
            vector.append(1 if b in store else 0)
            
        # 2. Category Vector (8 bit) - 메뉴명 기반
        name = item.get('menu_name', item.get('식품명', '')).replace(" ", "")
        for cat in self.cat_keys:
            keywords = self.categories[cat]
            is_match = any(k in name for k in keywords)
            vector.append(1 if is_match else 0)
            
        return np.array(vector)

    def calculate_hamming_distance(self, vec1, vec2):
        """두 벡터 간의 해밍 거리(서로 다른 비트 수)를 계산"""
        return np.sum(np.abs(vec1 - vec2))

    def get_diversity_score(self, combo):
        """
        조합 내 모든 아이템 쌍(Pair) 간의 해밍 거리 평균을 계산
        (점수가 높을수록 구성이 다양함)
        """
        if len(combo) < 2:
            return 0.0
            
        vectors = [self.create_vector(item) for item in combo]
        distances = []
        
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                dist = self.calculate_hamming_distance(vectors[i], vectors[j])
                distances.append(dist)
                
        return np.mean(distances) if distances else 0.0


class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.0 Hamming Distance Diversity)...")
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일 없음")
        
        self.df = pd.read_csv(data_path)
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = ""
        
        self.menu_items = self.df.to_dict('records') 
        self.main_dishes = self.df.to_dict('records') 
        
        # 🧬 다양성 매니저 초기화
        self.div_manager = DiversityManager()
        
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 메뉴")

    def filter_by_allergens(self, allergies_to_avoid):
        if not allergies_to_avoid: return self.main_dishes
        allergens_lower = [a.lower() for a in allergies_to_avoid]
        safe_menu_items = []
        for item in self.main_dishes:
            is_safe = True
            for allergen in allergens_lower:
                if allergen in item['allergens_scraped']:
                    is_safe = False; break
            if is_safe: safe_menu_items.append(item)
        return safe_menu_items

    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT / 3 * 1.2) 
        sugar_max_grams = (target_cal * SUGAR_CAL_PERCENT) / ATWATER_C
        is_sugar_valid = (total_sugars <= sugar_max_grams * 1.5) 

        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            is_ratio_valid = (goal_ratios['C'][0] - 0.08 <= C_perc <= goal_ratios['C'][1] + 0.08) and \
                             (goal_ratios['P'][0] - 0.08 <= P_perc <= goal_ratios['P'][1] + 0.08) and \
                             (goal_ratios['F'][0] - 0.08 <= F_perc <= goal_ratios['F'][1] + 0.08)

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid

    def get_pareto_optimal_sets(self, candidates):
        # 파레토 최적화: 가격(낮음), 오차(낮음), 다양성(높음)
        # 다양성은 높을수록 좋으므로 음수로 변환하여 최소화 문제로 취급하거나, 정렬 시 고려
        # 여기서는 기존 로직 유지하되, 다양성 점수가 높은 순으로 2차 정렬
        sorted_candidates = sorted(candidates, key=lambda x: (x['error'], -x['diversity_score']))
        return sorted_candidates[:10] # 상위 10개 반환

    def get_priority_focus(self, solution, top_solutions):
        if solution['diversity_score'] >= 4.0: return "🌈 다양성 최고 (Hamming High)"
        min_price = min(s['price'] for s in top_solutions)
        if solution['price'] == min_price: return "🥇 최저 비용"
        return "💡 균형 조합"

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, allergies_to_avoid=[], excluded_codes=None, num_simulations=100000):
        if excluded_codes is None: excluded_codes = set()
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        
        safe_dishes = self.filter_by_allergens(allergies_to_avoid)
        filtered_dishes = [item for item in safe_dishes if item.get('FOOD_CODE') not in excluded_codes]
        if len(filtered_dishes) < 4: filtered_dishes = safe_dishes

        print(f"🔄 시뮬레이션 (Target: {target_cal}kcal) | 후보 {len(filtered_dishes)}개 | Hamming Distance 적용")

        valid_combinations = []
        
        for _ in range(num_simulations):
            k = random.randint(1, 4) 
            if len(filtered_dishes) >= k:
                combo = random.sample(filtered_dishes, k=k)
            else:
                combo = random.choices(filtered_dishes, k=k)
            
            total_price = sum(item['price'] for item in combo)
            
            # 영양 오차 계산
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            is_target_met = (target_cal * 0.70 <= tot_cal <= target_cal * 1.30) and (tot_prot >= target_prot * 0.70) 
            
            # 🧬 [New] 다양성 점수 계산 (Hamming Distance)
            div_score = self.div_manager.get_diversity_score(combo)
            
            # 다양성 필터: 2개 이상 선택 시, 너무 비슷한(Hamming 거리 0~1) 조합은 제외
            # 예: 참치마요(밥) + 전주비빔(밥) => 거리 가까움 => 탈락 유도
            is_diverse_enough = True
            if k > 1 and div_score < 1.0: # 최소한의 다양성 기준
                is_diverse_enough = False

            if is_target_met and is_ratio_valid and is_sodium_valid and is_sugar_valid and is_diverse_enough:
                valid_combinations.append({
                    'combo': combo,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'sodium': tot_sodium,
                    'error': error,
                    'diversity_score': div_score # 결과에 저장
                })

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations: return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        top_k_results = self.get_pareto_optimal_sets(valid_combinations)
        return top_k_results

# -----------------------------------------------------
# 실행 테스트
# -----------------------------------------------------
if __name__ == "__main__":
    USER_GOAL = "건강관리" 
    USER_CAL_DAILY = 2200 
    
    daily_prot_g, daily_carbs_g, daily_fat_g = calculate_macro_grams(USER_CAL_DAILY, USER_GOAL)
    
    MEALS_COUNT = 3
    meal_CAL_TARGET = round(USER_CAL_DAILY / MEALS_COUNT)
    meal_PROT_TARGET = round(daily_prot_g / MEALS_COUNT)
    
    print("\n==================================================")
    print(f"🥗 AI 식단 추천 v2.0 (Hamming Diversity Applied)")
    print(f"⭐ 1끼 목표: {meal_CAL_TARGET}kcal, 단백질 {meal_PROT_TARGET}g")
    print("==================================================")

    optimizer = DailyDietOptimizer()
    
    all_meal_results = []
    excluded_item_codes = set()
    
    for i in range(MEALS_COUNT):
        print(f"\n>>>>>>> 🥣 Meal {i+1} <<<<<<<")
        meal_result = optimizer.recommend_daily_diet(
            target_cal=meal_CAL_TARGET, 
            target_prot=meal_PROT_TARGET, 
            user_goal=USER_GOAL,
            excluded_codes=excluded_item_codes
        )
        
        if isinstance(meal_result, str):
            print(f"❌ {meal_result}")
            all_meal_results.append(None)
        else:
            # 다양성 점수와 에러를 고려해 1순위 선택
            best_combo = meal_result[0]
            all_meal_results.append(best_combo) 
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'): excluded_item_codes.add(item['FOOD_CODE'])

    # 최종 출력
    if any(all_meal_results):
        print("\n\n==================================================")
        print(f"📊 최종 추천 결과 (다양성 점수 포함)")
        print("==================================================")
        
        total_price = 0
        total_cal = 0
        
        for i, res in enumerate(all_meal_results):
            if res is None: continue
            total_price += res['price']
            total_cal += res['calories']
            
            div_msg = f"🌈 Hamming Score: {res['diversity_score']:.1f}" if len(res['combo']) > 1 else "1개 품목"
            print(f"\n[{i+1}끼] {len(res['combo'])}개 메뉴 | {div_msg}")
            for menu in res['combo']:
                store = menu.get('store_name', menu.get('제조사명', '편의점'))
                name = menu.get('menu_name', menu.get('식품명', '상품명'))
                print(f"  - [{store}] {name} ({menu['price']:,}원)")
        
        print("-" * 50)
        print(f"💰 총 금액: {total_price:,}원 | 🔥 총 칼로리: {total_cal:.0f}kcal")
        print("==================================================")