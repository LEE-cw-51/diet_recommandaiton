"""
식단 추천 알고리즘 프로토타입 v1.0
- 선형 계획법(Linear Programming) 기반
- Google OR-Tools 사용
- 예산 기반 + 영양 최적화 + 같은 브랜드 제약
"""

import pandas as pd
import numpy as np
from ortools.linear_solver import pywraplp
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class MealRecommendationEngine:
    """
    식단 추천 엔진
    
    주요 기능:
    1. 사용자 목표별 영양소 기준 설정
    2. 선형 계획법으로 최적 조합 탐색
    3. 결과 검증 및 분석
    """
    
    def __init__(self, db_path: str):
        """
        초기화
        
        Args:
            db_path: 영양 DB 경로 (CSV)
        """
        self.df = pd.read_csv(db_path)
        self._preprocess_data()
        
        # 목표별 칼로리 기준
        self.calorie_targets = {
            '다이어트': 1800,
            '균형': 2000,
            '벌크업': 2200
        }
        
        # 목표별 단백질 최소 기준 (g)
        self.protein_minimums = {
            '다이어트': 25,
            '균형': 20,
            '벌크업': 35
        }
        
        # 제약조건
        self.SODIUM_LIMIT = 2000  # mg
        self.CALORIE_TOLERANCE = 0.1  # ±10%
        self.MAX_ITEMS = 4  # 최대 4개 메뉴
        self.MIN_ITEMS = 2  # 최소 2개 메뉴
    
    def _preprocess_data(self):
        """
        데이터 전처리
        1. 결측치 제거
        2. 영양 데이터 정제
        """
        # 필수 컬럼 확인
        required_cols = ['price', '에너지(kcal)', '단백질(g)', '탄수화물(g)', '지방(g)', '나트륨(mg)']
        
        # 필수 컬럼이 모두 있는 행만 유지
        self.df = self.df.dropna(subset=required_cols)
        
        # 칼로리가 0인 행 제거 (오류 데이터)
        self.df = self.df[self.df['에너지(kcal)'] > 0]
        
        # 가격이 0 이하인 행 제거
        self.df = self.df[self.df['price'] > 0]
        
        print(f"✅ 데이터 전처리 완료")
        print(f"   총 {len(self.df)}개 상품 (결측치 제거 후)")
    
    def get_available_brands(self) -> List[str]:
        """이용 가능한 브랜드 목록 반환"""
        return sorted(self.df['brand_name'].unique().tolist())
    
    def recommend(self, 
                  budget: int, 
                  goal: str, 
                  brand: str) -> Optional[Dict]:
        """
        식단 추천 메인 함수
        
        Args:
            budget: 예산 (원)
            goal: 목표 ('다이어트' / '균형' / '벌크업')
            brand: 브랜드명 (예: 'GS25', 'CU' 등)
        
        Returns:
            추천 결과 딕셔너리 또는 None (해 없음)
        """
        
        # 입력 검증
        if goal not in self.calorie_targets:
            print(f"❌ 목표 오류: {goal}은(는) 지원하지 않습니다.")
            print(f"   가능한 목표: {list(self.calorie_targets.keys())}")
            return None
        
        if brand not in self.get_available_brands():
            print(f"❌ 브랜드 오류: {brand}은(는) DB에 없습니다.")
            print(f"   가능한 브랜드: {self.get_available_brands()}")
            return None
        
        if budget <= 0:
            print(f"❌ 예산 오류: {budget}원은 유효하지 않습니다.")
            return None
        
        print(f"\n{'='*80}")
        print(f"🍽️  식단 추천 시작")
        print(f"{'='*80}")
        print(f"📍 조건: {brand} | 예산 {budget:,}원 | 목표 {goal}")
        print(f"{'='*80}\n")
        
        # 해당 브랜드 상품만 필터링
        brand_df = self.df[self.df['brand_name'] == brand].reset_index(drop=True)
        
        if len(brand_df) == 0:
            print(f"❌ {brand}에서 상품을 찾을 수 없습니다.")
            return None
        
        # 목표에 따른 기준 설정
        target_calorie = self.calorie_targets[goal]
        min_protein = self.protein_minimums[goal]
        calorie_range = (
            target_calorie * (1 - self.CALORIE_TOLERANCE),
            target_calorie * (1 + self.CALORIE_TOLERANCE)
        )
        
        print(f"🎯 영양 기준:")
        print(f"   칼로리: {calorie_range[0]:.0f} ~ {calorie_range[1]:.0f} kcal")
        print(f"   단백질: ≥ {min_protein}g")
        print(f"   나트륨: ≤ {self.SODIUM_LIMIT}mg")
        print(f"   가격: ≤ {budget:,}원\n")
        
        # 선형 계획법 실행
        result = self._solve_with_linear_programming(
            brand_df, 
            budget, 
            calorie_range, 
            min_protein,
            goal
        )
        
        return result
    
    def _solve_with_linear_programming(self,
                                       brand_df: pd.DataFrame,
                                       budget: int,
                                       calorie_range: Tuple[float, float],
                                       min_protein: float,
                                       goal: str) -> Optional[Dict]:
        """
        선형 계획법으로 최적 조합 탐색
        
        목적함수: 영양 만족도 최대화
        제약조건:
        - 가격 ≤ 예산
        - 칼로리 범위 내
        - 나트륨 ≤ 2000mg
        - 단백질 ≥ 기준
        - 2~4개 메뉴 선택
        """
        
        # 솔버 생성
        solver = pywraplp.Solver.CreateSolver('GLOP')
        if not solver:
            print("❌ 솔버 생성 실패")
            return None
        
        n = len(brand_df)
        
        # 의사결정 변수: x_i (각 상품의 선택 여부, 0 또는 1)
        x = [solver.IntVar(0, 1, f'item_{i}') for i in range(n)]
        
        # ============ 제약조건 ============
        
        # 1. 가격 제약: Σ(price_i * x_i) ≤ budget
        price_constraint = solver.Constraint(0, float(budget), 'price_limit')
        for i in range(n):
            price_constraint.SetCoefficient(x[i], float(brand_df.iloc[i]['price']))
        
        # 2. 칼로리 범위 제약: calorie_min ≤ Σ(cal_i * x_i) ≤ calorie_max
        calorie_constraint_min = solver.Constraint(calorie_range[0], float('inf'), 'calorie_min')
        calorie_constraint_max = solver.Constraint(0, calorie_range[1], 'calorie_max')
        for i in range(n):
            cal = float(brand_df.iloc[i]['에너지(kcal)'])
            calorie_constraint_min.SetCoefficient(x[i], cal)
            calorie_constraint_max.SetCoefficient(x[i], cal)
        
        # 3. 나트륨 제약: Σ(sodium_i * x_i) ≤ SODIUM_LIMIT
        sodium_constraint = solver.Constraint(0, float(self.SODIUM_LIMIT), 'sodium_limit')
        for i in range(n):
            sodium_constraint.SetCoefficient(x[i], float(brand_df.iloc[i]['나트륨(mg)']))
        
        # 4. 단백질 제약: Σ(protein_i * x_i) ≥ min_protein
        protein_constraint = solver.Constraint(float(min_protein), float('inf'), 'protein_min')
        for i in range(n):
            protein_constraint.SetCoefficient(x[i], float(brand_df.iloc[i]['단백질(g)']))
        
        # 5. 메뉴 개수 제약: MIN_ITEMS ≤ Σ(x_i) ≤ MAX_ITEMS
        count_constraint_min = solver.Constraint(self.MIN_ITEMS, float('inf'), 'min_items')
        count_constraint_max = solver.Constraint(0, self.MAX_ITEMS, 'max_items')
        for i in range(n):
            count_constraint_min.SetCoefficient(x[i], 1)
            count_constraint_max.SetCoefficient(x[i], 1)
        
        # ============ 목적함수 ============
        
        objective = solver.Objective()
        
        for i in range(n):
            row = brand_df.iloc[i]
            protein = float(row['단백질(g)'])
            carb = float(row['탄수화물(g)'])
            fat = float(row['지방(g)'])
            cal = float(row['에너지(kcal)'])
            price = float(row['price'])
            
            # 영양 스코어 계산 (가중치는 나중에 튜닝)
            # 기본 가중치:
            # - 단백질 효율 (가격당 단백질): 높을수록 좋음
            # - 칼로리 효율 (가격당 칼로리): 합리적 범위가 좋음
            # - 나트륨 효율 (낮을수록 좋음)
            
            protein_efficiency = protein / price if price > 0 else 0  # g/원
            calorie_efficiency = cal / price if price > 0 else 0      # kcal/원
            sodium_penalty = 1 / (1 + float(row['나트륨(mg)']) / 100)         # 정규화된 페널티
            
            # 목표에 따른 가중치 조정
            if goal == '다이어트':
                # 단백질 효율을 가장 중시
                score = (protein_efficiency * 5 + 
                        calorie_efficiency * 2 + 
                        sodium_penalty * 1)
            elif goal == '균형':
                # 균형잡힌 영양
                score = (protein_efficiency * 3 + 
                        calorie_efficiency * 3 + 
                        sodium_penalty * 1)
            else:  # 벌크업
                # 칼로리와 단백질 모두 중시
                score = (protein_efficiency * 4 + 
                        calorie_efficiency * 4 + 
                        sodium_penalty * 0.5)
            
            objective.SetCoefficient(x[i], float(score))
        
        # 목적함수 최대화
        objective.SetMaximization()
        
        # ============ 솔버 실행 ============
        
        status = solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL:
            print("✅ 최적해 찾음!\n")
            return self._format_result(brand_df, x, solver, goal)
        
        elif status == pywraplp.Solver.FEASIBLE:
            print("⚠️  실행 가능한 해 찾음 (최적해 아님)\n")
            return self._format_result(brand_df, x, solver, goal)
        
        else:
            print("❌ 해를 찾을 수 없습니다.")
            print(f"   상태 코드: {status}")
            print("\n💡 문제 해결 방법:")
            print("   1. 예산을 늘려보세요")
            print("   2. 목표를 변경해보세요 (다이어트 → 균형)")
            print("   3. 다른 브랜드를 시도해보세요")
            return None
    
    def _format_result(self, 
                       brand_df: pd.DataFrame, 
                       x: List, 
                       solver,
                       goal: str) -> Dict:
        """
        결과 포맷팅 및 검증
        """
        
        selected_indices = [i for i in range(len(x)) if x[i].solution_value() > 0.5]
        selected_items = brand_df.iloc[selected_indices].reset_index(drop=True)
        
        # 영양 정보 계산
        total_price = selected_items['price'].sum()
        total_calories = selected_items['에너지(kcal)'].sum()
        total_protein = selected_items['단백질(g)'].sum()
        total_carb = selected_items['탄수화물(g)'].sum()
        total_fat = selected_items['지방(g)'].sum()
        total_sodium = selected_items['나트륨(mg)'].sum()
        
        # 영양소 비율 (칼로리 기준)
        protein_ratio = (total_protein * 4) / total_calories * 100 if total_calories > 0 else 0
        carb_ratio = (total_carb * 4) / total_calories * 100 if total_calories > 0 else 0
        fat_ratio = (total_fat * 9) / total_calories * 100 if total_calories > 0 else 0
        
        # 검증
        target_cal = self.calorie_targets[goal]
        cal_tolerance = target_cal * self.CALORIE_TOLERANCE
        cal_check = abs(total_calories - target_cal) <= cal_tolerance
        
        price_check = total_price <= self.recommendations_budget  # 나중에 사용할 변수
        protein_check = total_protein >= self.protein_minimums[goal]
        sodium_check = total_sodium <= self.SODIUM_LIMIT
        
        result = {
            'status': 'success',
            'goal': goal,
            'items': selected_items[['cleaned_item_name', 'price', '에너지(kcal)', 
                                     '단백질(g)', '탄수화물(g)', '지방(g)', '나트륨(mg)']].to_dict('records'),
            'summary': {
                'total_price': total_price,
                'total_calories': round(total_calories, 1),
                'total_protein': round(total_protein, 1),
                'total_carb': round(total_carb, 1),
                'total_fat': round(total_fat, 1),
                'total_sodium': round(total_sodium, 1),
                'item_count': len(selected_items)
            },
            'macros': {
                'protein_ratio': round(protein_ratio, 1),
                'carb_ratio': round(carb_ratio, 1),
                'fat_ratio': round(fat_ratio, 1)
            },
            'validation': {
                'price_valid': price_check,
                'calories_valid': cal_check,
                'protein_valid': protein_check,
                'sodium_valid': sodium_check,
                'all_valid': price_check and cal_check and protein_check and sodium_check
            }
        }
        
        self._print_result(result)
        
        return result
    
    def _print_result(self, result: Dict):
        """
        결과 출력 (보기 좋게)
        """
        
        print(f"{'='*80}")
        print(f"🎯 추천 결과")
        print(f"{'='*80}\n")
        
        print(f"📋 추천 메뉴 ({result['summary']['item_count']}개):")
        print(f"{'-'*80}")
        for i, item in enumerate(result['items'], 1):
            print(f"{i}. {item['cleaned_item_name']}")
            print(f"   가격: {item['price']:,}원 | 칼로리: {item['에너지(kcal)']:.0f}kcal | "
                  f"단백질: {item['단백질(g)']:.1f}g")
        
        print(f"\n{'-'*80}")
        print(f"💰 총 가격: {result['summary']['total_price']:,}원")
        print(f"🔥 총 칼로리: {result['summary']['total_calories']:.0f} kcal "
              f"({'✅' if result['validation']['calories_valid'] else '❌'})")
        print(f"💪 총 단백질: {result['summary']['total_protein']:.1f}g "
              f"({'✅' if result['validation']['protein_valid'] else '❌'})")
        print(f"🧂 총 나트륨: {result['summary']['total_sodium']:.0f}mg "
              f"({'✅' if result['validation']['sodium_valid'] else '❌'})")
        
        print(f"\n📊 영양소 비율 (칼로리 기준):")
        print(f"   탄수화물: {result['macros']['carb_ratio']:.1f}%")
        print(f"   단백질: {result['macros']['protein_ratio']:.1f}%")
        print(f"   지방: {result['macros']['fat_ratio']:.1f}%")
        
        print(f"\n{'='*80}\n")
        
        if not result['validation']['all_valid']:
            print(f"⚠️  일부 제약조건 미충족:")
            if not result['validation']['calories_valid']:
                print(f"   - 칼로리 범위 벗어남")
            if not result['validation']['protein_valid']:
                print(f"   - 단백질 기준 미달")
            if not result['validation']['sodium_valid']:
                print(f"   - 나트륨 초과")
            print()


