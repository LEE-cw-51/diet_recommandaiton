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

# [v2.8.4] NSGA-II 라이브러리 임포트 (안정성 강화)
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

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
                     '버거', '샌드위치', '토스트', '핫도그', '피자', '베이글', '라면', '우동', '국수', '파스타', '스파게티', '면', '짜장', '짬뽕'],
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
        self.name_features = [
            '닭', '치킨', '가슴살', '돼지', '돈까스', '햄', '베이컨', '소시지', '핫바', '후랑크',
            '소', '비프', '불고기', '스테이크', '새우', '오징어', '해물', '생선', '명란',
            '면', '파스타', '국수', '우동', '스파게티', '짜장', '짬뽕',
            '밥', '라이스', '덮밥', '비빔밥', '볶음밥', '국밥', '죽', '리조또',
            '빵', '버거', '샌드위치', '토스트', '베이글', '피자', '핫도그',
            '매운', '핫', '스파이시'
        ]
        self.allergy_features = ['난류', '알류', '계란', '우유', '땅콩', '견과', '복숭아', '토마토', '밀', '대두']
        self.cat_keys = ['MAIN', 'SIDE', 'DRINK', 'SNACK'] 

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

# [v2.8.4] pymoo 문제 정의 (안정성 대폭 강화)
class DietOptimizationProblem(ElementwiseProblem):
    def __init__(self, mains, sides, drinks, target_cal, target_prot, target_fat, sugar_limit, div_manager):
        # 유전자: [Main_idx, Side1_idx, Side2_idx, Drink_idx]
        self.mains = mains
        self.sides = sides
        self.drinks = drinks
        self.target_cal = target_cal
        self.target_prot = target_prot
        self.target_fat = target_fat
        self.sugar_limit = sugar_limit
        self.div_manager = div_manager
        
        xl = [0, 0, 0, 0]
        # [수정] xu 값을 명확하게 설정하고 음수 방지
        xu = [
            max(0, len(mains) - 1),      # Main은 필수이므로 최소 1개 필요
            max(0, len(sides)),           # Side는 선택 가능 (len = 선택 안함)
            max(0, len(sides)),           # Side는 선택 가능
            max(0, len(drinks))           # Drink는 선택 가능
        ]
        
        super().__init__(n_var=4, n_obj=3, n_constr=2, xl=xl, xu=xu, type_var=int)

    def _evaluate(self, x, out, *args, **kwargs):
        # [수정] 타입 안정성을 위해 int 변환
        x = x.astype(int)
        
        # [추가] 범위 체크 및 클리핑 - 안전장치
        x[0] = np.clip(x[0], 0, len(self.mains) - 1)
        x[1] = np.clip(x[1], 0, len(self.sides))
        x[2] = np.clip(x[2], 0, len(self.sides))
        x[3] = np.clip(x[3], 0, len(self.drinks))
        
        combo = []
        
        # 1. Main Menu (항상 추가)
        combo.append(self.mains[x[0]])
        
        # 2. Side 1 (선택적)
        if x[1] < len(self.sides):
            combo.append(self.sides[x[1]])
        
        # 3. Side 2 (선택적)
        if x[2] < len(self.sides):
            combo.append(self.sides[x[2]])
            
        # 4. Drink (선택적)
        if x[3] < len(self.drinks):
            combo.append(self.drinks[x[3]])

        total_cal = sum(item['calories'] for item in combo)
        total_prot = sum(item['protein'] for item in combo)
        total_fat = sum(item['fat'] for item in combo)
        total_sodium = sum(item['sodium'] for item in combo)
        total_sugar = sum(item['sugars'] for item in combo)
        total_price = sum(item['price'] for item in combo)
        
        cal_error = ((total_cal - self.target_cal) / self.target_cal) ** 2
        prot_error = ((total_prot - self.target_prot) / self.target_prot) ** 2
        
        sugar_penalty = 0
        if total_sugar > self.sugar_limit:
            sugar_penalty = ((total_sugar - self.sugar_limit) / self.sugar_limit) ** 2 * 3.0
            
        nutri_error = np.sqrt(cal_error + prot_error + sugar_penalty)
        price_obj = total_price

        if self.div_manager.check_ingredient_overlap(combo):
            diversity_score = -1.0
        else:
            diversity_score = self.div_manager.get_diversity_score(combo)
        
        div_obj = -diversity_score

        g1 = (total_sugar - self.sugar_limit * 1.5) 
        g2 = (self.target_prot * 0.8) - total_prot

        out["F"] = [nutri_error, price_obj, div_obj]
        out["G"] = [g1, g2]

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.8.4: NSGA-II Robust Fix)...")
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

    def recommend_daily_diet(self, target_cal, target_prot, target_fat, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, **kwargs):
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        
        sugar_ratio = SUGAR_RATIOS.get(user_goal, 0.10)
        meal_sugar_limit_g = (target_cal * sugar_ratio) / 4
        
        available_brands = [b for b in self.brand_menu_map.keys() if b not in excluded_brands]
        if not available_brands: return "❌ 가용 브랜드 없음"

        selected_brand = random.choice(available_brands)
        brand_db = self.brand_menu_map[selected_brand]
        
        mains = self.filter_by_allergens(brand_db.get('MAIN', []), allergies_to_avoid)
        sides = self.filter_by_allergens(brand_db.get('SIDE', []), allergies_to_avoid)
        drinks = self.filter_by_allergens(brand_db.get('DRINK', []), allergies_to_avoid)
        
        mains = [m for m in mains if m.get('FOOD_CODE') not in excluded_codes]
        sides = [s for s in sides if s.get('FOOD_CODE') not in excluded_codes]
        drinks = [d for d in drinks if d.get('FOOD_CODE') not in excluded_codes]
        
        if not mains: return "❌ 메인 메뉴 부족"

        try:
            problem = DietOptimizationProblem(
                mains, sides, drinks, target_cal, target_prot, target_fat, meal_sugar_limit_g, self.div_manager
            )

            algorithm = NSGA2(
                pop_size=100,
                n_offsprings=50,
                sampling=IntegerRandomSampling(),
                crossover=PointCrossover(n_points=2, prob=0.9), 
                mutation=PM(prob=0.1, eta=20),
                eliminate_duplicates=True
            )

            termination = get_termination("n_gen", 40) 

            res = minimize(problem, algorithm, termination, seed=1, verbose=False)
            
            # [추가] None 체크 강화
            if res is None or res.F is None or len(res.F) == 0:
                return "❌ 최적해 발견 실패"
                
        except Exception as e:
            print(f"⚠️ 최적화 중 에러 발생: {e}")
            return "❌ 최적화 실패"

        final_results = []
        for i, x in enumerate(res.X):
            # x를 int로 변환 후 접근
            x_int = x.astype(int)
            
            # [추가] 안전한 인덱싱을 위한 클리핑
            x_int[0] = np.clip(x_int[0], 0, len(mains) - 1)
            x_int[1] = np.clip(x_int[1], 0, len(sides))
            x_int[2] = np.clip(x_int[2], 0, len(sides))
            x_int[3] = np.clip(x_int[3], 0, len(drinks))
            
            combo = [mains[x_int[0]]]
            if x_int[1] < len(sides): combo.append(sides[x_int[1]])
            if x_int[2] < len(sides): combo.append(sides[x_int[2]])
            if x_int[3] < len(drinks): combo.append(drinks[x_int[3]])
            
            total_price = res.F[i][1]
            error = res.F[i][0]
            diversity_score = -res.F[i][2]
            
            total_cal = sum(item['calories'] for item in combo)
            total_prot = sum(item['protein'] for item in combo)
            total_fat = sum(item['fat'] for item in combo)
            total_sugars = sum(item['sugars'] for item in combo)
            
            final_results.append({
                'combo': combo,
                'brand': selected_brand,
                'price': total_price,
                'calories': total_cal,
                'protein': total_prot,
                'fat': total_fat,
                'sugars': total_sugars,
                'sugar_limit': meal_sugar_limit_g,
                'error': error,
                'diversity_score': diversity_score
            })
            
        sorted_results = sorted(final_results, key=lambda x: x['price'])
        return sorted_results[:5]

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
    current_status = {'calories': 0, 'protein': 0, 'fat': 0, 'sugars': 0, 'price': 0, 'diversity_sum': 0}
    excluded_codes = set()
    excluded_brands = set()
    result_log = []
    
    sugar_ratio = SUGAR_RATIOS.get(user_profile['goal'], 0.10)
    daily_sugar_limit_g = (user_profile['target_cal'] * sugar_ratio) / 4
    
    for i in range(MEALS_COUNT):
        remaining_meals = MEALS_COUNT - i
        target_cal = max((user_profile['target_cal'] - current_status['calories']) / remaining_meals, 100)
        target_prot = max((d_prot - current_status['protein']) / remaining_meals, 10)
        target_fat = max((d_fat - current_status['fat']) / remaining_meals, 5)
        
        # 1차 시도 (NSGA-II)
        meal_result = optimizer_instance.recommend_daily_diet(
            target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
            user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
            excluded_codes=excluded_codes, excluded_brands=excluded_brands
        )
        
        # 실패 시 재시도 (브랜드 제한 해제)
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=set()
            )

        if not isinstance(meal_result, str):
            best_combo = meal_result[0]
            current_status['calories'] += best_combo['calories']
            current_status['protein'] += best_combo['protein']
            current_status['fat'] += best_combo['fat']
            current_status['sugars'] += best_combo['sugars']
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
        "sugars": current_status['sugars'],
        "sugar_limit": daily_sugar_limit_g,
        "avg_diversity": current_status['diversity_sum'] / MEALS_COUNT,
        "target_cal": user_profile['target_cal'],
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
        activity_factor = random.uniform(1.2, 1.55) 
        gender_factor = 1.05 if gender == 'Male' else 0.95 
        tdee = int(weight * 24 * activity_factor * gender_factor)
        target_cal = tdee
        if goal == "다이어트": target_cal = int(tdee * 0.85)
        elif goal == "근육증가": target_cal = int(tdee * 1.15)
        num_allergies = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        allergies = random.sample(self.allergy_pool, num_allergies)
        return {"weight": weight, "gender": gender, "goal": goal, "target_cal": target_cal, "allergies": allergies}

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
    
    print(f"\n🚀 [Parallel] {NUM_USERS}명 시뮬레이션 시작 (v2.8.4: NSGA-II Robust Fix)")
    print(f"⚡ 활용할 CPU 코어 수: {CORES_TO_USE}개")
    print("--------------------------------------------------")
    
    start_time = time.time()
    with multiprocessing.Pool(processes=CORES_TO_USE, initializer=init_worker) as pool:
        results = pool.map(run_single_simulation, users)
    end_time = time.time()
    
    success_results = [res for res in results if res['success']]
    success_cnt = len(success_results)
    
    prices = [res['price'] for res in success_results]
    cal_accuracies = [max(0, (1 - abs(res['calories'] - res['target_cal']) / res['target_cal']) * 100) for res in success_results]
    diversity_scores = [res['avg_diversity'] for res in success_results]
    sugar_usage_rates = [(res['sugars'] / res['sugar_limit']) * 100 for res in success_results]
            
    success_rate = (success_cnt / NUM_USERS) * 100
    avg_price = np.mean(prices) if success_cnt > 0 else 0
    avg_cal_acc = np.mean(cal_accuracies) if success_cnt > 0 else 0
    avg_diversity = np.mean(diversity_scores) if success_cnt > 0 else 0
    avg_sugar_rate = np.mean(sugar_usage_rates) if success_cnt > 0 else 0
    
    print(f"\n✅ 시뮬레이션 완료 ({end_time - start_time:.2f}s)")
    print(f"📊 성공률: {success_rate:.1f}% ({success_cnt}/{NUM_USERS})")
    print(f"💰 평균 식단 가격: {avg_price:,.0f}원")
    print(f"🔥 평균 칼로리 정확도: {avg_cal_acc:.1f}%")
    print(f"🍭 평균 당류 한도 소진율: {avg_sugar_rate:.1f}%")
    print(f"🌈 평균 다양성 점수 (Hamming): {avg_diversity:.2f}")
    
    if success_cnt > 0:
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            plot_distribution(axes[0, 0], prices, "Price", "KRW", 'skyblue')
            plot_distribution(axes[0, 1], cal_accuracies, "Cal Accuracy", "%", 'lightgreen')
            plot_distribution(axes[1, 0], sugar_usage_rates, "Sugar Usage", "%", 'orange')
            plot_distribution(axes[1, 1], diversity_scores, "Diversity", "Score", 'gold')
            plt.tight_layout()
            plt.show()
        except Exception as e: print(f"❌ 시각화 오류: {e}")

    if success_cnt > 0:
        sample = random.choice(success_results)
        u = sample['user_profile']
        print(f"\n[NSGA-II Random Sample] {u['goal']} Target: {u['target_cal']}kcal")
        for m_idx, meal in enumerate(sample['results']):
            print(f"   🥣 Meal {m_idx+1} [{meal['brand']}]")
            for item in meal['combo']: print(f"       - {item.get('menu_name', item.get('식품명'))}")
        print(f"   👉 Total: {sample['price']:,}원 | Sugar {sample['sugars']:.1f}g | Div {sample['avg_diversity']:.2f}")