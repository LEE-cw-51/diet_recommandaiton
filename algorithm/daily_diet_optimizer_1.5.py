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
        print("⚙️ AI 추천 엔진 초기화 중 (v1.5 - 최종 로직)...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"❌ 데이터 파일이 없습니다: {data_path}")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝 및 필터링
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        # 알레르기 컬럼 문자열로 변환 및 소문자화 (필터링 준비)
        self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        self.main_dishes = self.df[(self.df['calories'] >= 250) & (self.df['price'] >= 3500)].to_dict('records')
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 유효 메뉴 로드됨")

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
        """식단 조합의 영양소 오차 및 제약 조건(비율, 나트륨, 당류) 검증"""
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        
        # 1. 목표 달성도 오차 계산 (RMSE 방식)
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        # 2. 제약 조건 검증
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT)

        # ❗ NEW: 당류 상한선 동적 계산 및 체크 (칼로리의 10% 내외)
        sugar_max_grams = (target_cal * SUGAR_CAL_PERCENT) / ATWATER_C
        is_sugar_valid = (total_sugars <= sugar_max_grams)

        # 매크로 비율 계산
        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            # 사용자 목표 비율 범위 내에 있는지 확인
            is_ratio_valid = (goal_ratios['C'][0] <= C_perc <= goal_ratios['C'][1]) and \
                             (goal_ratios['P'][0] <= P_perc <= goal_ratios['P'][1]) and \
                             (goal_ratios['F'][0] <= F_perc <= goal_ratios['F'][1])

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid

    def get_pareto_optimal_sets(self, candidates):
        """파레토 최적해(가격 vs 영양오차) 도출"""
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')

        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        
        return pareto_frontier

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, meals_count=3, allergies_to_avoid=[], num_simulations=100000):
        
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios:
            raise ValueError(f"❌ 잘못된 목표입니다. ({list(MACRO_GOAL_RATIOS.keys())} 중 선택)")

        # 1. 알레르기 필터링을 통해 안전한 메뉴 후보군 확보
        safe_dishes = self.filter_by_allergens(allergies_to_avoid)
        
        if len(safe_dishes) < meals_count:
             return "❌ 알레르기 필터링 후 남은 메뉴가 부족합니다."

        print(f"🔄 시뮬레이션 시작: 목표='{user_goal}', {meals_count}끼 (알레르기/당류 제약 적용)")

        valid_combinations = []
        
        for _ in range(num_simulations):
            # 중복 없는 조합 생성
            combo = random.sample(safe_dishes, k=meals_count) if len(safe_dishes) >= meals_count else random.choices(safe_dishes, k=meals_count)

            total_price = sum(item['price'] for item in combo)
            
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sugars, is_ratio_valid, is_sodium_valid, is_sugar_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            # 1차 필터링: (1) 목표 근접성 & (2) EER 준수 & (3) 나트륨 준수 & (4) 당류 준수
            is_target_met = (target_cal * 0.85 <= tot_cal <= target_cal * 1.15) and (tot_prot >= target_prot * 0.90) 
            
            # 브랜드 다양성 체크 (최대 2개 허용)
            brands = [item['store_name'] for item in combo]
            brand_counts = Counter(brands)
            is_diverse = not any(count > 2 for count in brand_counts.values())

            # ❗ 모든 제약 조건 통과 시 valid_combinations에 추가
            if is_target_met and is_ratio_valid and is_sodium_valid and is_sugar_valid and is_diverse:
                valid_combinations.append({
                    'combo': combo,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'carbs': tot_carbs,
                    'fat': tot_fat,
                    'sodium': tot_sodium,
                    'sugars': tot_sugars,
                    'error': error
                })

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations:
            return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        # 4. 파레토 최적화 및 결과 반환
        pareto_solutions = self.get_pareto_optimal_sets(valid_combinations)
        print(f"   🏆 파레토 최적해 도출: {len(pareto_solutions)}개")
        
        final_solutions = sorted(pareto_solutions, key=lambda x: x['price'])
        return final_solutions[:min(5, len(final_solutions))]

# -----------------------------------------------------
# 실행 테스트
# -----------------------------------------------------
if __name__ == "__main__":
    # 사용자 정의 변수 (예시: 75kg 활동적인 성인)
    USER_WEIGHT = 75 
    PROTEIN_FACTOR = 1.6 
    USER_PROT = round(USER_WEIGHT * PROTEIN_FACTOR) # 120g
    
    # [NEW] 알레르기 설정: 달걀(난류)과 땅콩을 피하는 사용자 시나리오
    USER_ALLERGIES = ['난류', '땅콩'] 

    # 시나리오 설정
    USER_GOAL = "다이어트" 
    USER_CAL = 2000
    MEALS = 3
    
    optimizer = DailyDietOptimizer()
    result = optimizer.recommend_daily_diet(
        target_cal=USER_CAL, target_prot=USER_PROT, meals_count=MEALS, user_goal=USER_GOAL,
        allergies_to_avoid=USER_ALLERGIES 
    )
    
    if isinstance(result, str):
        print(result)
    else:
        print("\n==================================================")
        print(f"🥗 [AI 추천 결과] {MEALS}끼 식단 (v1.5 - 최종) | 목표: {USER_GOAL}")
        print("==================================================")
        
        for i, res in enumerate(result):
            macro_sum_cal = (res['carbs'] * ATWATER_C) + (res['protein'] * ATWATER_P) + (res['fat'] * ATWATER_F)
            
            print(f"\n[옵션 {i+1}번 (파레토 최적)]")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  🔥 칼로리: {res['calories']:.0f}kcal")
            
            print("  --- 영양 상세 ---")
            print(f"  💪 단백질: {res['protein']:.0f}g (EER: {res['protein']*ATWATER_P/macro_sum_cal*100:.1f}%)")
            print(f"  🍚 탄수화물: {res['carbs']:.0f}g (EER: {res['carbs']*ATWATER_C/macro_sum_cal*100:.1f}%)")
            print(f"  🥓 지방: {res['fat']:.0f}g (EER: {res['fat']*ATWATER_F/macro_sum_cal*100:.1f}%)")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg (❗ 당류: {res['sugars']:.0f}g / 제한 {(USER_CAL * SUGAR_CAL_PERCENT / ATWATER_C):.1f}g)")
            
            print("  --- 상세 식단 ---")
            for menu in res['combo']:
                print(f"    - [{menu['store_name']}] {menu['menu_name']} ({menu['price']:,}원, {menu['calories']:.0f}kcal)")
        print("==================================================")