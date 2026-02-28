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


class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.4 Strict P >= 100% & Cal +/- 15%)...")
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다.")
        
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
        
        self.brand_menu_map = {}
        for item in self.menu_items:
            brand = item.get('store_name', item.get('제조사명', 'Unknown'))
            if brand not in self.brand_menu_map:
                self.brand_menu_map[brand] = []
            self.brand_menu_map[brand].append(item)
            
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 메뉴")

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

    # ❗ [v2.4] 반환값 수정
    def calculate_nutritional_error(self, combo, target_cal, target_prot, target_fat, goal_ratios):
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        
        t_cal = max(target_cal, 1)
        t_prot = max(target_prot, 1)
        t_fat = max(target_fat, 1)
        
        cal_error = ((total_cal - t_cal) / t_cal) ** 2
        prot_error = ((total_prot - t_prot) / t_prot) ** 2
        
        # 지방 초과 페널티
        fat_penalty = 0
        if total_fat > t_fat:
            fat_penalty = ((total_fat - t_fat) / t_fat) ** 2 * 2.0
            
        # 나트륨 초과 페널티
        sodium_penalty = 0
        if total_sodium > SODIUM_MAX_LIMIT / 3:
             sodium_penalty = ((total_sodium - (SODIUM_MAX_LIMIT/3)) / (SODIUM_MAX_LIMIT/3)) ** 2
            
        error_score = np.sqrt(cal_error + prot_error + fat_penalty + sodium_penalty)
        
        # -----------------------------------------------------
        # ❗ [v2.4] 하드 필터링 조건
        # -----------------------------------------------------
        # 단백질 >= 100%
        is_protein_min_met = (total_prot >= target_prot * 0.99) # 실수 오차 방지
        
        # 칼로리 +-15%
        is_cal_valid = (target_cal * 0.85 <= total_cal <= target_cal * 1.15)
        
        # 나트륨 상한선
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT * 0.5) 
        
        is_ratio_valid = True # 오차 점수가 제어하므로 유연하게 둠
        
        # ❗ is_protein_min_met와 is_cal_valid를 반환
        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sugars, is_ratio_valid, is_sodium_valid, is_protein_min_met, is_cal_valid

    def get_pareto_optimal_sets(self, candidates):
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')
        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        return pareto_frontier

    def recommend_daily_diet(self, target_cal, target_prot, target_fat, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=100000):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)

        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        print(f"🔄 시뮬레이션 (목표: Cal {int(target_cal)} +/- 15%, P >={int(target_prot)}g) | 브랜드: {available_brands}")

        valid_combinations = []
        
        for _ in range(num_simulations):
            selected_brand = random.choice(available_brands)
            brand_items = self.brand_menu_map[selected_brand]
            
            safe = self.filter_by_allergens(brand_items, allergies_to_avoid)
            filtered = [item for item in safe if item.get('FOOD_CODE') not in excluded_codes]
            if not filtered: continue

            k = random.randint(1, 4)
            combo = random.sample(filtered, k=k) if len(filtered) >= k else random.choices(filtered, k=k)
            
            total_price = sum(item['price'] for item in combo)
            
            # ❗ [v2.4] 반환값 변경에 따른 수정
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sugars, is_ratio_valid, is_sodium_valid, is_protein_min_met, is_cal_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, target_fat, goal_ratios
            )

            # ❗ [v2.4] 엄격한 필터 적용
            if is_protein_min_met and is_cal_valid and is_sodium_valid:
                valid_combinations.append({
                    'combo': combo,
                    'brand': selected_brand,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'sodium': tot_sodium,
                    'error': error
                })

        print(f"   ✅ 후보 발견: {len(valid_combinations)}개")
        if not valid_combinations: return "❌ 조건 만족 식단 없음"

        pareto = self.get_pareto_optimal_sets(valid_combinations)
        # 영양 오차가 가장 적은 순으로 정렬
        final_sorted = sorted(pareto, key=lambda x: x['error'])
        
        return final_sorted

