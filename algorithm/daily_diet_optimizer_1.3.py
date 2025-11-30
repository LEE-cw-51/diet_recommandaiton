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

# 에너지 적정 비율 (EER) 설정
MACRO_GOAL_RATIOS = {
    # P: (P_min, P_max), C: (C_min, C_max), F: (F_min, F_max) - (±5% 허용 범위)
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)},
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v1.3 - 단백질 제약 강화)...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"❌ 데이터 파일이 없습니다.")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝 및 필터링
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        self.menu_items = self.df.to_dict('records')
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 유효 메뉴 로드됨")

    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        # ... (생략: 오차 및 EER 계산 로직은 동일) ...
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sat_fat = sum(item['saturated_fat'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        # EER 비율 및 나트륨 체크 로직 (생략: v1.2와 동일)
        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT)

        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            is_ratio_valid = (goal_ratios['C'][0] <= C_perc <= goal_ratios['C'][1]) and \
                             (goal_ratios['P'][0] <= P_perc <= goal_ratios['P'][1]) and \
                             (goal_ratios['F'][0] <= F_perc <= goal_ratios['F'][1])

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sat_fat, total_sugars, is_ratio_valid, is_sodium_valid

    def get_pareto_optimal_sets(self, candidates):
        # ... (생략: 파레토 최적화 로직은 동일) ...
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')

        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        
        return pareto_frontier

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, meals_count=3, num_simulations=100000):
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios: raise ValueError(f"❌ 잘못된 목표입니다.")

        print(f"🔄 시뮬레이션 시작: 목표='{user_goal}', {meals_count}끼 (단백질 상한 110% 제약)")

        valid_combinations = []
        
        for _ in range(num_simulations):
            if len(self.menu_items) >= meals_count:
                combo = random.sample(self.menu_items, k=meals_count)
            else:
                combo = random.choices(self.menu_items, k=meals_count)

            total_price = sum(item['price'] for item in combo)
            
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sat_fat, tot_sugars, is_ratio_valid, is_sodium_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            # ---------------------------------------------------------
            # [핵심 수정] 단백질 상한선 추가 (최대 110%까지만 허용)
            # ---------------------------------------------------------
            is_target_met = (target_cal * 0.85 <= tot_cal <= target_cal * 1.15) and \
                            (target_prot * 0.90 <= tot_prot <= target_prot * 1.10) 
            
            if is_target_met and is_ratio_valid and is_sodium_valid:
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
        return final_solutions[:min(5, len(final_solutions))]

# -----------------------------------------------------
# 테스트 실행 (체중 기반 단백질 목표 설정)
# -----------------------------------------------------
if __name__ == "__main__":
    # 사용자 정의 변수
    USER_WEIGHT = 75 # kg (예시)
    PROTEIN_FACTOR = 1.6 # g/kg (활동량 많은 성인 기준)
    USER_PROT = round(USER_WEIGHT * PROTEIN_FACTOR) # 75kg * 1.6g = 120g
    
    # 시나리오 설정
    USER_GOAL = "다이어트" 
    USER_CAL = 2000
    MEALS = 3
    
    print(f"📊 [사용자 설정] 체중: {USER_WEIGHT}kg, 목표 단백질: {USER_PROT}g")
    
    optimizer = DailyDietOptimizer()
    result = optimizer.recommend_daily_diet(
        target_cal=USER_CAL, target_prot=USER_PROT, meals_count=MEALS, user_goal=USER_GOAL
    )
    
    if isinstance(result, str):
        print(result)
    else:
        print("\n==================================================")
        print(f"🥗 [AI 추천 결과] {MEALS}끼 식단 (v1.3 - 단백질 제약 적용)")
        print("==================================================")
        
        for i, res in enumerate(result):
            # EER 비율 검증 출력
            macro_sum_cal = (res['carbs'] * ATWATER_C) + (res['protein'] * ATWATER_P) + (res['fat'] * ATWATER_F)
            
            print(f"\n[옵션 {i+1}번]")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  🔥 칼로리: {res['calories']:.0f}kcal (목표 {USER_CAL}kcal)")
            
            print("  --- 영양 상세 ---")
            print(f"  💪 단백질: {res['protein']:.0f}g (EER: {res['protein']*ATWATER_P/macro_sum_cal*100:.1f}%)")
            print(f"  🍚 탄수화물: {res['carbs']:.0f}g (EER: {res['carbs']*ATWATER_C/macro_sum_cal*100:.1f}%)")
            print(f"  🥓 지방: {res['fat']:.0f}g (EER: {res['fat']*ATWATER_F/macro_sum_cal*100:.1f}%)")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg (포화지방: {res['saturated_fat']:.1f}g | 당류: {res['sugars']:.0f}g)")
            
            print("  --- 상세 식단 ---")
            for menu in res['combo']:
                print(f"    - [{menu['store_name']}] {menu['menu_name']} ({menu['price']:,}원, {menu['calories']:.0f}kcal)")
        print("==================================================")