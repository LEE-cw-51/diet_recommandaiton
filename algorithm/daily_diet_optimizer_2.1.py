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
SODIUM_MAX_LIMIT = 2500  # 1일 나트륨 상한선 (mg)
SUGAR_CAL_PERCENT = 0.10 # 1일 총 칼로리의 10%를 당류 상한선으로 설정

# 사용자 목표별 에너지 적정 비율 (EER) 설정
MACRO_GOAL_RATIOS = {
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)},
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

def calculate_macro_grams(target_cal, user_goal):
    """일일 목표 칼로리 및 목표에 따른 P/C/F 목표그램을 계산합니다."""
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
        print("⚙️ AI 추천 엔진 초기화 중 (v2.1 Brand Set & Rotation)...")
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다. 경로를 확인해주세요.")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝 및 기본 필터링 (최소 가격 1500원, 최소 칼로리 50kcal)
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = ""
        
        # 전체 메뉴 목록 정의
        self.menu_items = self.df.to_dict('records')
        
        # ❗ [v2.1] 브랜드별 메뉴 그룹화 (시뮬레이션 속도 최적화)
        self.brand_menu_map = {}
        for item in self.menu_items:
            # store_name 혹은 제조사명에서 브랜드 추출
            brand = item.get('store_name', item.get('제조사명', 'Unknown'))
            if brand not in self.brand_menu_map:
                self.brand_menu_map[brand] = []
            self.brand_menu_map[brand].append(item)
            
        print(f"✅ 데이터 로드 완료: 총 {len(self.df)}개 | 감지된 브랜드: {list(self.brand_menu_map.keys())}")

    def filter_by_allergens(self, dishes, allergies_to_avoid):
        if not allergies_to_avoid:
            return dishes
            
        allergens_lower = [a.lower() for a in allergies_to_avoid]
        safe_menu_items = []
        
        for item in dishes:
            is_safe = True
            for allergen in allergens_lower:
                if allergen in item['allergens_scraped']:
                    is_safe = False
                    break
            if is_safe:
                safe_menu_items.append(item)
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
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')

        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        return pareto_frontier

    def get_priority_focus(self, solution, top_solutions):
        min_price = min(s['price'] for s in top_solutions)
        min_sodium = min(s['sodium'] for s in top_solutions)
        min_error = min(s['error'] for s in top_solutions)
        
        if solution['price'] == min_price: return "🥇 최저 비용"
        if solution['sodium'] == min_sodium: return "🌱 최저 나트륨"
        if solution['error'] < min_error * 1.05: return "🎯 목표 정확도 최우선"
        return "💡 균형 조합"

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=100000):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
            
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios: raise ValueError(f"❌ 잘못된 목표입니다.")

        # 1. 사용 가능한 브랜드 선정 (제외 브랜드 필터링)
        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands:
            return "❌ 모든 브랜드가 제외되었습니다 (후보 부족)."

        print(f"🔄 시뮬레이션 시작 (Target: {target_cal}kcal) | 가용 브랜드: {available_brands}")

        valid_combinations = []
        
        for _ in range(num_simulations):
            # ❗ [Step 1] 랜덤 브랜드 선택 (단일 브랜드 구성 원칙)
            selected_brand = random.choice(available_brands)
            brand_items = self.brand_menu_map[selected_brand]
            
            # ❗ [Step 2] 해당 브랜드 내에서 알레르기/중복 아이템 필터링
            safe_brand_items = self.filter_by_allergens(brand_items, allergies_to_avoid)
            filtered_brand_items = [item for item in safe_brand_items if item.get('FOOD_CODE') not in excluded_codes]
            
            if not filtered_brand_items: continue # 해당 브랜드에 먹을 게 없으면 스킵

            # ❗ [Step 3] 1~4개 아이템 샘플링
            k = random.randint(1, 4)
            if len(filtered_brand_items) >= k:
                combo = random.sample(filtered_brand_items, k=k)
            else:
                combo = random.choices(filtered_brand_items, k=k)
            
            # [Step 4] 영양 및 제약조건 검증
            total_price = sum(item['price'] for item in combo)
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )
            is_target_met = (target_cal * 0.70 <= tot_cal <= target_cal * 1.30) and (tot_prot >= target_prot * 0.70) 

            if is_target_met and is_ratio_valid and is_sodium_valid and is_sugar_valid:
                valid_combinations.append({
                    'combo': combo,
                    'brand': selected_brand, # 선택된 브랜드 저장
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'sodium': tot_sodium,
                    'error': error
                })

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")
        if not valid_combinations: return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        top_k_results = self.get_pareto_optimal_sets(valid_combinations)
        return top_k_results

