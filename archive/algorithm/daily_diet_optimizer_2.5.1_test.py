import pandas as pd
import numpy as np
import random
import os
import sys
import time
import multiprocessing
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
# 클래스 정의 (FoodCategorizer, DiversityManager)
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
        return 'SIDE'

class DiversityManager:
    def __init__(self):
        self.cat_keys = ['MAIN', 'SIDE', 'DRINK', 'SNACK'] 
    def create_vector(self, item):
        vector = []
        item_cat = item.get('category_tag', 'ETC')
        for cat in self.cat_keys:
            vector.append(1 if cat == item_cat else 0)
        return np.array(vector)
    def calculate_hamming_distance(self, vec1, vec2):
        return np.sum(np.abs(vec1 - vec2))
    def get_diversity_score(self, combo):
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
        if not os.path.exists(data_path):
            data_path = 'final_nutrition_db.csv' 
            if not os.path.exists(data_path):
                data_path = os.path.join('data', 'processed', 'final_nutrition_db.csv')
            if not os.path.exists(data_path):
                raise FileNotFoundError(f"❌ 데이터 파일이 없습니다: {data_path}")
        
        self.df = pd.read_csv(data_path)
        self.df = self.df[(self.df['price'] > 500) & (self.df['calories'] > 10)]
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sodium', 'saturated_fat', 'sugars', 'price']
        for col in numeric_cols:
             self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        if 'allergens_scraped' in self.df.columns:
            self.df['allergens_scraped'] = self.df['allergens_scraped'].astype(str).str.lower()
        else:
            self.df['allergens_scraped'] = ""
        
        self.categorizer = FoodCategorizer()
        self.df['category_tag'] = self.df.apply(
            lambda x: self.categorizer.assign_category(x.get('menu_name', x.get('식품명', ''))), axis=1
        )
        
        self.menu_items = self.df.to_dict('records')
        self.brand_menu_map = {}
        for item in self.menu_items:
            brand = item.get('store_name', item.get('제조사명', 'Unknown'))
            cat = item['category_tag']
            if brand not in self.brand_menu_map:
                self.brand_menu_map[brand] = {c: [] for c in self.categorizer.keywords.keys()}
            self.brand_menu_map[brand][cat].append(item)
            
        self.div_manager = DiversityManager()

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

    def calculate_nutritional_error(self, combo, target_cal, target_prot, target_fat, goal_ratios, prot_min_factor=0.95, cal_range=0.15):
        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        
        t_cal = max(target_cal, 1)
        t_prot = max(target_prot, 1)
        # ❗ [수정] t_fat 정의 추가 (이전 코드에서 누락된 부분)
        t_fat = max(target_fat, 1) 
        
        cal_error = ((total_cal - t_cal) / t_cal) ** 2
        prot_error = ((total_prot - t_prot) / t_prot) ** 2
        
        fat_penalty = 0
        if total_fat > t_fat: fat_penalty = ((total_fat - t_fat) / t_fat) ** 2 * 2.0
        sodium_penalty = 0
        if total_sodium > SODIUM_MAX_LIMIT / 3: sodium_penalty = ((total_sodium - (SODIUM_MAX_LIMIT/3)) / (SODIUM_MAX_LIMIT/3)) ** 2
            
        error_score = np.sqrt(cal_error + prot_error + fat_penalty + sodium_penalty)
        
        is_protein_min_met = (total_prot >= target_prot * prot_min_factor)
        is_cal_valid = (target_cal * (1 - cal_range) <= total_cal <= target_cal * (1 + cal_range))
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
        return sorted_candidates[:5]

    def recommend_daily_diet(self, target_cal, target_prot, target_fat, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=20000, **kwargs):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        
        prot_min_factor = kwargs.get('prot_min_factor', 0.95)
        cal_range = kwargs.get('cal_range', 0.15)
        
        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        valid_combinations = []
        
        for _ in range(num_simulations):
            selected_brand = random.choice(available_brands)
            brand_db = self.brand_menu_map[selected_brand]
            
            mains = self.filter_by_allergens(brand_db.get('MAIN', []), allergies_to_avoid)
            sides = self.filter_by_allergens(brand_db.get('SIDE', []), allergies_to_avoid)
            drinks = self.filter_by_allergens(brand_db.get('DRINK', []), allergies_to_avoid)
            
            mains = [m for m in mains if m.get('FOOD_CODE') not in excluded_codes]
            sides = [s for s in sides if s.get('FOOD_CODE') not in excluded_codes]
            drinks = [d for d in drinks if d.get('FOOD_CODE') not in excluded_codes]
            
            if not mains: continue 

            # 식사 템플릿
            combo = [random.choice(mains)]
            if sides and random.random() < 0.6:
                combo.append(random.choice(sides))
                if len(sides) > 1 and random.random() < 0.3:
                    combo.append(random.choice(sides))
            if drinks and random.random() < 0.5:
                combo.append(random.choice(drinks))
            
            # 해밍 거리
            div_score = 0
            if len(combo) > 1:
                div_score = self.div_manager.get_diversity_score(combo)
                if div_score == 0.0: continue

            # 영양 검증
            total_price = sum(item['price'] for item in combo)
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, is_sodium_valid, is_protein_min_met, is_cal_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, target_fat, dict(), prot_min_factor, cal_range
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
                    'error': error,
                    'diversity_score': div_score
                })

        if not valid_combinations: return "❌ 조건 만족 식단 없음"

        pareto = self.get_pareto_optimal_sets(valid_combinations)
        final_sorted = sorted(pareto, key=lambda x: x['price'])
        
        return final_sorted

