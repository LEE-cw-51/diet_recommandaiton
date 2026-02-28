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
# 🧬 [v2.1.2] 다양성 관리 클래스 (Hamming + Ingredient Check)
# -----------------------------------------------------------
class DiversityManager:
    def __init__(self):
        # 1. 카테고리 키워드
        self.categories = {
            'RICE': ['밥', '도시락', '김밥', '주먹밥', '비빔밥', '덮밥', '리조또', '국밥', '죽'],
            'NOODLE': ['면', '라면', '우동', '파스타', '국수', '스파게티', '짜장', '짬뽕'],
            'BREAD': ['빵', '버거', '샌드위치', '토스트', '케이크', '머핀', '핫도그', '베이글'],
            'MEAT': ['닭', '치킨', '돈까스', '불고기', '소시지', '햄', '수육', '스테이크', '제육', '너겟'],
            'SEAFOOD': ['참치', '게맛살', '새우', '오징어', '어묵', '핫바'],
            'SALAD': ['샐러드', '채소', '과일', '야채', '옥수수', '고구마'],
            'DAIRY': ['우유', '치즈', '요거트', '유산균', '라떼'],
            'DRINK': ['음료', '워터', '주스', '티', '커피', '아메리카노', '콜라', '사이다'],
            'SNACK': ['칩', '쿠키', '과자', '젤리', '초콜릿', '바']
        }
        self.cat_keys = list(self.categories.keys())
        
        # 2. ❗ [New] 핵심 재료 키워드 (중복 방지용)
        self.ingredients = [
            '참치', '치킨', '닭', '불고기', '비프', '소고기', '돼지', '돈까스', '스팸', '햄', 
            '새우', '오징어', '제육', '갈비', '베이컨', '계란', '명란'
        ]

    def create_vector(self, item):
        vector = []
        name = item.get('menu_name', item.get('식품명', '')).replace(" ", "")
        for cat in self.cat_keys:
            keywords = self.categories[cat]
            is_match = any(k in name for k in keywords)
            vector.append(1 if is_match else 0)
        return np.array(vector)

    def calculate_hamming_distance(self, vec1, vec2):
        return np.sum(np.abs(vec1 - vec2))

    def get_diversity_score(self, combo):
        if len(combo) < 2: return 0.0
        vectors = [self.create_vector(item) for item in combo]
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                dist = self.calculate_hamming_distance(vectors[i], vectors[j])
                distances.append(dist)
        return np.mean(distances) if distances else 0.0

    def check_ingredient_overlap(self, combo):
        """
        ❗ [New] 한 끼니 내에서 핵심 재료가 겹치는지 검사
        True: 중복 있음 (나쁜 조합), False: 중복 없음 (좋은 조합)
        """
        if len(combo) < 2: return False
        
        found_ingredients = []
        for item in combo:
            name = item.get('menu_name', item.get('식품명', ''))
            for ing in self.ingredients:
                if ing in name:
                    found_ingredients.append(ing)
        
        # 중복된 재료가 있는지 확인 (예: ['참치', '참치'] -> 중복)
        ingredient_counts = Counter(found_ingredients)
        for ing, count in ingredient_counts.items():
            if count > 1:
                return True # 중복 발생
                
        return False # 중복 없음


class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.1.2 Ingredient Filtering)...")
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다.")
        
        self.df = pd.read_csv(data_path)
        self.df = self.df[(self.df['price'] > 1000) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = ""
        
        self.menu_items = self.df.to_dict('records')
        self.brand_menu_map = {}
        for item in self.menu_items:
            brand = item.get('store_name', item.get('제조사명', 'Unknown'))
            if brand not in self.brand_menu_map:
                self.brand_menu_map[brand] = []
            self.brand_menu_map[brand].append(item)
            
        self.div_manager = DiversityManager()
        print(f"✅ 데이터 로드 완료: 총 {len(self.df)}개")

    def filter_by_allergens(self, dishes, allergies_to_avoid):
        if not allergies_to_avoid: return dishes
        allergens_lower = [a.lower() for a in allergies_to_avoid]
        safe_menu_items = []
        for item in dishes:
            is_safe = True
            for allergen in allergens_lower:
                if allergen in item['allergens_scraped']: is_safe = False; break
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
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT / 3 * 1.3)
        sugar_max_grams = (target_cal * SUGAR_CAL_PERCENT) / ATWATER_C
        is_sugar_valid = (total_sugars <= sugar_max_grams * 1.5) 

        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            # 비율 범위 (오차 함수가 메인이므로 조금 넓게 허용)
            is_ratio_valid = (goal_ratios['C'][0] - 0.1 <= C_perc <= goal_ratios['C'][1] + 0.1) and \
                             (goal_ratios['P'][0] - 0.1 <= P_perc <= goal_ratios['P'][1] + 0.1) and \
                             (goal_ratios['F'][0] - 0.1 <= F_perc <= goal_ratios['F'][1] + 0.1)

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid

    def get_pareto_optimal_sets(self, candidates):
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')
        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        return pareto_frontier

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=100000, relaxation_factor=1.0):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)

        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        valid_combinations = []
        
        for _ in range(num_simulations):
            selected_brand = random.choice(available_brands)
            brand_items = self.brand_menu_map[selected_brand]
            
            safe = self.filter_by_allergens(brand_items, allergies_to_avoid)
            filtered = [item for item in safe if item.get('FOOD_CODE') not in excluded_codes]
            if not filtered: continue

            k = random.randint(1, 4)
            if len(filtered) >= k:
                combo = random.sample(filtered, k=k)
            else:
                combo = random.choices(filtered, k=k)
            
            # 🧬 [v2.1.2] 재료 중복 검사 (참치+참치 방지)
            if self.div_manager.check_ingredient_overlap(combo):
                continue

            # 해밍 거리 검사
            div_score = 0
            if k > 1:
                div_score = self.div_manager.get_diversity_score(combo)
                if div_score < 1.0: continue
            
            total_price = sum(item['price'] for item in combo)
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )
            
            # ❗ [Relaxation] 영양 범위 유연성 적용 (기본 1.0, 재시도 시 확장)
            cal_min = 0.70 / relaxation_factor
            cal_max = 1.30 * relaxation_factor
            prot_min = 0.70 / relaxation_factor
            
            is_target_met = (target_cal * cal_min <= tot_cal <= target_cal * cal_max) and (tot_prot >= target_prot * prot_min) 

            if is_target_met and is_ratio_valid and is_sodium_valid and is_sugar_valid:
                valid_combinations.append({
                    'combo': combo,
                    'brand': selected_brand,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'sodium': tot_sodium,
                    'error': error,
                    'diversity_score': div_score
                })

        if not valid_combinations: return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        top_k_results = self.get_pareto_optimal_sets(valid_combinations)
        return top_k_results

