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

# -----------------------------------------------------------
# [설정] 차트 한글 폰트 깨짐 방지 (로컬 환경용)
# -----------------------------------------------------------
# 실행 전 본인 PC에 설치된 한글 폰트명으로 변경이 필요할 수 있습니다.
# Mac: 'AppleGothic', Windows: 'Malgun Gothic' 등
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
SUGAR_CAL_PERCENT = 0.10

MACRO_GOAL_RATIOS = {
    "다이어트": {'P': (0.35, 0.50), 'C': (0.30, 0.45), 'F': (0.15, 0.30)},
    "건강관리": {'P': (0.25, 0.35), 'C': (0.45, 0.55), 'F': (0.15, 0.25)},
    "근육증가": {'P': (0.35, 0.45), 'C': (0.35, 0.45), 'F': (0.15, 0.25)}
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'final_nutrition_db.csv')

def calculate_macro_grams(target_cal, user_goal, weight):
    protein_factors = {
        "다이어트": 2.0,
        "건강관리": 1.2,
        "근육증가": 1.6
    }
    factor = protein_factors.get(user_goal, 1.2)
    target_prot = round(weight * factor)
    
    prot_cal = target_prot * ATWATER_P
    remaining_cal = target_cal - prot_cal
    
    if remaining_cal <= 0:
        return target_prot, 0, 0
    
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
    
    target_carbs = round(target_carbs_cal / ATWATER_C)
    target_fat = round(target_fat_cal / ATWATER_F)
    
    return target_prot, target_carbs, target_fat

# -----------------------------------------------------------
# 클래스 정의
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
    """
    [v2.7.1 Upgrade] 
    통합 임베딩 (Integrated Embedding): 메뉴명 + 알러지 정보
    """
    def __init__(self):
        # 1. 메뉴명 추정 특성 (Name Features)
        self.name_features = [
            '닭', '치킨', '가슴살', # 0: Poultry
            '돼지', '돈까스', '햄', '베이컨', '소시지', '핫바', '후랑크', # 1: Pork
            '소', '비프', '불고기', '스테이크', # 2: Beef
            '새우', '오징어', '해물', '생선', '명란', # 3: Seafood
            '면', '파스타', '국수', '우동', '스파게티', '짜장', '짬뽕', # 4: Noodles
            '밥', '라이스', '덮밥', '비빔밥', '볶음밥', '국밥', '죽', '리조또', # 5: Rice
            '빵', '버거', '샌드위치', '토스트', '베이글', '피자', '핫도그', # 6: Bread
            '매운', '핫', '스파이시' # 7: Taste
        ]
        
        # 2. 알러지 정보 기반 특성 (Allergen Features)
        self.allergy_features = [
            '난류', '알류', '계란', # Eggs
            '우유', # Milk/Dairy
            '땅콩', '견과', # Nuts
            '복숭아', '토마토', # Fruits/Veg
            '밀', '대두' # Common Allergens (이건 중복 허용 가능성이 높음)
        ]
        
        # 3. 카테고리
        self.cat_keys = ['MAIN', 'SIDE', 'DRINK', 'SNACK'] 

    def create_vector(self, item):
        """메뉴 이름, 알러지 정보, 카테고리를 모두 반영한 통합 벡터 생성"""
        vector = []
        name = item.get('menu_name', item.get('식품명', ''))
        allergens = str(item.get('allergens_scraped', ''))
        
        # (1) 이름 기반 특성 태깅
        for feature in self.name_features:
            vector.append(1 if feature in name else 0)
            
        # (2) 알러지 정보 기반 특성 태깅 (이름 또는 알러지 정보 컬럼 확인)
        for feature in self.allergy_features:
            if feature in allergens or feature in name:
                vector.append(1)
            else:
                vector.append(0)
        
        # (3) 카테고리 태깅
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
    
    def check_ingredient_overlap(self, combo):
        """
        [중요] 중복 필터링은 '메인 재료'에 대해서만 엄격하게 적용
        (밀, 대두 같은 흔한 알러지 성분이 겹친다고 식단을 제외하면 안 되므로)
        """
        if len(combo) < 2: return False
        
        vectors = [self.create_vector(item) for item in combo]
        
        # 메인 재료 특성의 길이만큼만 슬라이싱해서 검사 (name_features)
        main_feature_len = len(self.name_features)
        
        sum_vector = np.sum(vectors, axis=0)
        
        # 메인 재료 부분에서 2개 이상 겹치면 True (제외)
        if np.any(sum_vector[:main_feature_len] > 1):
            return True
        return False