# -----------------------------------------------------
# 전역 변수 (Worker Process용)
# -----------------------------------------------------
optimizer_instance = None

def init_worker():
    global optimizer_instance
    optimizer_instance = DailyDietOptimizer()

def run_single_simulation(user_profile):
    """단일 유저에 대한 3끼 시뮬레이션 실행 (Worker가 처리)"""
    global optimizer_instance
    
    try:
        d_prot, d_carbs, d_fat = calculate_macro_grams(user_profile['target_cal'], user_profile['goal'])
    except:
        return {"success": False, "reason": "Target Calc Error"}

    MEALS_COUNT = 3
    current_status = {'calories': 0, 'protein': 0, 'fat': 0, 'price': 0, 'diversity_sum': 0}
    excluded_codes = set()
    excluded_brands = set()
    
    result_log = []
    
    for i in range(MEALS_COUNT):
        remaining_meals = MEALS_COUNT - i
        
        target_cal = max((user_profile['target_cal'] - current_status['calories']) / remaining_meals, 100)
        target_prot = max((d_prot - current_status['protein']) / remaining_meals, 10)
        target_fat = max((d_fat - current_status['fat']) / remaining_meals, 5)
        
        # 1차 시도
        meal_result = optimizer_instance.recommend_daily_diet(
            target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
            user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
            excluded_codes=excluded_codes, excluded_brands=excluded_brands 
        )
        
        # 2차 시도 (브랜드 제약 해제)
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=set(),
                prot_min_factor=0.90, cal_range=0.20
            )

        if not isinstance(meal_result, str):
            best_combo = meal_result[0]
            
            current_status['calories'] += best_combo['calories']
            current_status['protein'] += best_combo['protein']
            current_status['fat'] += best_combo['fat']
            current_status['price'] += best_combo['price']
            
            current_status['diversity_sum'] += best_combo.get('diversity_score', 0)
            
            excluded_brands.add(best_combo['brand'])
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'): excluded_codes.add(item['FOOD_CODE'])
            
            result_log.append(best_combo)
        else:
            return {"success": False, "reason": f"Meal {i+1} Failed"}

    return {
        "success": True,
        "price": current_status['price'],
        "calories": current_status['calories'],
        "protein": current_status['protein'],
        "avg_diversity": current_status['diversity_sum'] / MEALS_COUNT,
        "target_cal": user_profile['target_cal'],
        "target_prot": d_prot,
        "results": result_log, 
        "user_profile": user_profile
    }