# -----------------------------------------------------
# 실행 테스트 (Dynamic Daily Logic)
# -----------------------------------------------------
if __name__ == "__main__":
    USER_CAL_DAILY = 2200
    USER_GOAL = "건강관리" 
    
    try:
        daily_prot_g, daily_carbs_g, daily_fat_g = calculate_macro_grams(USER_CAL_DAILY, USER_GOAL)
    except ValueError: sys.exit(1)
    
    print("\n==================================================")
    print(f"🥗 AI 식단 추천 v2.4 (Nutrition Accuracy First)")
    print(f"🎯 일일 목표: {USER_CAL_DAILY}kcal | P {daily_prot_g}g | C {daily_carbs_g}g | F {daily_fat_g}g")
    print("==================================================")

    optimizer = DailyDietOptimizer()
    
    current_status = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0, 'price': 0, 'sodium': 0}
    all_meal_results = []
    
    excluded_codes = set()
    excluded_brands = set()
    MEALS_COUNT = 3

    for i in range(MEALS_COUNT):
        remaining_meals = MEALS_COUNT - i
        
        # 동적 목표 할당
        target_cal = max((USER_CAL_DAILY - current_status['calories']) / remaining_meals, 100)
        target_prot = max((daily_prot_g - current_status['protein']) / remaining_meals, 10)
        target_fat = max((daily_fat_g - current_status['fat']) / remaining_meals, 5)
        
        print(f"\n>>>>>>> 🥣 Meal {i+1} (목표: Cal {int(target_cal)} +/- 15%, P >={int(target_prot)}g) <<<<<<<")
        
        results = optimizer.recommend_daily_diet(
            target_cal=target_cal,
            target_prot=target_prot,
            target_fat=target_fat,
            user_goal=USER_GOAL,
            excluded_codes=excluded_codes,
            excluded_brands=excluded_brands
        )
        
        if isinstance(results, str):
            print(f"⚠️ {results} -> 브랜드 제약 해제 후 재시도")
            results = optimizer.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=USER_GOAL, excluded_codes=excluded_codes, excluded_brands=set()
            )

        if not isinstance(results, str):
            best_combo = results[0] 
            all_meal_results.append(best_combo)
            
            current_status['calories'] += best_combo['calories']
            current_status['protein'] += best_combo['protein']
            current_status['fat'] += best_combo['fat']
            current_status['carbs'] += best_combo['carbs']
            current_status['price'] += best_combo['price']
            current_status['sodium'] += best_combo['sodium']
            
            excluded_brands.add(best_combo['brand'])
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'): excluded_codes.add(item['FOOD_CODE'])
        else:
            all_meal_results.append(None)

    # -----------------------------------------------------
    # 최종 결과 출력
    # -----------------------------------------------------
    if any(all_meal_results):
        print("\n\n==================================================")
        print(f"📊 최종 추천 식단 (P >= 100%, Cal +/- 15%)")
        print("==================================================")
        
        for i, res in enumerate(all_meal_results):
            if res is None:
                print(f"❌ Meal {i+1} : 추천 실패")
                continue
                
            brand_name = res['brand']
            print(f"\n>>> 🥣 Meal {i+1} [{brand_name}] ({len(res['combo'])}개)")
            print(f"    합계: 💸 {res['price']:,}원 | 🔥 {res['calories']:.0f}kcal | P:{res['protein']:.0f}g | F:{res['fat']:.0f}g")
            
            print("    --------------------------------------------")
            for menu in res['combo']:
                name = menu.get('menu_name', menu.get('식품명', '상품명'))
                print(f"    - {name}")
                print(f"      └ 💸 {menu['price']:,}원 | 🔥 {menu['calories']:.0f} | P:{menu['protein']:.0f}g")

        print("\n==================================================")
        print("📊 📅 일일 전체 합계 (Total vs Goal)")
        print("==================================================")
        
        print(f"💸 총 가격: {current_status['price']:,}원")
        print(f"🔥 총 칼로리: {current_status['calories']:.0f}kcal (목표: {USER_CAL_DAILY})")
        
        print("\n--- 영양 성분 달성 현황 ---")
        p_rate = current_status['protein'] / daily_prot_g * 100 if daily_prot_g > 0 else 0
        f_rate = current_status['fat'] / daily_fat_g * 100 if daily_fat_g > 0 else 0
        
        print(f"💪 단백질: {current_status['protein']:.0f}g (목표 >={daily_prot_g}g | {p_rate:.1f}%)")
        print(f"🥓 지방  : {current_status['fat']:.0f}g (목표 <={daily_fat_g}g | {f_rate:.1f}%)")
        print(f"🧂 나트륨: {current_status['sodium']:.0f}mg (제한: {SODIUM_MAX_LIMIT}mg)")
        print("==================================================")