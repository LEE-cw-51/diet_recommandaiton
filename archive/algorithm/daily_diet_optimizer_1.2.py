import pandas as pd
import numpy as np
import random
import os
import sys
from collections import Counter

# -----------------------------------------------------------
# [제약 조건 상수]
# -----------------------------------------------------------
ATWATER_P = 4
ATWATER_C = 4
ATWATER_F = 9
SODIUM_MAX_LIMIT = 2500  # 현실성을 위해 2000 -> 2500으로 약간 완화 (선택사항)

# 사용자 목표별 에너지 적정 비율 (EER)
MACRO_GOAL_RATIOS = {
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)}, # 단백질 상한 50%까지 허용
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v1.2 - 메인요리 필터링 적용)...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"❌ 데이터 파일이 없습니다: {data_path}")
        
        self.df = pd.read_csv(data_path)
        
        # 숫자형 변환
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        # ---------------------------------------------------------
        # [핵심 수정 1] 메인 요리(Main Dish) 후보군 별도 정의
        # - 조건: 칼로리 250kcal 이상 AND 가격 3500원 이상
        # - 사이드(콜라, 콘샐러드 등)가 '끼니'로 선택되는 것 방지
        # ---------------------------------------------------------
        self.main_dishes = self.df[
            (self.df['calories'] >= 250) & 
            (self.df['price'] >= 3500)
        ].to_dict('records')
        
        print(f"✅ 데이터 로드 완료: 총 {len(self.df)}개 중 '메인 요리' 후보 {len(self.main_dishes)}개")

    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sat_fat = sum(item['saturated_fat'] for item in combo)
        total_sugars = sum(item['sugars'] for item in combo)
        
        # 1. RMSE 오차 계산
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        # 2. EER 비율 및 나트륨 체크
        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT)
        
        # [수정] 데이터 누락으로 나트륨이 0인 경우 -> 유효하지 않은 것으로 간주 (또는 경고)
        if total_sodium < 50: 
            is_sodium_valid = False 

        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            is_ratio_valid = (goal_ratios['C'][0] <= C_perc <= goal_ratios['C'][1]) and \
                             (goal_ratios['P'][0] <= P_perc <= goal_ratios['P'][1]) and \
                             (goal_ratios['F'][0] <= F_perc <= goal_ratios['F'][1])

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sat_fat, total_sugars, is_ratio_valid, is_sodium_valid

    def get_pareto_optimal_sets(self, candidates):
        # 가격 오름차순 정렬
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

        print(f"🔄 시뮬레이션 시작: {user_goal} 모드 | {meals_count}끼 (메인요리만 구성)")

        valid_combinations = []
        
        for _ in range(num_simulations):
            # [수정] main_dishes 리스트에서만 뽑음 (음료수 제외)
            if len(self.main_dishes) >= meals_count:
                combo = random.sample(self.main_dishes, k=meals_count)
            else:
                combo = random.choices(self.main_dishes, k=meals_count)

            # [핵심 수정 2] 브랜드 다양성 체크 (한 브랜드 몰빵 방지)
            # 3끼 중 동일 브랜드는 최대 2개까지만 허용
            brands = [item['store_name'] for item in combo]
            brand_counts = Counter(brands)
            if any(count > 2 for count in brand_counts.values()):
                continue

            total_price = sum(item['price'] for item in combo)
            
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, tot_sat_fat, tot_sugars, is_ratio_valid, is_sodium_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            # 1차 필터링
            is_target_met = (target_cal * 0.85 <= tot_cal <= target_cal * 1.15) and (tot_prot >= target_prot * 0.9)

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

        print(f"   ✅ 유효한 식단 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations:
            return "❌ 조건에 맞는 식단을 찾지 못했습니다."

        pareto_solutions = self.get_pareto_optimal_sets(valid_combinations)
        print(f"   🏆 파레토 최적해 도출: {len(pareto_solutions)}개")
        
        final_solutions = sorted(pareto_solutions, key=lambda x: x['price'])
        return final_solutions[:min(5, len(final_solutions))]

# -----------------------------------------------------
# 테스트 실행
# -----------------------------------------------------
if __name__ == "__main__":
    USER_GOAL = "다이어트"
    USER_CAL = 2000
    USER_PROT = 100
    MEALS = 3
    
    optimizer = DailyDietOptimizer()
    result = optimizer.recommend_daily_diet(
        target_cal=USER_CAL, target_prot=USER_PROT, meals_count=MEALS, user_goal=USER_GOAL
    )
    
    if isinstance(result, str):
        print(result)
    else:
        print("\n==================================================")
        print(f"🥗 [AI 추천 결과] {MEALS}끼 식단 (v1.2 - 메인요리 & 다양성)")
        print("==================================================")
        
        for i, res in enumerate(result):
            print(f"\n[옵션 {i+1}번]")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  🔥 칼로리: {res['calories']:.0f}kcal")
            
            macro_sum = (res['carbs']*4) + (res['protein']*4) + (res['fat']*9)
            
            print(f"  --- 영양 상세 ---")
            print(f"  💪 단백질: {res['protein']:.0f}g (EER: {res['protein']*4/macro_sum*100:.1f}%)")
            print(f"  🍚 탄수화물: {res['carbs']:.0f}g (EER: {res['carbs']*4/macro_sum*100:.1f}%)")
            print(f"  🥓 지방: {res['fat']:.0f}g (EER: {res['fat']*9/macro_sum*100:.1f}%)")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg")
            
            print("  --- 상세 식단 ---")
            for menu in res['combo']:
                print(f"    - [{menu['store_name']}] {menu['menu_name']} ({menu['price']:,}원, {menu['calories']:.0f}kcal)")
        print("==================================================")