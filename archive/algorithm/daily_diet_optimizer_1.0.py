import pandas as pd
import numpy as np
import random
import os
import sys

# -----------------------------------------------------------
# [제약 조건 상수 설정]
# -----------------------------------------------------------
ATWATER_P = 4
ATWATER_C = 4
ATWATER_F = 9
SODIUM_MAX_LIMIT = 2000  # 1일 권장 나트륨 상한선 (mg)

# 사용자 목표별 에너지 적정 비율 (EER) 설정
# (최소 비율, 최대 비율)
MACRO_GOAL_RATIOS = {
    "다이어트": {
        'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25) # 탄40:단40:지20
    },
    "건강관리": {
        'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25) # 탄50:단30:지20
    },
    "근육증가": {
        'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25) # 탄40:단40:지20 (단백질 강화)
    }
}

# 프로젝트 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"❌ 데이터 파일이 없습니다: {data_path}")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝: 가격 1500원 초과, 칼로리 50kcal 초과 메뉴만 사용 (소스/음료 제외)
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        
        # 숫자형 변환 (안전 장치)
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        self.menu_items = self.df.to_dict('records')
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 유효 메뉴 로드됨")

    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        """
        식단 조합의 영양소 오차 계산 및 제약 조건(비율, 나트륨) 검증
        """
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        
        # 1. 목표 달성도 오차 계산 (RMSE 방식)
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        # 2. 제약 조건 검증
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT) # 나트륨 2000mg 이하

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

        return error_score, total_cal, total_prot, total_sodium, is_ratio_valid, is_sodium_valid

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

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, meals_count=3, num_simulations=100000):
        """
        사용자 목표(user_goal)에 맞춰 식단을 추천합니다.
        """
        # 1. 목표에 따른 비율 설정 로드
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios:
            raise ValueError(f"❌ 잘못된 목표입니다. ({list(MACRO_GOAL_RATIOS.keys())} 중 선택)")

        print(f"🔄 시뮬레이션 시작: 목표='{user_goal}', {meals_count}끼 식사 (나트륨제한 적용)")

        valid_combinations = []
        
        # 2. 몬테카를로 시뮬레이션
        for _ in range(num_simulations):
            # 중복 없는 메뉴 조합 시도
            if len(self.menu_items) >= meals_count:
                combo = random.sample(self.menu_items, k=meals_count)
            else:
                combo = random.choices(self.menu_items, k=meals_count)

            total_price = sum(item['price'] for item in combo)
            
            # 오차 및 제약조건 계산
            error, tot_cal, tot_prot, tot_sodium, is_ratio_valid, is_sodium_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, goal_ratios
            )

            # 3. 필터링: 칼로리/단백질 목표 근접성 + 비율 준수 + 나트륨 준수
            is_target_met = (target_cal * 0.85 <= tot_cal <= target_cal * 1.15) and (tot_prot >= target_prot * 0.9)

            if is_target_met and is_ratio_valid and is_sodium_valid:
                valid_combinations.append({
                    'combo': combo,
                    'price': total_price,
                    'calories': tot_cal,
                    'protein': tot_prot,
                    'sodium': tot_sodium,
                    'error': error
                })

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations:
            return "❌ 조건에 맞는 식단을 찾지 못했습니다. (예산/목표 조정 필요)"

        # 4. 파레토 최적화 및 결과 반환
        pareto_solutions = self.get_pareto_optimal_sets(valid_combinations)
        print(f"   🏆 파레토 최적해 도출: {len(pareto_solutions)}개")
        
        final_solutions = sorted(pareto_solutions, key=lambda x: x['price'])
        return final_solutions[:min(5, len(final_solutions))]

# -----------------------------------------------------
# 실행 테스트
# -----------------------------------------------------
if __name__ == "__main__":
    # 테스트 시나리오 설정
    USER_GOAL = "건강관리"  # 다이어트 / 건강관리 / 근육증가
    USER_CAL = 2200
    USER_PROT = 120
    MEALS = 3
    
    optimizer = DailyDietOptimizer()
    result = optimizer.recommend_daily_diet(
        target_cal=USER_CAL, target_prot=USER_PROT, meals_count=MEALS, user_goal=USER_GOAL
    )
    
    if isinstance(result, str):
        print(result)
    else:
        print("\n==================================================")
        print(f"🥗 [AI 추천 결과] {MEALS}끼 식단 (목표: {USER_GOAL})")
        print("==================================================")
        for i, res in enumerate(result):
            print(f"\n[옵션 {i+1}번 (파레토 최적)]")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  💪 단백질: {res['protein']:.0f}g")
            print(f"  🔥 칼로리: {res['calories']:.0f}kcal")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg")
            
            print("  --- 상세 식단 ---")
            for menu in res['combo']:
                print(f"    - [{menu['store_name']}] {menu['menu_name']} ({menu['price']:,}원)")
        print("==================================================")