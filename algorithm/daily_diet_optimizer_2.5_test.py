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

# -----------------------------------------------------------
# 🏷️ 식품 카테고리 분류기 (템플릿 생성용)
# -----------------------------------------------------------
class FoodCategorizer:
    def __init__(self):
        self.keywords = {
            'MAIN': ['도시락', '덮밥', '비빔밥', '볶음밥', '김밥', '주먹밥', '삼각김밥', '리조또', '국밥', '죽', 
                     '버거', '샌드위치', '토스트', '핫도그', '피자', '베이글', 
                     '라면', '우동', '국수', '파스타', '스파게티', '면', '짜장', '짬뽕'],
            'SIDE': ['샐러드', '닭가슴살', '치킨', '핫바', '소시지', '후랑크', '계란', '두부', '김치', '수프', '국', '찌개', '너겟', '감자', '스틱'],
            'DRINK': ['물', '워터', '아메리카노', '커피', '라떼', '우유', '두유', '유산균', '주스', '에이드', '콜라', '사이다', '티', '차', '음료', '비타'],
            'SNACK': ['과자', '칩', '쿠키', '빵', '케이크', '젤리', '초콜릿', '바', '아이스크림', '팝콘', '맛밤', '육포', '오징어']
        }
    def assign_category(self, item_name):
        name = item_name.replace(" ", "")
        for cat, kws in self.keywords.items():
            if any(kw in name for kw in kws): return cat
        return 'SIDE' # 분류 불가시 SIDE로 간주

# -----------------------------------------------------------
# 🧬 해밍 거리 기반 다양성 관리
# -----------------------------------------------------------
class DiversityManager:
    def __init__(self):
        self.cat_keys = ['MAIN', 'SIDE', 'DRINK', 'SNACK'] 

    def create_vector(self, item):
        """아이템의 category_tag를 기반으로 이진 벡터를 생성"""
        vector = []
        item_cat = item.get('category_tag', 'ETC')
        for cat in self.cat_keys:
            vector.append(1 if cat == item_cat else 0)
        return np.array(vector)

    def calculate_hamming_distance(self, vec1, vec2):
        return np.sum(np.abs(vec1 - vec2))

    def get_diversity_score(self, combo):
        """조합 내 아이템 간의 평균 해밍 거리 계산"""
        if len(combo) < 2: return 0.0
        vectors = [self.create_vector(item) for item in combo]
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                dist = self.calculate_hamming_distance(vectors[i], vectors[j])
                distances.append(dist)
        return np.mean(distances) if distances else 0.0


class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.5_test: Category + Hamming + Brand Set)...")
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다.")
        
        self.df = pd.read_csv(data_path)
        self.df = self.df[(self.df['price'] > 500) & (self.df['calories'] > 10)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = ""
        
        # 🏷️ 카테고리 태그 추가
        self.categorizer = FoodCategorizer()
        self.df['category_tag'] = self.df.apply(
            lambda x: self.categorizer.assign_category(x.get('menu_name', x.get('식품명', ''))), axis=1
        )
        
        self.menu_items = self.df.to_dict('records')
        
        # 브랜드별/카테고리별 그룹화
        self.brand_menu_map = {}
        for item in self.menu_items:
            brand = item.get('store_name', item.get('제조사명', 'Unknown'))
            cat = item['category_tag']
            
            if brand not in self.brand_menu_map:
                self.brand_menu_map[brand] = {c: [] for c in self.categorizer.keywords.keys()}
            
            self.brand_menu_map[brand][cat].append(item)
            
        # 🧬 다양성 매니저 초기화
        self.div_manager = DiversityManager()
            
        print(f"✅ 데이터 로드 및 분류 완료: 총 {len(self.df)}개")

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

    def calculate_nutritional_error(self, combo, target_cal, target_prot, target_fat, goal_ratios):
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        
        t_cal = max(target_cal, 1)
        t_prot = max(target_prot, 1)
        t_fat = max(target_fat, 1)
        
        cal_error = ((total_cal - t_cal) / t_cal) ** 2
        prot_error = ((total_prot - t_prot) / t_prot) ** 2
        
        fat_penalty = 0
        if total_fat > t_fat: fat_penalty = ((total_fat - t_fat) / t_fat) ** 2 * 2.0
        sodium_penalty = 0
        if total_sodium > SODIUM_MAX_LIMIT / 3: sodium_penalty = ((total_sodium - (SODIUM_MAX_LIMIT/3)) / (SODIUM_MAX_LIMIT/3)) ** 2
            
        error_score = np.sqrt(cal_error + prot_error + fat_penalty + sodium_penalty)
        
        # 하드 필터링 조건 (엄격 유지)
        is_protein_min_met = (total_prot >= target_prot * 0.95)
        is_cal_valid = (target_cal * 0.85 <= total_cal <= target_cal * 1.15)
        is_sodium_valid = (total_sodium <= SODIUM_MAX_LIMIT * 0.6) 
        
        return error_score, total_cal, total_prot, total_carbs, total_fat, total_sodium, is_sodium_valid, is_protein_min_met, is_cal_valid

    def get_pareto_optimal_sets(self, candidates):
        sorted_candidates = sorted(candidates, key=lambda x: x['price'])
        pareto_frontier = []
        min_error_so_far = float('inf')
        for candidate in sorted_candidates:
            if candidate['error'] < min_error_so_far:
                pareto_frontier.append(candidate)
                min_error_so_far = candidate['error']
        return sorted_candidates[:5] # 가격 최우선

    def recommend_daily_diet(self, target_cal, target_prot, target_fat, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=100000):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)

        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        valid_combinations = []
        
        for _ in range(num_simulations):
            selected_brand = random.choice(available_brands)
            brand_db = self.brand_menu_map[selected_brand]
            
            # 1. 템플릿 생성을 위한 카테고리별 후보 필터링
            mains = self.filter_by_allergens(brand_db.get('MAIN', []), allergies_to_avoid)
            sides = self.filter_by_allergens(brand_db.get('SIDE', []), allergies_to_avoid)
            drinks = self.filter_by_allergens(brand_db.get('DRINK', []), allergies_to_avoid)
            
            mains = [m for m in mains if m.get('FOOD_CODE') not in excluded_codes]
            sides = [s for s in sides if s.get('FOOD_CODE') not in excluded_codes]
            drinks = [d for d in drinks if d.get('FOOD_CODE') not in excluded_codes]
            
            if not mains: continue 

            # 2. 🍱 식사 템플릿 생성 (MAIN 필수)
            combo = [random.choice(mains)]
            
            if sides and random.random() < 0.6:
                combo.append(random.choice(sides))
                if len(sides) > 1 and random.random() < 0.3:
                    combo.append(random.choice(sides))
            
            if drinks and random.random() < 0.5:
                combo.append(random.choice(drinks))
            
            # 🧬 해밍 거리 체크 (다양성 제약)
            if len(combo) > 1:
                div_score = self.div_manager.get_diversity_score(combo)
                if div_score == 0.0: continue

            # 3. 영양 검증
            total_price = sum(item['price'] for item in combo)
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, is_sodium_valid, is_protein_min_met, is_cal_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, target_fat, goal_ratios
            )

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

        if not valid_combinations: return "❌ 조건 만족 식단 없음"

        pareto = self.get_pareto_optimal_sets(valid_combinations)
        final_sorted = sorted(pareto, key=lambda x: x['price'])
        
        return final_sorted

