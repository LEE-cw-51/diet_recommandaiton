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
        print("⚙️ AI 추천 엔진 초기화 중 (v1.9 Sequential Diversity)...")
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
        
        self.menu_items = self.df.to_dict('records') 
        
        # 메인 요리 제약 해제
        self.main_dishes = self.df.to_dict('records') 
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 메뉴 | 후보군 제약 해제됨 (Total {len(self.main_dishes)} items)")

    def filter_by_allergens(self, allergies_to_avoid):
        # (생략: v1.8과 동일한 알레르기 필터링 로직)
        if not allergies_to_avoid:
            return self.main_dishes
            
        allergens_lower = [a.lower() for a in allergies_to_avoid]
        safe_menu_items = []
        
        for item in self.main_dishes:
            is_safe = True
            for allergen in allergens_lower:
                if allergen in item['allergens_scraped']:
                    is_safe = False
                    break
            
            if is_safe:
                safe_menu_items.append(item)
                
        return safe_menu_items


    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        # (생략: v1.8과 동일한 영양소 오차 및 제약 조건 검증 로직)
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        total_sat_fat = sum(item['saturated_fat'] for item in combo)
        
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
            
            is_ratio_valid = (goal_ratios['C'][0] - 0.05 <= C_perc <= goal_ratios['C'][1] + 0.05) and \
                             (goal_ratios['P'][0] - 0.05 <= P_perc <= goal_ratios['P'][1] + 0.05) and \
                             (goal_ratios['F'][0] - 0.05 <= F_perc <= goal_ratios['F'][1] + 0.05)

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sat_fat, total_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid

    def get_pareto_optimal_sets(self, candidates):
        # (생략: v1.8과 동일한 파레토 최적화 로직)
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')

        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        
        return pareto_frontier

    def get_priority_focus(self, solution, top_solutions):
        # (생략: v1.8과 동일한 우선순위 부여 로직)
        min_price = min(s['price'] for s in top_solutions)
        min_sodium = min(s['sodium'] for s in top_solutions)
        min_sat_fat = min(s['saturated_fat'] for s in top_solutions)
        min_error = min(s['error'] for s in top_solutions)
        
        if solution['price'] == min_price: return "🥇 최저 비용"
        if solution['sodium'] == min_sodium: return "🌱 최저 나트륨"
        if solution['saturated_fat'] == min_sat_fat: return "❤️ 최저 포화지방"
        if solution['error'] < min_error * 1.05: return "🎯 목표 정확도 최우선"
            
        return "💡 균형 조합"


    # ❗ [v1.9 변경점] excluded_codes 매개변수 추가
    def recommend_daily_diet(self, target_cal, target_prot, user_goal, allergies_to_avoid=[], excluded_codes=None, num_simulations=100000):
        
        if excluded_codes is None:
            excluded_codes = set()
            
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios: raise ValueError(f"❌ 잘못된 목표입니다.")

        # 1. 알레르기 필터링
        safe_dishes = self.filter_by_allergens(allergies_to_avoid)

        # ❗ 2. 이전 식단에 포함된 아이템 제외 필터링
        filtered_dishes = [item for item in safe_dishes if item.get('FOOD_CODE') not in excluded_codes]

        
        if len(filtered_dishes) < 4:
             # 제외 항목이 많아 후보군이 부족하면 기존 항목 포함하여 다시 시도 (최소한의 안전장치)
             filtered_dishes = safe_dishes

        print(f"🔄 시뮬레이션 시작: 1끼 목표 (Cal:{target_cal}, Prot:{target_prot}) | 남은 후보 {len(filtered_dishes)}개")

        valid_combinations = []
        
        for _ in range(num_simulations):
            
            k = random.randint(1, 4) 
            
            # ❗ 필터링된 리스트에서 샘플링
            if len(filtered_dishes) >= k:
                combo = random.sample(filtered_dishes, k=k)
            else:
                # 후보군 부족 시 중복 허용
                combo = random.choices(filtered_dishes, k=k)
            
            total_price = sum(item['price'] for item in combo)
            
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sat_fat, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            is_target_met = (target_cal * 0.70 <= tot_cal <= target_cal * 1.30) and (tot_prot >= target_prot * 0.70) 
            
            # 브랜드 제약
            brands = [item.get('store_name', item.get('제조사명', 'Unknown')) for item in combo]
            brand_counts = Counter(brands)
            is_diverse = not any(count > 2 for count in brand_counts.values())

            if is_target_met and is_ratio_valid and is_sodium_valid and is_sugar_valid and is_diverse:
                valid_combinations.append({
                    'combo': combo,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'saturated_fat': tot_sat_fat,
                    'sodium': tot_sodium,
                    'sugars': tot_sugars,
                    'error': error
                })

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations:
            return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        pareto_solutions = self.get_pareto_optimal_sets(valid_combinations)
        print(f"   🏆 파레토 최적해 도출: {len(pareto_solutions)}개")
        
        final_solutions = sorted(pareto_solutions, key=lambda x: x['price'])
        top_k_results = final_solutions[:min(5, len(final_solutions))]
        
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
    print(f"🍽️ 일일 목표: {USER_CAL_DAILY}kcal | 목표: {USER_GOAL}")
    print(f"    - 총 목표(g): 단 {daily_prot_g} / 탄 {daily_carbs_g} / 지 {daily_fat_g}")
    print(f"⭐ 1끼 목표 (균등 분배): 약 {meal_CAL_TARGET}kcal, 단백질 {meal_PROT_TARGET}g")
    print("==================================================")

    optimizer = DailyDietOptimizer()
    
    all_meal_results = []
    excluded_item_codes = set() # ❗ [v1.9] 제외할 FOOD_CODE 저장용 Set
    
    for i in range(MEALS_COUNT):
        print(f"\n>>>>>>> 🥣 Meal {i+1} 추천 (아침/점심/저녁) <<<<<<<")
        
        meal_result = optimizer.recommend_daily_diet(
            target_cal=meal_CAL_TARGET, 
            target_prot=meal_PROT_TARGET, 
            user_goal=USER_GOAL,
            allergies_to_avoid=USER_ALLERGIES,
            excluded_codes=excluded_item_codes # ❗ 제외 목록 전달
        )
        
        if isinstance(meal_result, str):
            print(f"❌ Meal {i+1} : {meal_result}")
            all_meal_results.append(None)
        else:
            best_combo = meal_result[0]
            all_meal_results.append(best_combo) 
            
            # ❗ 성공 시, 해당 식단에 사용된 FOOD_CODE를 제외 목록에 추가
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'):
                    excluded_item_codes.add(item['FOOD_CODE'])


    # -----------------------------------------------------
    # 3. 최종 결과 출력
    # -----------------------------------------------------
    if any(all_meal_results):
        
        final_total = {
            'price': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sodium': 0
        }
        
        print("\n\n==================================================")
        print(f"🥗 [AI 추천 결과 v1.9] 3끼 균등 분배 (순차적 다양성)")
        print("==================================================")
        
        for i, res in enumerate(all_meal_results):
            if res is None:
                print(f"❌ Meal {i+1} : 추천 실패")
                continue
                
            for key in final_total.keys():
                final_total[key] += res[key]
                
            print(f"\n>>> 🥣 Meal {i+1} (품목 수: {len(res['combo'])}개)")
            print(f"  💸 {res['price']:,}원 | 🔥 {res['calories']:.0f}kcal")
            print(f"  📊 탄 {res['carbs']:.0f}g | 단 {res['protein']:.0f}g | 지 {res['fat']:.0f}g | 나 {res['sodium']:.0f}mg")
            
            for menu in res['combo']:
                store = menu.get('store_name', menu.get('제조사명', '편의점'))
                name = menu.get('menu_name', menu.get('식품명', '상품명'))
                print(f"    - [{store}] {name} ({menu['price']:,}원)")

        print("\n==================================================")
        print("📊 📅 일일 전체 합계 (Total Daily Intake)")
        print("==================================================")
        
        print(f"💸 총 가격: {final_total['price']:,}원")
        print(f"🔥 총 칼로리: {final_total['calories']:.0f}kcal (목표: {USER_CAL_DAILY})")
        
        print("\n--- 영양 성분 달성률 ---")
        if daily_prot_g > 0:
            print(f"💪 단백질: {final_total['protein']:.0f}g (목표: {daily_prot_g}g | 달성률: {final_total['protein']/daily_prot_g*100:.1f}%)")
        if daily_carbs_g > 0:
            print(f"🍚 탄수화물: {final_total['carbs']:.0f}g (목표: {daily_carbs_g}g | 달성률: {final_total['carbs']/daily_carbs_g*100:.1f}%)")
        if daily_fat_g > 0:
            print(f"🥓 지방: {final_total['fat']:.0f}g (목표: {daily_fat_g}g | 달성률: {final_total['fat']/daily_fat_g*100:.1f}%)")
        print(f"🧂 나트륨: {final_total['sodium']:.0f}mg (제한: {SODIUM_MAX_LIMIT}mg)")
        print("==================================================")