import pandas as pd
import numpy as np
import random
import os
import sys
import time
import multiprocessing
import matplotlib.pyplot as plt 
import matplotlib.font_manager as fm
from collections import Counter

# [v2.9.6] NSGA-II 라이브러리 임포트
try:
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.operators.crossover.sbx import SBX
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import IntegerRandomSampling
    from pymoo.operators.crossover.pntx import PointCrossover
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination
except ImportError:
    print("❌ 'pymoo' 라이브러리가 없습니다. 'pip install pymoo'를 실행해주세요.")
    sys.exit()

# -----------------------------------------------------------
# [설정] 차트 한글 폰트 깨짐 방지
# -----------------------------------------------------------
try:
    plt.rcParams['font.family'] = 'Malgun Gothic' 
except:
    pass
plt.rcParams['axes.unicode_minus'] = False

# -----------------------------------------------------------
# [제약 조건 상수 설정]
# -----------------------------------------------------------
ATWATER_P = 4
ATWATER_C = 4
ATWATER_F = 9
SODIUM_MAX_LIMIT = 2500
SUGAR_RATIOS = {"다이어트": 0.05, "건강관리": 0.10, "근육증가": 0.10}
MACRO_GOAL_RATIOS = {
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)},
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

# [v2.9.6] 목적 함수별 가중치 (단백질 오차, 탄수화물 오차, 지방 오차, 가격, 다양성)
OBJECTIVE_WEIGHTS = np.array([1.0, 1.0, 1.0, 1.0, 1.0]) 
# Meal당 제시할 대안의 개수
NUM_ALTERNATIVES = 3 
# NSGA-II를 실행할 브랜드 샘플 개수
NUM_BRAND_SAMPLES = 5 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

# TDEE 계산을 위한 활동 계수
ACTIVITY_FACTORS = {
    "거의 활동 없음": 1.2,
    "가벼운 활동": 1.375,
    "보통 활동": 1.55,
    "매우 활동적": 1.725,
    "극한 활동": 1.9
}

def calculate_bmr_tdee(gender, weight, height, age, activity_level):
    """미플린-산 제어 공식 기반 BMR/TDEE 계산"""
    if gender == 'Male':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else: # Female
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    factor = ACTIVITY_FACTORS.get(activity_level, 1.375)
    tdee = int(bmr * factor)
    return tdee

def calculate_macro_grams(target_cal, user_goal, weight):
    protein_factors = {"다이어트": 2.0, "건강관리": 1.2, "근육증가": 1.6}
    factor = protein_factors.get(user_goal, 1.2)
    target_prot = round(weight * factor)
    
    prot_cal = target_prot * ATWATER_P
    remaining_cal = target_cal - prot_cal
    
    if remaining_cal <= 0: return target_prot, 0, 0
    
    avg_ratios = {
        "다이어트": {'C': 0.375, 'F': 0.225},
        "건강관리": {'C': 0.50, 'F': 0.20},
        "근육증가": {'C': 0.40, 'F': 0.20}
    }
    C_prop = avg_ratios[user_goal]['C']
    F_prop = avg_ratios[user_goal]['F']
    total_CF_prop = C_prop + F_prop
    
    target_carbs_cal = remaining_cal * (C_prop / total_CF_prop)
    target_fat_cal = remaining_cal * (F_prop / total_CF_prop)
    
    return target_prot, round(target_carbs_cal / ATWATER_C), round(target_fat_cal / ATWATER_F)

