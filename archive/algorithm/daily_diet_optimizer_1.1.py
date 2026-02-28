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
MACRO_GOAL_RATIOS = {
    "다이어트": {
        'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25) # 탄40:단40:지20 목표 (±5% 허용)
    },
    "건강관리": {
        'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25) # 탄50:단30:지20 목표 (±5% 허용)
    },
    "근육증가": {
        'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25) # 탄40:단40:지20 목표 (±5% 허용)
    }
}

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"❌ 데이터 파일이 없습니다: {data_path}")
        
        self.df = pd.read_csv(data_path)
        
        # 데이터 클리닝 및 필터링
        self.df = self.df[(self.df['price'] > 1500) & (self.df['calories'] > 50)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        self.menu_items = self.df.to_dict('records')
        print(f"✅ 데이터 로드 완료: {len(self.df)}개 유효 메뉴 로드됨")

    def calculate_nutritional_error(self, combo, target_cal, target_prot, goal_ratios):
        """식단 조합의 영양소 오차(RMSE) 및 제약 조건(비율, 나트륨) 검증"""
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sat_fat = sum(item['saturated_fat'] for item in combo) # 포화지방 추가
        total_sugars = sum(item['sugars'] for item in combo) # 당류 추가
        
        # 1. 목표 달성도 오차 계산 (RMSE 방식)
        cal_error = ((total_cal - target_cal) / target_cal) ** 2
        prot_error = ((total_prot - target_prot) / target_prot) ** 2
        error_score = np.sqrt(cal_error + prot_error)
        
        # 2. EER 비율 계산 및 준수 여부 검사
        macro_sum_cal = (total_carbs * ATWATER_C) + (total_prot * ATWATER_P) + (total_fat * ATWATER_F)
        
        is_ratio_valid = False
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT)

        if macro_sum_cal > 0:
            P_perc = (total_prot * ATWATER_P) / macro_sum_cal
            C_perc = (total_carbs * ATWATER_C) / macro_sum_cal
            F_perc = (total_fat * ATWATER_F) / macro_sum_cal
            
            # 사용자 목표 비율 범위 내에 있는지 확인
            is_ratio_valid = (goal_ratios['C'][0] <= C_perc <= goal_ratios['C'][1]) and \
                             (goal_ratios['P'][0] <= P_perc <= goal_ratios['P'][1]) and \
                             (goal_ratios['F'][0] <= F_perc <= goal_ratios['F'][1])

        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, total_sat_fat, total_sugars, is_ratio_valid, is_sodium_valid

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

    def get_priority_focus(self, solution, top_solutions):
        """각 옵션의 최적화된 특징을 레이블로 부여합니다."""
        
        # 1. 최저 비용 체크
        if solution['price'] == min(s['price'] for s in top_solutions):
            return "🥇 최저 비용"
        
        # 2. 최저 나트륨 체크
        if solution['sodium'] == min(s['sodium'] for s in top_solutions):
            return "🌱 최저 나트륨"

        # 3. 최고 단백질 체크
        if solution['protein'] == max(s['protein'] for s in top_solutions):
            return "💪 최고 단백질"
        
        # 4. 목표 정확도 체크 (오차가 가장 적은 경우)
        if solution['error'] == min(s['error'] for s in top_solutions):
            return "🎯 목표 정확도 최우선"
            
        # 5. 최저 포화지방 체크
        if solution['saturated_fat'] == min(s['saturated_fat'] for s in top_solutions):
            return "❤️ 최저 포화지방"
            
        return "💡 균형 조합"

    def recommend_daily_diet(self, target_cal, target_prot, user_goal, meals_count=3, num_simulations=100000):
        
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        if not goal_ratios:
            raise ValueError(f"❌ 잘못된 목표입니다. ({list(MACRO_GOAL_RATIOS.keys())} 중 선택)")

        print(f"🔄 시뮬레이션 시작: 목표='{user_goal}', {meals_count}끼 식사 (나트륨제한 적용)")

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

            # 1차 필터링: (1) 목표 근접성 & (2) EER 준수 & (3) 나트륨 준수
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

        print(f"   ✅ 조건 만족 조합 발견: {len(valid_combinations)}개")

        if not valid_combinations:
            return "❌ 조건에 맞는 식단을 찾지 못했습니다. (예산/목표 조정 필요)"

        # 4. 파레토 최적화 및 결과 반환
        pareto_solutions = self.get_pareto_optimal_sets(valid_combinations)
        
        print(f"   🏆 파레토 최적해 도출: {len(pareto_solutions)}개")
        
        final_solutions = sorted(pareto_solutions, key=lambda x: x['price'])
        top_k_solutions = final_solutions[:min(5, len(final_solutions))]
        
        return top_k_solutions

# -----------------------------------------------------
# 실행 테스트
# -----------------------------------------------------
if __name__ == "__main__":
    # 테스트 시나리오 설정
    USER_GOAL = "다이어트"  # 다이어트 / 건강관리 / 근육증가
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
        print(f"🥗 [AI 추천 결과] {MEALS}끼 식단 (목표: {USER_GOAL})")
        print("==================================================")
        
        # 우선순위 레이블 부여를 위해 Top K 결과만 따로 전달
        top_k_results = result
        
        for i, res in enumerate(top_k_results):
            # 우선순위 레이블 부여
            priority_label = optimizer.get_priority_focus(res, top_k_results)
            
            print(f"\n[옵션 {i+1}번] {priority_label}")
            print(f"  💸 총 가격: {res['price']:,}원")
            print(f"  🔥 칼로리: {res['calories']:.0f}kcal")
            
            # EER 비율 검증 출력
            macro_sum_cal = (res['carbs'] * ATWATER_C) + (res['protein'] * ATWATER_P) + (res['fat'] * ATWATER_F)
            
            print(f"  --- 영양 상세 ---")
            print(f"  💪 단백질: {res['protein']:.0f}g (EER: {res['protein']*ATWATER_P/macro_sum_cal*100:.1f}%)")
            print(f"  🍚 탄수화물: {res['carbs']:.0f}g (EER: {res['carbs']*ATWATER_C/macro_sum_cal*100:.1f}%)")
            print(f"  🥓 지방: {res['fat']:.0f}g (EER: {res['fat']*ATWATER_F/macro_sum_cal*100:.1f}%)")
            print(f"  🧂 나트륨: {res['sodium']:.0f}mg (포화지방: {res['saturated_fat']:.1f}g | 당류: {res['sugars']:.0f}g)")
            
            print("  --- 상세 식단 ---")
            for menu in res['combo']:
                print(f"    - [{menu['store_name']}] {menu['menu_name']} ({menu['price']:,}원)")
        print("==================================================")