# -----------------------------------------------------
# 실행 테스트
# -----------------------------------------------------
if __name__ == "__main__":
    USER_WEIGHT = 75 
    PROTEIN_FACTOR = 1.6 
    USER_ALLERGIES = ['난류', '땅콩'] 
    USER_GOAL = "건강관리" 
    USER_CAL_DAILY = 2200 
    
    try:
        daily_prot_g, daily_carbs_g, daily_fat_g = calculate_macro_grams(USER_CAL_DAILY, USER_GOAL)
    except ValueError as e:
        print(e)
        sys.exit(1)
        
    MEALS_COUNT = 3
    meal_CAL_TARGET = round(USER_CAL_DAILY / MEALS_COUNT)
    meal_PROT_TARGET = round(daily_prot_g / MEALS_COUNT)
    
    print("\n==================================================")
    print(f"🥗 AI 식단 추천 v2.1 (단일 브랜드 세트 & 브랜드 순환)")
    print(f"⭐ 1끼 목표: {meal_CAL_TARGET}kcal, 단백질 {meal_PROT_TARGET}g")
    print("==================================================")

    optimizer = DailyDietOptimizer()
    
    all_meal_results = []
    excluded_item_codes = set()
    excluded_brands = set() # ❗ 이미 방문한 브랜드 저장
    
    for i in range(MEALS_COUNT):
        print(f"\n>>>>>>> 🥣 Meal {i+1} 추천 <<<<<<<")
        
        # 이전 끼니에 먹은 브랜드는 제외하고 추천 요청
        meal_result = optimizer.recommend_daily_diet(
            target_cal=meal_CAL_TARGET, 
            target_prot=meal_PROT_TARGET, 
            user_goal=USER_GOAL,
            allergies_to_avoid=USER_ALLERGIES,
            excluded_codes=excluded_item_codes,
            excluded_brands=excluded_brands 
        )
        
        if isinstance(meal_result, str):
            print(f"❌ {meal_result}")
            # 만약 추천 실패 시, 브랜드 제약을 풀고 재시도 (Fallback)
            print("⚠️ 브랜드 제약을 해제하고 재시도합니다.")
            meal_result = optimizer.recommend_daily_diet(
                target_cal=meal_CAL_TARGET, 
                target_prot=meal_PROT_TARGET, 
                user_goal=USER_GOAL,
                allergies_to_avoid=USER_ALLERGIES,
                excluded_codes=excluded_item_codes,
                excluded_brands=set() # 브랜드 초기화
            )
        
        if not isinstance(meal_result, str):
            best_combo = meal_result[0]
            all_meal_results.append(best_combo) 
            
            # 사용된 아이템 및 브랜드 제외 목록에 추가
            excluded_brands.add(best_combo['brand'])
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'): excluded_item_codes.add(item['FOOD_CODE'])
        else:
             all_meal_results.append(None)

    # -----------------------------------------------------
    # 최종 결과 출력 (상세 영양성분 포함)
    # -----------------------------------------------------
    if any(all_meal_results):
        final_total = {'price': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sodium': 0}
        
        print("\n\n==================================================")
        print(f"📊 최종 추천 식단 (3끼 브랜드 순환)")
        print("==================================================")
        
        for i, res in enumerate(all_meal_results):
            if res is None:
                print(f"❌ Meal {i+1} : 추천 실패")
                continue
                
            for key in final_total.keys():
                final_total[key] += res[key]
                
            brand_name = res['brand']
            print(f"\n>>> 🥣 Meal {i+1} [{brand_name}] (품목 수: {len(res['combo'])}개)")
            print(f"    합계: 💸 {res['price']:,}원 | 🔥 {res['calories']:.0f}kcal | 탄 {res['carbs']:.0f}g | 단 {res['protein']:.0f}g | 지 {res['fat']:.0f}g")
            
            print("    --------------------------------------------")
            for menu in res['combo']:
                name = menu.get('menu_name', menu.get('식품명', '상품명'))
                # 개별 영양성분 및 가격 출력
                print(f"    - {name}")
                print(f"      └ 💸 {menu['price']:,}원 | 🔥 {menu['calories']:.0f}kcal | C:{menu['carbs']:.1f}g P:{menu['protein']:.1f}g F:{menu['fat']:.1f}g")

        print("\n==================================================")
        print("📊 📅 일일 전체 합계 (Total Daily Intake)")
        print("==================================================")
        
        print(f"💸 총 가격: {final_total['price']:,}원")
        print(f"🔥 총 칼로리: {final_total['calories']:.0f}kcal (목표: {USER_CAL_DAILY})")
        
        print("\n--- 영양 성분 달성률 ---")
        if daily_prot_g > 0:
            print(f"💪 단백질: {final_total['protein']:.0f}g (목표: {daily_prot_g}g | {final_total['protein']/daily_prot_g*100:.1f}%)")
        if daily_carbs_g > 0:
            print(f"🍚 탄수화물: {final_total['carbs']:.0f}g (목표: {daily_carbs_g}g | {final_total['carbs']/daily_carbs_g*100:.1f}%)")
        if daily_fat_g > 0:
            print(f"🥓 지방: {final_total['fat']:.0f}g (목표: {daily_fat_g}g | {final_total['fat']/daily_fat_g*100:.1f}%)")
        print(f"🧂 나트륨: {final_total['sodium']:.0f}mg")
        print("==================================================")