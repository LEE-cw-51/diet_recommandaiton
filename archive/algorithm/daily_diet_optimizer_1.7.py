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

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v1.7 Detailed View)...")
        if not os.path.exists(data_path):
            # 경로 문제 발생 시 현재 폴더 기준으로 재시도 (실행 위치 유연성 확보)
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                 # data/processed/ 경로로 재시도
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다. 경로를 확인해주세요.")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝 및 필터링
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        # 알레르기 컬럼 문자열로 변환 및 소문자화 (필터링 준비)
        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = "" # 컬럼 없으면 빈 문자열 처리
        
        # 전체 메뉴 목록 정의
        self.menu_items = self.df.to_dict('records') 
        
        # 메인 요리 후보군 정의 (필터링된 서브셋)
        self.main_dishes = self.df[(self.df['calories'] >= 250) & (self.df['price'] >= 3500)].to_dict('records')
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 메뉴 | {len(self.main_dishes)}개 메인 요리 후보")

    def filter_by_allergens(self, allergies_to_avoid):
        """사용자가 피해야 할 알레르기 성분을 포함하는 메뉴를 제외합니다."""
        
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
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT)
        sugar_max_grams = (target_cal * SUGAR_CAL_PERCENT) / ATWATER_C
        is_sugar_valid = (total_sugars <= sugar_max_grams)

        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            is_ratio_valid = (goal_ratios['C'][0] <= C_perc <= goal_ratios['C'][1]) and \
                             (goal_ratios['P'][0] <= P_perc <= goal_ratios['P'][1]) and \
                             (goal_ratios['F'][0] <= F_perc <= goal_ratios['F'][1])

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sat_fat, total_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid

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
        min_sat_fat = min(s['saturated_fat'] for s in top_solutions)
        min_error = min(s['error'] for s in top_solutions)
        
        if solution['price'] == min_price: return "🥇 최저 비용"
        if solution['sodium'] == min_sodium: return "🌱 최저 나트륨"
        if solution['saturated_fat'] == min_sat_fat: return "❤️ 최저 포화지방"
        if solution['error'] < min_error * 1.05: return "🎯 목표 정확도 최우선"
            
        return "💡 균형 조합"


    def recommend_daily_diet(self, target_cal, target_prot, user_goal, meals_count=3, allergies_to_avoid=[], num_simulations=100000):
        
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios: raise ValueError(f"❌ 잘못된 목표입니다.")

        # 1. 알레르기 필터링
        safe_dishes = self.filter_by_allergens(allergies_to_avoid)
        
        if len(safe_dishes) < meals_count:
             return "❌ 알레르기 필터링 후 남은 메뉴가 부족합니다."

        print(f"🔄 시뮬레이션 시작: 목표='{user_goal}', {meals_count}끼")

        valid_combinations = []
        
        for _ in range(num_simulations):
            # 중복 없는 조합 생성 (safe_dishes에서 샘플링)
            combo = random.sample(safe_dishes, k=meals_count) if len(safe_dishes) >= meals_count else random.choices(safe_dishes, k=meals_count)

            total_price = sum(item['price'] for item in combo)
            
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sat_fat, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            is_target_met = (target_cal * 0.85 <= tot_cal <= target_cal * 1.15) and (tot_prot >= target_prot * 0.90) 
            
            # 브랜드 다양성 체크 (같은 브랜드 3개 몰빵 방지)
            brands = [item.get('store_name', 'Unknown') for item in combo] # store_name 없을 경우 대비
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
    USER_PROT = round(USER_WEIGHT * PROTEIN_FACTOR) # 120g
    USER_ALLERGIES = ['난류', '땅콩'] 

    USER_GOAL = "건강관리" 
    USER_CAL = 2200
    MEALS = 3
    
    # 클래스 인스턴스 생성 (경로는 자동 탐색)
    optimizer = DailyDietOptimizer()
    
    result = optimizer.recommend_daily_diet(
        target_cal=USER_CAL, target_prot=USER_PROT, meals_count=MEALS, user_goal=USER_GOAL,
        allergies_to_avoid=USER_ALLERGIES 
    )
    
    if isinstance(result, str):
        print(result)
    else:
        print("\n==================================================")
        print(f"🥗 [AI 추천 결과 v1.7] {MEALS}끼 식단 상세 | 목표: {USER_GOAL}")
        print("==================================================")
        
        for i, res in enumerate(result):
            priority_label = optimizer.get_priority_focus(res, result)
            
            macro_sum_cal = (res['carbs'] * ATWATER_C) + (res['protein'] * ATWATER_P) + (res['fat'] * ATWATER_F)
            
            print(f"\n[옵션 {i+1}번] {priority_label}")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  🔥 총 칼로리: {res['calories']:.0f}kcal")
            
            print("  --- 영양 합계 ---")
            print(f"  💪 단백질: {res['protein']:.0f}g ({res['protein']*ATWATER_P/macro_sum_cal*100:.1f}%)")
            print(f"  🍚 탄수화물: {res['carbs']:.0f}g ({res['carbs']*ATWATER_C/macro_sum_cal*100:.1f}%)")
            print(f"  🥓 지방: {res['fat']:.0f}g ({res['fat']*ATWATER_F/macro_sum_cal*100:.1f}%)")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg")
            
            print("  --- 상세 식단 (개별 영양성분) ---")
            for menu in res['combo']:
                # store_name과 menu_name 키가 확실하지 않을 경우를 대비해 get 사용
                store = menu.get('store_name', menu.get('제조사명', '편의점'))
                name = menu.get('menu_name', menu.get('식품명', '상품명'))
                
                # [v1.7 변경점] 개별 메뉴의 영양성분 출력 추가
                print(f"    - [{store}] {name}")
                print(f"      💰 {menu['price']:,}원 | 🔥 {menu['calories']:.0f}kcal")
                print(f"      📊 탄 {menu['carbs']:.1f}g | 단 {menu['protein']:.1f}g | 지 {menu['fat']:.1f}g | 나 {menu['sodium']:.0f}mg")
        print("==================================================")