# ============ 테스트 코드 ============

def main():
    """
    테스트 메인 함수
    """
    
    # 엔진 초기화
    engine = MealRecommendationEngine('data/processed/matched_nutrition_db.csv')
    
    print(f"\n📚 이용 가능한 브랜드:")
    print(f"   {', '.join(engine.get_available_brands())}\n")
    
    # 테스트 케이스 1: GS25, 다이어트, 7,000원
    print("\n" + "="*80)
    print("TEST CASE 1: GS25 | 다이어트 | 7,000원")
    print("="*80)
    engine.recommendations_budget = 7000  # 나중에 검증용
    result1 = engine.recommend(budget=7000, goal='다이어트', brand='GS25')
    
    # 테스트 케이스 2: CU, 균형, 8,000원
    print("\n" + "="*80)
    print("TEST CASE 2: CU | 균형 | 8,000원")
    print("="*80)
    engine.recommendations_budget = 8000
    result2 = engine.recommend(budget=8000, goal='균형', brand='CU')
    
    # 테스트 케이스 3: 맥도날드, 벌크업, 12,000원
    print("\n" + "="*80)
    print("TEST CASE 3: 맥도날드 | 벌크업 | 12,000원")
    print("="*80)
    engine.recommendations_budget = 12000
    result3 = engine.recommend(budget=12000, goal='벌크업', brand='맥도날드')
    
    # 테스트 케이스 4: 불가능한 케이스 (예산 너무 적음)
    print("\n" + "="*80)
    print("TEST CASE 4: GS25 | 다이어트 | 1,000원 (불가능한 케이스)")
    print("="*80)
    engine.recommendations_budget = 1000
    result4 = engine.recommend(budget=1000, goal='다이어트', brand='GS25')


if __name__ == '__main__':
    main()