class DailyDietOptimizer:
    def __init__(self, data_path=DATA_PATH):
        print("⚙️ AI 추천 엔진 초기화 중 (v2.7.1: Name + Allergen Vectorization)...")
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

        # 알러지 컬럼 문자열 변환
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
        return sorted_candidates[:5]

    def recommend_daily_diet(self, target_cal, target_prot, target_fat, user_goal, allergies_to_avoid=[], excluded_codes=None, excluded_brands=None, num_simulations=20000, **kwargs):
        
        if excluded_codes is None: excluded_codes = set()
        if excluded_brands is None: excluded_brands = set()
        goal_ratios = MACRO_GOAL_RATIOS.get(user_goal)
        
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

            combo = [random.choice(mains)]
            if sides and random.random() < 0.6:
                combo.append(random.choice(sides))
                if len(sides) > 1 and random.random() < 0.3:
                    combo.append(random.choice(sides))
            if drinks and random.random() < 0.5:
                combo.append(random.choice(drinks))
            
            # [v2.7.1] 통합 벡터 기반 중복 재료 필터링
            if self.div_manager.check_ingredient_overlap(combo): continue
            
            div_score = 0
            if len(combo) > 1:
                # [v2.7.1] 통합 벡터 기반 다양성 점수 계산
                div_score = self.div_manager.get_diversity_score(combo)
                if div_score == 0.0: continue

            total_price = sum(item['price'] for item in combo)
            error, tot_cal, tot_prot, tot_carbs, tot_fat, tot_sodium, is_sodium_valid, is_protein_min_met, is_cal_valid = self.calculate_nutritional_error(
                combo, target_cal, target_prot, target_fat, goal_ratios, prot_min_factor, cal_range
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
    global optimizer_instance
    
    try:
        d_prot, d_carbs, d_fat = calculate_macro_grams(user_profile['target_cal'], user_profile['goal'], user_profile['weight'])
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
            excluded_codes=excluded_codes, excluded_brands=excluded_brands,
            prot_min_factor=0.95, cal_range=0.15
        )
        
        # 2차 시도
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=excluded_brands,
                prot_min_factor=0.70, cal_range=0.30
            )

        # 3차 시도
        if isinstance(meal_result, str):
            meal_result = optimizer_instance.recommend_daily_diet(
                target_cal=target_cal, target_prot=target_prot, target_fat=target_fat,
                user_goal=user_profile['goal'], allergies_to_avoid=user_profile['allergies'],
                excluded_codes=excluded_codes, excluded_brands=set(),
                prot_min_factor=0.70, cal_range=0.30
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
    median_val = np.median(data)
    min_val = np.min(data)
    max_val = np.max(data)
    
    ax.hist(data, bins=20, color=color, edgecolor='black', alpha=0.7)
    ax.axvline(mean_val, color='red', linestyle='dashed', linewidth=1.5, label=f'Mean: {mean_val:.1f}')
    ax.axvline(median_val, color='green', linestyle='dashed', linewidth=1.5, label=f'Median: {median_val:.1f}')
    
    stats_text = f"Mean: {mean_val:,.1f}\nMedian: {median_val:,.1f}\nMin: {min_val:,.1f}\nMax: {max_val:,.1f}"
    props = dict(boxstyle='round', facecolor='white', alpha=0.5)
    ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, fontsize=10, verticalalignment='top', horizontalalignment='right', bbox=props)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.5)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    NUM_USERS = 100 
    user_gen = RandomUserGenerator()
    users = [user_gen.generate() for _ in range(NUM_USERS)]
    
    try:
        total_cores = multiprocessing.cpu_count()
        CORES_TO_USE = max(1, total_cores - 1)
    except:
        CORES_TO_USE = 2
    
    print(f"\n🚀 [Parallel] {NUM_USERS}명 시뮬레이션 시작 (v2.7.1: Name + Allergen Vector)")
    print(f"⚡ 활용할 CPU 코어 수: {CORES_TO_USE}개")
    print("--------------------------------------------------")
    
    start_time = time.time()
    
    with multiprocessing.Pool(processes=CORES_TO_USE, initializer=init_worker) as pool:
        results = pool.map(run_single_simulation, users)
        
    end_time = time.time()
    
    success_results = [res for res in results if res['success']]
    success_cnt = len(success_results)
    
    prices = []
    cal_accuracies = []
    prot_accuracies = []
    diversity_scores = []
    
    for res in success_results:
        prices.append(res['price'])
        cal_diff = abs(res['calories'] - res['target_cal']) / res['target_cal']
        prot_diff = abs(res['protein'] - res['target_prot']) / res['target_prot']
        
        cal_accuracies.append(max(0, (1 - cal_diff) * 100))
        prot_accuracies.append(max(0, (1 - prot_diff) * 100))
        diversity_scores.append(res['avg_diversity'])
            
    success_rate = (success_cnt / NUM_USERS) * 100
    avg_price = np.mean(prices) if success_cnt > 0 else 0
    avg_cal_acc = np.mean(cal_accuracies) if success_cnt > 0 else 0
    avg_prot_acc = np.mean(prot_accuracies) if success_cnt > 0 else 0
    avg_diversity = np.mean(diversity_scores) if success_cnt > 0 else 0
    
    print(f"\n✅ 시뮬레이션 완료 ({end_time - start_time:.2f}s)")
    print(f"📊 성공률: {success_rate:.1f}% ({success_cnt}/{NUM_USERS})")
    print(f"💰 평균 식단 가격: {avg_price:,.0f}원")
    print(f"🔥 평균 칼로리 정확도: {avg_cal_acc:.1f}%")
    print(f"💪 평균 단백질 정확도: {avg_prot_acc:.1f}%")
    print(f"🌈 평균 다양성 점수 (Hamming): {avg_diversity:.2f}")
    
    if success_cnt > 0:
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            plot_distribution(axes[0, 0], prices, "Price Distribution", "Price (KRW)", color='skyblue')
            plot_distribution(axes[0, 1], cal_accuracies, "Calorie Accuracy", "Accuracy (%)", color='lightgreen')
            plot_distribution(axes[1, 0], prot_accuracies, "Protein Accuracy", "Accuracy (%)", color='salmon')
            plot_distribution(axes[1, 1], diversity_scores, "Diversity Score (Hamming)", "Score", color='gold')
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"❌ 시각화 오류: {e}")

    if success_cnt > 0:
        sample_size = min(5, success_cnt)
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