# -----------------------------------------------------------
# 클래스 정의
# -----------------------------------------------------------
class FoodCategorizer:
    def __init__(self):
        self.keywords = {
            'MAIN': ['도시락', '덮밥', '비빔밥', '볶음밥', '김밥', '주먹밥', '삼각김밥', '리조또', '국밥', '죽',
                     '버거', '샌드위치', '토스트', '핫도그', '피자', '베이글', '국수', '파스타', '스파게티', '면', '짜장'],
            'SOUP': ['국', '찌개', '탕', '라면', '우동', '짬뽕', '수프', '곰탕', '설렁탕', '순대국', '감자탕'],
            'SIDE': ['샐러드', '닭가슴살', '치킨', '핫바', '소시지', '후랑크', '계란', '두부', '김치', '너겟', '감자', '스틱'],
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
        self.name_features = [
            '닭', '치킨', '가슴살', '돼지', '돈까스', '햄', '베이컨', '소시지', '핫바', '후랑크',
            '소', '비프', '불고기', '스테이크', '새우', '오징어', '해물', '생선', '명란',
            '면', '파스타', '국수', '우동', '스파게티', '짜장', '짬뽕',
            '밥', '라이스', '덮밥', '비빔밥', '볶음밥', '국밥', '죽', '리조또',
            '빵', '버거', '샌드위치', '토스트', '베이글', '피자', '핫도그',
            '매운', '핫', '스파이시'
        ]
        self.allergy_features = ['난류', '알류', '계란', '우유', '땅콩', '견과', '복숭아', '토마토', '밀', '대두']
        self.cat_keys = ['MAIN', 'SOUP', 'SIDE', 'DRINK', 'SNACK']

    def create_vector(self, item):
        vector = []
        name = item.get('menu_name', item.get('식품명', ''))
        allergens = str(item.get('allergens_scraped', ''))
        for feature in self.name_features: vector.append(1 if feature in name else 0)
        for feature in self.allergy_features: vector.append(1 if (feature in allergens or feature in name) else 0)
        item_cat = item.get('category_tag', 'ETC')
        for cat in self.cat_keys: vector.append(1 if cat == item_cat else 0)
        return np.array(vector)

    def calculate_hamming_distance(self, vec1, vec2):
        return np.sum(np.abs(vec1 - vec2))

    def get_diversity_score(self, combo):
        if len(combo) < 2: return 0.0
        vectors = [self.create_vector(item) for item in combo]
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                distances.append(self.calculate_hamming_distance(vectors[i], vectors[j]))
        return np.mean(distances) if distances else 0.0
    
    def check_ingredient_overlap(self, combo):
        if len(combo) < 2: return False
        vectors = [self.create_vector(item) for item in combo]
        main_feature_len = len(self.name_features)
        sum_vector = np.sum(vectors, axis=0)
        if np.any(sum_vector[:main_feature_len] > 1): return True
        return False


# [v2.9.6] Problem 정의 - 목적함수: P/C/F 오차 + 가격 + 다양성, 제약조건: 칼로리/단백질 총량
class DietOptimizationProblem(ElementwiseProblem):
    def __init__(self, mains, sides, drinks, target_cal, target_prot, target_carbs, target_fat, 
                 sugar_limit, div_manager, cal_range_factor, prot_min_factor):
        self.mains = mains
        self.sides = sides
        self.drinks = drinks
        self.target_cal = target_cal
        self.target_prot = target_prot
        self.target_carbs = target_carbs
        self.target_fat = target_fat
        self.sugar_limit = sugar_limit
        self.div_manager = div_manager
        self.cal_range_factor = cal_range_factor
        self.prot_min_factor = prot_min_factor
        
        xl = [0, 0, 0, 0]
        xu = [
            max(0, len(mains) - 1),
            max(0, len(sides)),
            max(0, len(sides)),
            max(0, len(drinks))
        ]
        
        # [v2.9.6] n_obj=5 (P오차, C오차, F오차, 가격, -다양성), n_constr=3 (당류, 칼로리범위, 단백질최소)
        super().__init__(n_var=4, n_obj=5, n_constr=3, xl=xl, xu=xu, type_var=int)

    def _evaluate(self, x, out, *args, **kwargs):
        x = x.astype(int)
        
        x[0] = np.clip(x[0], 0, len(self.mains) - 1)
        x[1] = np.clip(x[1], 0, len(self.sides))
        x[2] = np.clip(x[2], 0, len(self.sides))
        x[3] = np.clip(x[3], 0, len(self.drinks))
        
        combo = [self.mains[x[0]]]
        if x[1] < len(self.sides): combo.append(self.sides[x[1]])
        if x[2] < len(self.sides): combo.append(self.sides[x[2]])
        if x[3] < len(self.drinks): combo.append(self.drinks[x[3]])

        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_carbs = sum(item['carbs'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sugar = sum(item['sugars'] for item in combo)
        total_price = sum(item['price'] for item in combo)
        
        # ============================================================
        # [v2.9.6] 목적함수 5개: 단백질/탄수화물/지방 오차 + 가격 + 다양성
        # ============================================================
        
        # 1) 단백질 오차 (Objective 1) - 가중치 높음
        prot_error = abs(total_prot - self.target_prot) / max(self.target_prot, 1)
        
        # 2) 탄수화물 오차 (Objective 2)
        carbs_error = abs(total_carbs - self.target_carbs) / max(self.target_carbs, 1)
        
        # 3) 지방 오차 (Objective 3)
        fat_error = abs(total_fat - self.target_fat) / max(self.target_fat, 1)
        
        # 4) 가격 (Objective 4) - 최소화
        price_obj = total_price
        
        # 5) 다양성 (Objective 5) - 최대화 → -1 곱해서 최소화
        if self.div_manager.check_ingredient_overlap(combo):
            diversity_score = -1.0  # 재료 중복 시 페널티
        else:
            diversity_score = self.div_manager.get_diversity_score(combo)
        div_obj = -diversity_score

        # ============================================================
        # [v2.9.6] 제약조건 3개: 당류, 칼로리 범위, 단백질 최소
        # ============================================================
        
        # g1: 당류 제한 (sugar <= sugar_limit * 1.5)
        g1 = (total_sugar - self.sugar_limit * 1.5)
        
        # g2: 칼로리 범위 제약 (target_cal ± cal_range_factor)
        cal_lower_bound = self.target_cal * (1 - self.cal_range_factor)
        cal_upper_bound = self.target_cal * (1 + self.cal_range_factor)
        g2_lower = cal_lower_bound - total_cal  # total_cal >= lower_bound → g2_lower <= 0
        g2_upper = total_cal - cal_upper_bound  # total_cal <= upper_bound → g2_upper <= 0
        g2 = max(g2_lower, g2_upper)
        
        # g3: 단백질 최소 제약 (total_prot >= target_prot * prot_min_factor)
        g3 = (self.target_prot * self.prot_min_factor) - total_prot

        out["F"] = [prot_error, carbs_error, fat_error, price_obj, div_obj]
        out["G"] = [g1, g2, g3]


class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.9.6: Macro-based Objectives)...")
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
        safe_menu_items = []
        for item in dishes:
            allergens = item.get('allergens', item.get('allergens_scraped', ''))
            if isinstance(allergens, dict):
                # from_supabase(): {"난류": true, ...} 형태
                if not any(allergens.get(a, False) for a in allergies_to_avoid):
                    safe_menu_items.append(item)
            else:
                # from_csv(): 문자열 형태
                allergens_lower = str(allergens).lower()
                if not any(a.lower() in allergens_lower for a in allergies_to_avoid):
                    safe_menu_items.append(item)
        return safe_menu_items

    @classmethod
    def from_supabase(cls, cal_min: float = 10.0) -> "DailyDietOptimizer":
        """Supabase food_master 테이블에서 데이터를 불러와 optimizer를 초기화합니다.

        pagination(range 1,000행 단위)으로 전체 3,358행을 로딩.
        allergens 컬럼은 JSONB dict {"알레르겐명": bool, ...} 형식.
        """
        from db.client import get_client
        print("⚙️ Supabase에서 food_master 로딩 중...")
        sb = get_client()
        rows = []
        offset = 0
        while True:
            resp = (
                sb.table("food_master")
                .select("id,menu_name,store_name,category_type,"
                        "calories,protein,carbs,fat,sugars,sodium,price,allergens")
                .range(offset, offset + 999)
                .execute()
            )
            batch = resp.data
            if not batch:
                break
            rows.extend(batch)
            print(f"  로딩 중... {len(rows)}행")
            if len(batch) < 1000:
                break
            offset += 1000

        print(f"  총 {len(rows)}행 로딩 완료")

        obj = cls.__new__(cls)

        df = pd.DataFrame(rows)
        numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'sugars', 'sodium', 'price']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['price'] = df['price'].fillna(0)
        df = df[df['calories'] > cal_min]
        df = df[df['price'] > 500]

        # allergens: JSONB dict {"난류": true, ...} 또는 None → {} 정규화
        df['allergens'] = df['allergens'].apply(
            lambda v: v if isinstance(v, dict) else {}
        )

        obj.df = df
        obj.categorizer = FoodCategorizer()
        obj.df = obj.df.copy()
        obj.df['category_tag'] = obj.df['menu_name'].apply(
            lambda name: obj.categorizer.assign_category(name if isinstance(name, str) else '')
        )
        obj.menu_items = obj.df.to_dict('records')
        obj.brand_menu_map = {}
        for item in obj.menu_items:
            brand = item.get('store_name', 'Unknown') or 'Unknown'
            cat = item['category_tag']
            if brand not in obj.brand_menu_map:
                obj.brand_menu_map[brand] = {c: [] for c in obj.categorizer.keywords.keys()}
            if cat in obj.brand_menu_map[brand]:
                obj.brand_menu_map[brand][cat].append(item)
        obj.div_manager = DiversityManager()

        print(f"✅ from_supabase() 초기화 완료: {len(obj.menu_items)}개 메뉴, {len(obj.brand_menu_map)}개 브랜드")
        return obj

    def recommend_daily_diet(self, target_cal, target_prot, target_carbs, target_fat, user_goal, 
                             allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, **kwargs):
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        
        cal_range_factor = kwargs.get('cal_range_factor', 0.05)
        prot_min_factor = kwargs.get('prot_min_factor', 0.95)
        
        sugar_ratio = SUGAR_RATIOS.get(user_goal, 0.10)
        meal_sugar_limit_g = (target_cal * sugar_ratio) / 4
        
        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        num_brands = min(NUM_BRAND_SAMPLES, len(available_brands))
        sampled_brands = random.sample(available_brands, num_brands)

        all_candidate_results = []
        
        for selected_brand in sampled_brands:
            brand_db = self.brand_menu_map[selected_brand]
            
            mains = self.filter_by_allergens(brand_db.get('MAIN', []), allergies_to_avoid)
            sides = self.filter_by_allergens(
                brand_db.get('SIDE', []) + brand_db.get('SOUP', []), allergies_to_avoid
            )
            drinks = self.filter_by_allergens(brand_db.get('DRINK', []), allergies_to_avoid)
            
            mains = [m for m in mains if m.get('FOOD_CODE') not in excluded_codes]
            sides = [s for s in sides if s.get('FOOD_CODE') not in excluded_codes]
            drinks = [d for d in drinks if d.get('FOOD_CODE') not in excluded_codes]
            
            if not mains or (len(mains) + len(sides)) < 3: 
                continue 

            try:
                problem = DietOptimizationProblem(
                    mains, sides, drinks, 
                    target_cal, target_prot, target_carbs, target_fat,
                    meal_sugar_limit_g, self.div_manager,
                    cal_range_factor, prot_min_factor
                )

                algorithm = NSGA2(
                    pop_size=120,
                    n_offsprings=60,
                    sampling=IntegerRandomSampling(),
                    crossover=PointCrossover(n_points=2, prob=0.9), 
                    mutation=PM(prob=0.1, eta=20),
                    eliminate_duplicates=True
                )

                termination = get_termination("n_gen", 60) 

                res = minimize(problem, algorithm, termination, seed=1, verbose=False)
                
                if res is None or res.F is None or len(res.F) == 0:
                    continue

                for i, x in enumerate(res.X):
                    if res.G is not None and np.any(res.G[i] > 0):
                        continue

                    x_int = x.astype(int)
                    x_int[0] = np.clip(x_int[0], 0, len(mains) - 1)
                    x_int[1] = np.clip(x_int[1], 0, len(sides))
                    x_int[2] = np.clip(x_int[2], 0, len(sides))
                    x_int[3] = np.clip(x_int[3], 0, len(drinks))
                    
                    combo = [mains[x_int[0]]]
                    if x_int[1] < len(sides): combo.append(sides[x_int[1]])
                    if x_int[2] < len(sides): combo.append(sides[x_int[2]])
                    if x_int[3] < len(drinks): combo.append(drinks[x_int[3]])
                    
                    # [v2.9.6] 목적함수 값 추출
                    prot_error = res.F[i][0]
                    carbs_error = res.F[i][1]
                    fat_error = res.F[i][2]
                    total_price = res.F[i][3]
                    diversity_score = -res.F[i][4]
                    
                    all_candidate_results.append({
                        'combo': combo,
                        'brand': selected_brand,
                        'price': total_price,
                        'calories': sum(item['calories'] for item in combo),
                        'protein': sum(item['protein'] for item in combo),
                        'carbs': sum(item['carbs'] for item in combo),
                        'fat': sum(item['fat'] for item in combo),
                        'sugars': sum(item['sugars'] for item in combo),
                        'sugar_limit': meal_sugar_limit_g,
                        'prot_error': prot_error,
                        'carbs_error': carbs_error,
                        'fat_error': fat_error,
                        'diversity_score': diversity_score,
                        'objectives': res.F[i]
                    })
                    
            except Exception as e:
                continue 

        if not all_candidate_results:
            return "❌ 최적해 발견 실패 (모든 브랜드 시도)"

        # [v2.9.6] 5개 목적함수에 대한 가중 유클리드 거리 계산
        objective_data = np.array([r['objectives'] for r in all_candidate_results])
        
        min_obj = np.min(objective_data, axis=0)
        max_obj = np.max(objective_data, axis=0)
        obj_range = max_obj - min_obj
        obj_range[obj_range == 0] = 1e-6
        
        normalized_obj = (objective_data - min_obj) / obj_range
        weighted_normalized_obj = normalized_obj * OBJECTIVE_WEIGHTS
        
        ideal_point = np.array([0, 0, 0, 0, 0]) 
        distances = np.linalg.norm(weighted_normalized_obj - ideal_point, axis=1)
        
        sorted_indices = np.argsort(distances)
        
        final_alternatives = []
        used_brands = set()

        for idx in sorted_indices:
            candidate = all_candidate_results[idx]
            if candidate['brand'] not in used_brands:
                final_alternatives.append(candidate)
                used_brands.add(candidate['brand'])
            
            if len(final_alternatives) >= NUM_ALTERNATIVES:
                break
        
        if not final_alternatives:
             final_alternatives = [all_candidate_results[sorted_indices[0]]]
        
        return final_alternatives


# -----------------------------------------------------
# 전역 변수 및 실행 로직
# -----------------------------------------------------
optimizer_instance = None

def init_worker():
    global optimizer_instance
    optimizer_instance = DailyDietOptimizer()

def run_single_simulation(user_profile):
    global optimizer_instance
    try:
        d_prot, d_carbs, d_fat = calculate_macro_grams(user_profile['target_cal'], user_profile['goal'], user_profile['weight'])
    except:
        return {"success": False, "reason": "Target Calc Error"}

    MEALS_COUNT = 3
    current_status = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0, 'sugars': 0, 'price': 0, 'diversity_sum': 0}
    excluded_codes = set()
    excluded_brands = set()
    result_log = []
    
    sugar_ratio = SUGAR_RATIOS.get(user_profile['goal'], 0.10)
    daily_sugar_limit_g = (user_profile['target_cal'] * sugar_ratio) / 4
    
    for i in range(MEALS_COUNT):
        remaining_meals = MEALS_COUNT - i
        target_cal = max((user_profile['target_cal'] - current_status['calories']) / remaining_meals, 100)
        target_prot = max((d_prot - current_status['protein']) / remaining_meals, 10)
        target_carbs = max((d_carbs - current_status['carbs']) / remaining_meals, 10)
        target_fat = max((d_fat - current_status['fat']) / remaining_meals, 5)
        
        # [v2.9.6] 1차 시도: 칼로리 ±5%, 단백질 95%
        meal_result = optimizer_instance.recommend_daily_diet(
            target_cal=target_cal, target_prot=target_prot, 
            target_carbs=target_carbs, target_fat=target_fat,
            user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
            excluded_codes=excluded_codes, excluded_brands=excluded_brands,
            cal_range_factor=0.05, prot_min_factor=0.95
        )
        
        # [v2.9.6] 2차 시도: 칼로리 ±10%, 단백질 90%
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, 
                target_carbs=target_carbs, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=excluded_brands,
                cal_range_factor=0.10, prot_min_factor=0.90
            )

        # [v2.9.6] 3차 시도: 칼로리 ±15%, 단백질 85% + 브랜드 제한 해제
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, 
                target_carbs=target_carbs, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=set(),
                cal_range_factor=0.15, prot_min_factor=0.85
            )

        if not isinstance(meal_result, str):
            result_log.append(meal_result)
            
            best_combo = meal_result[0]
            current_status['calories'] += best_combo['calories']
            current_status['protein'] += best_combo['protein']
            current_status['fat'] += best_combo['fat']
            current_status['carbs'] += best_combo['carbs']
            current_status['sugars'] += best_combo['sugars']
            current_status['price'] += best_combo['price']
            current_status['diversity_sum'] += best_combo.get('diversity_score', 0)
            
            excluded_brands.add(best_combo['brand'])
            for item in best_combo['combo']:
                if item.get('FOOD_CODE'): excluded_codes.add(item['FOOD_CODE'])
        else:
            return {"success": False, "reason": f"Meal {i+1} Failed"}

    return {
        "success": True,
        "price": current_status['price'],
        "calories": current_status['calories'],
        "protein": current_status['protein'],
        "carbs": current_status['carbs'],
        "fat": current_status['fat'],
        "sugars": current_status['sugars'],
        "sugar_limit": daily_sugar_limit_g,
        "avg_diversity": current_status['diversity_sum'] / MEALS_COUNT,
        "target_cal": user_profile['target_cal'],
        "target_prot": d_prot,
        "target_carbs": d_carbs,
        "target_fat": d_fat,
        "results": result_log, 
        "user_profile": user_profile
    }