# -----------------------------------------------------
# 🧪 [테스트] 랜덤 유저 생성
# -----------------------------------------------------
class RandomUserGenerator:
    def __init__(self):
        self.goals = ["다이어트", "건강관리", "근육증가"]
        self.allergy_pool = ["난류", "땅콩", "우유", "대두", "밀", "새우", "복숭아"]
    def generate(self):
        weight = random.randint(45, 100)
        goal = random.choice(self.goals)
        activity_factor = random.uniform(1.2, 1.9)
        tdee = int(weight * 24 * activity_factor)
        target_cal = tdee
        if goal == "다이어트": target_cal = int(tdee * 0.85)
        elif goal == "근육증가": target_cal = int(tdee * 1.15)
        num_allergies = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        allergies = random.sample(self.allergy_pool, num_allergies)
        return {"weight": weight, "goal": goal, "target_cal": target_cal, "allergies": allergies}

if __name__ == "__main__":
    optimizer = DailyDietOptimizer()
    user_gen = RandomUserGenerator()
    NUM_USERS = 3
    
    for u_idx in range(NUM_USERS):
        user_profile = user_gen.generate()
        try:
            d_prot, d_carbs, d_fat = calculate_macro_grams(user_profile['target_cal'], user_profile['goal'])
        except: continue
            
        print(f"\n==================================================")
        print(f"👤 [User {u_idx+1}] 체중: {user_profile['weight']}kg | 목표: {user_profile['goal']}")
        print(f"   🎯 일일 타겟: {user_profile['target_cal']}kcal (P {d_prot}g / C {d_carbs}g / F {d_fat}g)")
        print("==================================================")
        
        MEALS_COUNT = 3
        current_status = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0, 'price': 0, 'sodium': 0}
        excluded_codes = set()
        excluded_brands = set()
        
        for i in range(MEALS_COUNT):
            remaining_meals = MEALS_COUNT - i
            
            target_cal = max((user_profile['target_cal'] - current_status['calories']) / remaining_meals, 100)
            target_prot = max((d_prot - current_status['protein']) / remaining_meals, 10)
            target_fat = max((d_fat - current_status['fat']) / remaining_meals, 5)
            
            meal_result = optimizer.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=excluded_brands 
            )
            
            if isinstance(meal_result, str):
                meal_result = optimizer.recommend_daily_diet(
                    target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                    user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                    excluded_codes=excluded_codes, excluded_brands=set()
                )

            if not isinstance(meal_result, str):
                best_combo = meal_result[0]
                
                current_status['calories'] += best_combo['calories']
                current_status['protein'] += best_combo['protein']
                current_status['fat'] += best_combo['fat']
                current_status['price'] += best_combo['price']
                current_status['sodium'] += best_combo['sodium']
                
                excluded_brands.add(best_combo['brand'])
                for item in best_combo['combo']:
                    if item.get('FOOD_CODE'): excluded_codes.add(item['FOOD_CODE'])
                
                print(f"   >>> Meal {i+1} [{best_combo['brand']}]: {len(best_combo['combo'])}개 ({best_combo['price']:,}원)")
                for menu in best_combo['combo']:
                    tag = menu.get('category_tag', 'ETC')
                    print(f"       [{tag}] {menu.get('menu_name', menu.get('식품명'))} (P:{menu['protein']}g)")
            else:
                print(f"   >>> Meal {i+1}: ❌ 추천 실패")

        print("\n   📊 [일일 합계]")
        print(f"   💸 총액: {current_status['price']:,}원")
        print(f"   🔥 열량: {current_status['calories']:.0f}kcal (달성률 {current_status['calories']/user_profile['target_cal']*100:.1f}%)")
        print(f"   💪 단백질: {current_status['protein']:.0f}g (달성률 {current_status['protein']/d_prot*100:.1f}%)")
        print(f"   🧂 나트륨: {current_status['sodium']:.0f}mg")
        print("\n")