class RandomUserGenerator:
    def __init__(self):
        self.goals = ["다이어트", "건강관리", "근육증가"]
        self.allergy_pool = ["난류", "땅콩", "우유", "대두", "밀", "새우", "복숭아"]
    def generate(self):
        weight = random.randint(45, 100)
        gender = random.choice(['Male', 'Female'])
        goal = random.choice(self.goals)
        activity_factor = random.uniform(1.2, 1.9)
        gender_factor = 1.05 if gender == 'Male' else 0.95 
        tdee = int(weight * 24 * activity_factor * gender_factor)
        target_cal = tdee
        if goal == "다이어트": target_cal = int(tdee * 0.85)
        elif goal == "근육증가": target_cal = int(tdee * 1.15)
        num_allergies = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        allergies = random.sample(self.allergy_pool, num_allergies)
        return {"weight": weight, "gender": gender, "goal": goal, "target_cal": target_cal, "allergies": allergies}

if __name__ == "__main__":
    
    multiprocessing.freeze_support()
    
    NUM_USERS = 100 
    user_gen = RandomUserGenerator()
    users = [user_gen.generate() for _ in range(NUM_USERS)]
    
    CORES_TO_USE = 4
    
    print(f"\n🚀 [Parallel] {NUM_USERS}명 시뮬레이션 시작 (CPU Cores: {CORES_TO_USE})")
    print("--------------------------------------------------")
    
    start_time = time.time()
    
    with multiprocessing.Pool(processes=CORES_TO_USE, initializer=init_worker) as pool:
        results = pool.map(run_single_simulation, users)
        
    end_time = time.time()
    
    success_results = [res for res in results if res['success']]
    success_cnt = len(success_results)
    fail_cnt = NUM_USERS - success_cnt
    
    total_price = 0
    cal_acc_sum = 0
    prot_acc_sum = 0
    diversity_sum = 0
    
    for res in success_results:
        total_price += res['price']
        cal_acc = abs(res['calories'] - res['target_cal']) / res['target_cal']
        prot_acc = abs(res['protein'] - res['target_prot']) / res['target_prot']
        
        cal_acc_sum += (1 - cal_acc)
        prot_acc_sum += (1 - prot_acc)
        diversity_sum += res['avg_diversity']
            
    success_rate = (success_cnt / NUM_USERS) * 100
    avg_price = total_price / success_cnt if success_cnt > 0 else 0
    avg_cal_acc = (cal_acc_sum / success_cnt) * 100 if success_cnt > 0 else 0
    avg_prot_acc = (prot_acc_sum / success_cnt) * 100 if success_cnt > 0 else 0
    avg_diversity = diversity_sum / success_cnt if success_cnt > 0 else 0
    
    print("\n==================================================")
    print(f"📊 [v2.5.1] 성능 평가 리포트 ({NUM_USERS}명)")
    print("==================================================")
    print(f"⏱️ 총 소요 시간: {end_time - start_time:.2f}초")
    print(f"✅ 성공 횟수: {success_cnt}명 ({success_rate:.1f}%)")
    print(f"❌ 실패 횟수: {fail_cnt}명")
    print("--------------------------------------------------")
    print(f"💰 평균 식단 가격: {avg_price:,.0f}원")
    print(f"🔥 평균 칼로리 정확도: {avg_cal_acc:.1f}%")
    print(f"💪 평균 단백질 정확도: {avg_prot_acc:.1f}%")
    print(f"🌈 평균 다양성 점수 (Hamming): {avg_diversity:.2f}")
    print("==================================================")

    if success_cnt > 0:
        sample_size = min(10, success_cnt)
        random_samples = random.sample(success_results, sample_size)
        
        print(f"\n🎲 랜덤 샘플 {sample_size}명 상세 출력")
        print("==================================================")
        
        for idx, sample in enumerate(random_samples):
            u = sample['user_profile']
            print(f"\n[Sample {idx+1}] {u['weight']}kg | {u['gender']} | {u['goal']} | Target: {u['target_cal']}kcal (P {int(sample['target_prot'])}g)")
            
            for m_idx, meal in enumerate(sample['results']):
                print(f"   🥣 Meal {m_idx+1} [{meal['brand']}] ({len(meal['combo'])}개, {meal['calories']:.0f}kcal)")
                for item in meal['combo']:
                    tag = item.get('category_tag', 'ETC')
                    print(f"       [{tag}] {item.get('menu_name', item.get('식품명'))}")
            
            print(f"   👉 Total: {sample['price']:,}원 | {sample['calories']:.0f}kcal | P {sample['protein']:.0f}g | Div {sample['avg_diversity']:.2f}")