# -----------------------------------------------------
# 🧪 [테스트] 랜덤 유저 + 브랜드 순환 우선 로직
# -----------------------------------------------------
class RandomUserGenerator:
    def __init__(self):
        self.goals = ["다이어트", "건강관리", "근육증가"]
        self.allergy_pool = ["난류", "땅콩", "우유", "대두", "밀", "새우", "복숭아"]
    def generate(self):
        weight = random.randint(45, 100)
        goal = random.choice(self.goals)
        activity_factor = random.uniform(1.2, 1.9)
        tdee = int(weight * 24 * activity_factor)
        target_cal = tdee
        if goal == "다이어트": target_cal = int(tdee * 0.85)
        elif goal == "근육증가": target_cal = int(tdee * 1.15)
        num_allergies = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        allergies = random.sample(self.allergy_pool, num_allergies)
        return {"weight": weight, "goal": goal, "target_cal": target_cal, "allergies": allergies}

if __name__ == "__main__":
    optimizer = DailyDietOptimizer()
    user_gen = RandomUserGenerator()
    NUM_USERS = 3
    
    for u_idx in range(NUM_USERS):
        user_profile = user_gen.generate()
        try:
            d_prot, d_carbs, d_fat = calculate_macro_grams(user_profile['target_cal'], user_profile['goal'])
        except: continue
            
        print(f"\n==================================================")
        print(f"👤 [User {u_idx+1}] 체중: {user_profile['weight']}kg | 목표: {user_profile['goal']}")
        print(f"   🎯 일일 타겟: {user_profile['target_cal']}kcal (P {d_prot}g / C {d_carbs}g / F {d_fat}g)")
        print("==================================================")
        
        MEALS_COUNT = 3
        meal_cal_target = round(user_profile['target_cal'] / MEALS_COUNT)
        meal_prot_target = round(d_prot / MEALS_COUNT)
        
        all_meal_results = []
        excluded_item_codes = set()
        excluded_brands = set()
        
        final_total = {'price': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sodium': 0}
        
        for i in range(MEALS_COUNT):
            # 1차 시도: 기본 조건
            meal_result = optimizer.recommend_daily_diet(
                target_cal=meal_cal_target, target_prot=meal_prot_target, 
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_item_codes, excluded_brands=excluded_brands 
            )
            
            # ❗ [v2.1.2] 실패 시 전략: 영양 제약 완화 -> 브랜드 제약 유지
            if isinstance(meal_result, str):
                print(f"   ⚠️ Meal {i+1} 1차 실패... 영양 제약 완화 후 재시도")
                meal_result = optimizer.recommend_daily_diet(
                    target_cal=meal_cal_target, target_prot=meal_prot_target, 
                    user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                    excluded_codes=excluded_item_codes, excluded_brands=excluded_brands,
                    num_simulations=150000, relaxation_factor=1.2 # 범위 20% 확장
                )
            
            # 2차 시도도 실패하면 -> 최후의 수단: 브랜드 제약 해제 (User 2 방지용)
            if isinstance(meal_result, str):
                print(f"   ⚠️ Meal {i+1} 2차 실패... 브랜드 제약 해제")
                meal_result = optimizer.recommend_daily_diet(
                    target_cal=meal_cal_target, target_prot=meal_prot_target, 
                    user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                    excluded_codes=excluded_item_codes, excluded_brands=set(), # 브랜드 리셋
                    relaxation_factor=1.2
                )

            if not isinstance(meal_result, str):
                best_combo = meal_result[0]
                all_meal_results.append(best_combo)
                
                excluded_brands.add(best_combo['brand'])
                for item in best_combo['combo']:
                    if item.get('FOOD_CODE'): excluded_item_codes.add(item['FOOD_CODE'])
                
                for k in final_total: final_total[k] += best_combo[k]
                    
                print(f"   >>> Meal {i+1} [{best_combo['brand']}]: {len(best_combo['combo'])}개 ({best_combo['price']:,}원)")
                for menu in best_combo['combo']:
                    print(f"       - {menu.get('menu_name', menu.get('식품명'))}")
            else:
                print(f"   >>> Meal {i+1}: ❌ 최종 실패")

        if any(all_meal_results):
            print("\n   📊 [일일 합계]")
            print(f"   💸 총액: {final_total['price']:,}원")
            print(f"   🔥 열량: {final_total['calories']:.0f}kcal ({final_total['calories']/user_profile['target_cal']*100:.1f}%)")
            print(f"   💪 단백질: {final_total['protein']:.0f}g ({final_total['protein']/d_prot*100:.1f}%)")
        print("\n")