class RandomUserGenerator:
    def __init__(self):
        self.goals = ["다이어트", "건강관리", "근육증가"]
        self.allergy_pool = ["난류", "땅콩", "우유", "대두", "밀", "새우", "복숭아"]
        self.activity_levels = list(ACTIVITY_FACTORS.keys()) 

    def generate(self):
        weight = random.randint(50, 90)
        height = random.randint(155, 190)
        age = random.randint(20, 50)
        gender = random.choice(['Male', 'Female'])
        goal = random.choice(self.goals)
        activity_level = random.choice(self.activity_levels)
        
        tdee = calculate_bmr_tdee(gender, weight, height, age, activity_level)
        
        target_cal = tdee
        if goal == "다이어트": target_cal = int(tdee * 0.85)
        elif goal == "근육증가": target_cal = int(tdee * 1.15)
        
        num_allergies = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        allergies = random.sample(self.allergy_pool, num_allergies)
        
        return {
            "weight": weight, 
            "height": height,
            "age": age,
            "gender": gender, 
            "goal": goal, 
            "target_cal": target_cal, 
            "allergies": allergies,
            "activity_level": activity_level
        }


def plot_distribution(ax, data, title, xlabel, color='skyblue'):
    if not data: return
    mean_val = np.mean(data)
    ax.hist(data, bins=20, color=color, edgecolor='black', alpha=0.7)
    ax.axvline(mean_val, color='red', linestyle='dashed', linewidth=1.5, label=f'Mean: {mean_val:.1f}')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.5)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    NUM_USERS = 50 
    user_gen = RandomUserGenerator()
    users = [user_gen.generate() for _ in range(NUM_USERS)]
    
    try: CORES_TO_USE = max(1, multiprocessing.cpu_count() - 1)
    except: CORES_TO_USE = 2
    
    print(f"\n🚀 [Parallel] {NUM_USERS}명 시뮬레이션 시작 (v2.9.6: Macro-based Objectives)")
    print(f"⚡ 활용할 CPU 코어 수: {CORES_TO_USE}개")
    print("--------------------------------------------------")
    
    start_time = time.time()
    with multiprocessing.Pool(processes=CORES_TO_USE, initializer=init_worker) as pool:
        results = pool.map(run_single_simulation, users)
    end_time = time.time()
    
    success_results = [res for res in results if res['success']]
    success_cnt = len(success_results)
    
    prices = [res['price'] for res in success_results]
    
    cal_accuracies = []
    prot_accuracies = []
    carbs_accuracies = []
    fat_accuracies = []
    
    diversity_scores = []
    sugar_usage_rates = []
    
    for res in success_results:
        t_cal, t_prot, t_carbs, t_fat = res['target_cal'], res['target_prot'], res['target_carbs'], res['target_fat']
        
        cal_accuracies.append(max(0, (1 - abs(res['calories'] - t_cal) / t_cal) * 100))
        prot_accuracies.append(max(0, (1 - abs(res['protein'] - t_prot) / t_prot) * 100))
        carbs_accuracies.append(max(0, (1 - abs(res['carbs'] - t_carbs) / t_carbs) * 100))
        
        if t_fat > 0:
            fat_accuracies.append(max(0, (1 - abs(res['fat'] - t_fat) / t_fat) * 100))
        else:
            fat_accuracies.append(100.0 if res['fat'] == 0 else 0.0)

        diversity_scores.append(res['avg_diversity'])
        sugar_usage_rates.append((res['sugars'] / res['sugar_limit']) * 100)
            
    success_rate = (success_cnt / NUM_USERS) * 100
    avg_price = np.mean(prices) if success_cnt > 0 else 0
    avg_cal_acc = np.mean(cal_accuracies) if success_cnt > 0 else 0
    avg_prot_acc = np.mean(prot_accuracies) if success_cnt > 0 else 0
    avg_carbs_acc = np.mean(carbs_accuracies) if success_cnt > 0 else 0
    avg_fat_acc = np.mean(fat_accuracies) if success_cnt > 0 else 0
    avg_diversity = np.mean(diversity_scores) if success_cnt > 0 else 0
    avg_sugar_rate = np.mean(sugar_usage_rates) if success_cnt > 0 else 0
    
    print(f"\n✅ 시뮬레이션 완료 ({end_time - start_time:.2f}s)")
    print(f"📊 성공률: {success_rate:.1f}% ({success_cnt}/{NUM_USERS})")
    print(f"💰 평균 식단 가격: {avg_price:,.0f}원")
    print(f"🔥 평균 칼로리 정확도: {avg_cal_acc:.1f}%")
    print(f"💪 평균 단백질 정확도: {avg_prot_acc:.1f}%")
    print(f"🍞 평균 탄수화물 정확도: {avg_carbs_acc:.1f}%")
    print(f"🧈 평균 지방 정확도: {avg_fat_acc:.1f}%")
    print(f"🍭 평균 당류 한도 소진율: {avg_sugar_rate:.1f}%")
    print(f"🌈 평균 다양성 점수 (Hamming): {avg_diversity:.2f}")
    
    if success_cnt > 0:
        fig1, axes1 = plt.subplots(2, 2, figsize=(15, 12))
        plot_distribution(axes1[0, 0], prices, "Price Distribution", "KRW", 'skyblue')
        plot_distribution(axes1[0, 1], cal_accuracies, "Calorie Accuracy", "%", 'lightgreen')
        plot_distribution(axes1[1, 0], sugar_usage_rates, "Sugar Usage", "%", 'orange')
        plot_distribution(axes1[1, 1], diversity_scores, "Diversity Score", "Score", 'gold')
        plt.tight_layout()
        plt.savefig('figure1_core_metrics.png')
        
        fig2, axes2 = plt.subplots(2, 2, figsize=(15, 12))
        plot_distribution(axes2[0, 0], prot_accuracies, "Protein Accuracy", "%", 'salmon')
        plot_distribution(axes2[0, 1], carbs_accuracies, "Carbs Accuracy", "%", 'teal')
        plot_distribution(axes2[1, 0], fat_accuracies, "Fat Accuracy", "%", 'purple')
        plot_distribution(axes2[1, 1], cal_accuracies, "Cal Accuracy (Reference)", "%", 'lightgreen')
        plt.tight_layout()
        plt.savefig('figure2_macro_accuracy.png')

    if success_cnt > 0:
        sample = random.choice(success_results)
        u = sample['user_profile']
        
        print(f"\n[NSGA-II Random Sample] Goal: {u['goal']} | Target Cal: {u['target_cal']}kcal")
        
        print("\n   👉 Target (g): P: {tp:,.0f} | C: {tc:,.0f} | F: {tf:,.0f}".format(
            tp=sample['target_prot'], tc=sample['target_carbs'], tf=sample['target_fat']))
        print("   👉 Actual (g): P: {ap:,.0f} | C: {ac:,.0f} | F: {af:,.0f}".format(
            ap=sample['protein'], ac=sample['carbs'], af=sample['fat']))
        
        for m_idx, meal_alternatives in enumerate(sample['results']):
            print(f"\n   🥣 Meal {m_idx+1} Alternatives")
            for alt_idx, meal in enumerate(meal_alternatives):
                tag = "[SELECTED]" if alt_idx == 0 else f"[Option {alt_idx}]"
                print(f"       {tag} | Brand: {meal['brand']} | Price: {meal['price']:,.0f}원 | Div: {meal['diversity_score']:.2f}")
                print(f"               P_err: {meal['prot_error']:.2%} | C_err: {meal['carbs_error']:.2%} | F_err: {meal['fat_error']:.2%}")
                for item in meal['combo']: 
                    item_tag = item.get('category_tag', 'ETC')
                    print(f"           [{item_tag}] {item.get('menu_name', item.get('식품명'))}")
            
        print(f"\n   👉 Total Price (Based on SELECTED): {sample['price']:,}원 | Sugar {sample['sugars']:.1f}g | Avg Div {sample['avg_diversity']:.2f}")