# -*- coding: utf-8 -*-
import pandas as pd
import re
from fuzzywuzzy import fuzz
import tqdm  # tqdm 모듈 전체를 임포트
import os
# [최적화 1] rapidfuzz 라이브러리 임포트
import rapidfuzz.process as rf_process
import rapidfuzz.fuzz as rf_fuzz

# --- 1. 경로 설정 (프로젝트 루트 기준으로 상대 경로 설정) ---
PROD_DATA_PATH = '../data/processed/all_products_combined.csv'
NUT_DATA_PATH = '../data/processed/final_cleaned_nutrition_db.csv'
OUTPUT_PATH = '../data/processed/matched_nutrition_db.csv'
FUZZY_MATCH_THRESHOLD = 90  # 유사도 매칭 임계값 (90점 이상만 인정)

# -----------------------------------------------------------
# --- 2. 텍스트 정규화 및 전처리 함수 ---
# -----------------------------------------------------------

def clean_name(name):
    """
    상품명/식품명에서 브랜드, 특수문자, 버전 등을 제거하고 핵심 이름만 추출하여 정규화합니다.
    """
    if pd.isna(name):
        return ""
    
    cleaned = str(name)
    cleaned = re.sub(r'[\(（].*?[\)）]', '', cleaned)
    cleaned = re.sub(r'[\[【].*?[\]】]', '', cleaned)
    cleaned = re.sub(r'[^\s\w]|_', '', cleaned) 
    cleaned = re.sub(r'\s*\d+\s*', '', cleaned) 
    cleaned = re.sub(r'NEW|OLD|ORIGINAL|기본|세트|콤보|패키지', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().replace(' ', '').lower()
    
    return cleaned

# -----------------------------------------------------------
# --- 3. 데이터 매칭 메인 함수 ---
# -----------------------------------------------------------

def match_data(prod_path, nut_path, output_path, threshold):
    """
    제품 데이터와 영양소 데이터를 2단계에 걸쳐 매칭하고 결과를 저장합니다.
    """
    print(f"1. 데이터 로드 시작: 제품({os.path.basename(prod_path)}), 영양소({os.path.basename(nut_path)})")
    
    try:
        df_prod = pd.read_csv(prod_path)
        # DtypeWarning을 방지하기 위해 low_memory=False 추가
        df_nut = pd.read_csv(nut_path, low_memory=False) 
    except FileNotFoundError as e:
        print("-" * 50); print(f"‼️ [오류] 파일을 찾을 수 없습니다: {e.filename}"); print("    1. 파일이 해당 경로에 정확히 있는지 확인하세요."); print("    2. 파일 이름에 오타가 없는지 확인하세요."); print("-" * 50); return

    if 'Original_ItemName' in df_prod.columns: prod_name_col = 'Original_ItemName'
    elif 'item_name' in df_prod.columns: prod_name_col = 'item_name'
    else: print("‼️ [오류] 제품 파일에 'item_name' 또는 'Original_ItemName' 컬럼이 없습니다."); return
        
    df_prod['cleaned_item_name'] = df_prod[prod_name_col].apply(clean_name)
    df_nut['cleaned_식품명'] = df_nut['식품명'].apply(clean_name)

    nut_cols_to_keep = ['FOOD_CODE', '식품명', '에너지(kcal)', '단백질(g)', '지방(g)', '탄수화물(g)', '나트륨(mg)', 'cleaned_식품명']
    nut_cols_exist = [col for col in nut_cols_to_keep if col in df_nut.columns]
    df_nut_slim = df_nut[nut_cols_exist].rename(columns={'식품명': 'Original_FoodName'})
    df_prod.rename(columns={prod_name_col: 'Original_ItemName'}, inplace=True)
    
    print("2. [단계 1] 완벽 일치 매칭 (Exact Match) 진행...")
    
    matched_df_exact = pd.merge(df_prod, df_nut_slim, left_on='cleaned_item_name', right_on='cleaned_식품명', how='inner', suffixes=('_prod', '_nut'))
    matched_prod_names = matched_df_exact['cleaned_item_name'].unique()
    
    unmatched_prod = df_prod[~df_prod['cleaned_item_name'].isin(matched_prod_names)].copy()
    unmatched_nut = df_nut_slim[~df_nut_slim['cleaned_식품명'].isin(matched_prod_names)].copy().reset_index(drop=True) # [최적화] 인덱스 리셋

    print(f"  -> 완벽 일치 매칭 수: {len(matched_df_exact)}")
    print(f"  -> 남은 미매칭 제품 수: {len(unmatched_prod)}")

    print(f"3. [단계 2] 유사도 기반 매칭 (Fuzzy Match, Threshold={threshold}) 진행 (최적화 모드)...")

    fuzzy_matches = []
    
    # [최적화 2] 비교 대상(영양 DB) 목록을 미리 만듭니다. (수만 개)
    nut_choices_list = unmatched_nut['cleaned_식품명'].to_list()
    
    if not nut_choices_list:
        print("  -> 비교할 영양 DB 항목이 없어 2단계를 건너뜁니다.")
    else:
        # [최적화 3] pandas의 apply 기능을 사용하여 한 줄씩 처리 (2776번만 반복)
        def find_best_match(prod_row):
            # rapidfuzz.process.extractOne:
            # prod_row['cleaned_item_name'] (제품명 1개)을
            # nut_choices_list (영양 DB 전체)와 비교하여
            # 점수가 90점(threshold)이 넘는 것 중 1등(가장 비슷한 것)을 찾아냅니다.
            match_result = rf_process.extractOne(
                prod_row['cleaned_item_name'],
                nut_choices_list,
                scorer=rf_fuzz.token_sort_ratio, # 점수 계산 방식 (fuzzwuzzy와 동일)
                score_cutoff=threshold
            )
            
            if match_result:
                # match_result는 (매칭된이름, 점수, 리스트에서의인덱스) 튜플
                score = match_result[1]
                list_index = match_result[2] # nut_choices_list에서의 인덱스
                
                # 인덱스를 사용하여 원본 영양소 정보를 가져옵니다.
                nut_row = unmatched_nut.iloc[list_index]
                
                # 제품 정보와 영양소 정보를 합칩니다.
                final_result = prod_row.to_dict()
                final_result.update(nut_row.to_dict())
                final_result['match_score'] = score
                return final_result
            return None

        # [최적화 4] tqdm.pandas()를 사용하여 apply에 진행률 표시
        tqdm.tqdm.pandas(desc="Optimized Fuzzy Matching")
        fuzzy_results = unmatched_prod.progress_apply(find_best_match, axis=1)
        
        # None이 아닌 유효한 매칭 결과만 리스트에 추가
        fuzzy_matches = [item for item in fuzzy_results if item is not None]

    matched_df_fuzzy = pd.DataFrame(fuzzy_matches)
    
    if not matched_df_fuzzy.empty:
        matched_df_fuzzy.sort_values(by='match_score', ascending=False, inplace=True)
        matched_df_fuzzy.drop_duplicates(subset=['Original_ItemName'], keep='first', inplace=True)
    
    print(f"  -> 유사도 일치 매칭 수: {len(matched_df_fuzzy)}")
    
    # -----------------------------------------------------------
    # 4. 최종 결과 통합 및 저장
    # -----------------------------------------------------------
    
    final_cols = ['Original_ItemName', 'cleaned_item_name', 'brand_name', 'price', 'Original_FoodName', 'FOOD_CODE', '에너지(kcal)', '단백질(g)', '지방(g)', '탄수화물(g)', '나트륨(mg)']
    
    available_cols_exact = [col for col in final_cols if col in matched_df_exact.columns]
    
    if not matched_df_fuzzy.empty:
        available_cols_fuzzy = [col for col in final_cols if col in matched_df_fuzzy.columns]
        final_matched_df = pd.concat([matched_df_exact[available_cols_exact], matched_df_fuzzy[available_cols_fuzzy]], ignore_index=True)
    else:
        final_matched_df = matched_df_exact[available_cols_exact]
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_matched_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print("-" * 50)
    print(f"✅ 데이터 매칭 완료!")
    print(f"총 매칭된 항목 수: {len(final_matched_df)}건")
    print(f"결과 파일 저장 위치: {output_path}")
    print("-" * 50)
    
    return final_matched_df

# -----------------------------------------------------------
# --- 5. 실행 블록 ---
# -----------------------------------------------------------
if __name__ == "__main__":
    
    try:
        import fuzzywuzzy
        import rapidfuzz # [최적화 5] rapidfuzz가 설치되었는지 확인
    except ImportError:
        print("="*60)
        print("‼️ 필수 라이브러리 설치 안내:")
        print("   fuzzywuzzy, tqdm, rapidfuzz가 필요합니다.")
        print("   다음 명령어로 설치하세요:")
        print("   pip install pandas fuzzywuzzy[speedup] tqdm rapidfuzz") # [최적화 6] 설치 명령어에 rapidfuzz 추가
        print("="*60)
        exit() 
        
    match_data(
        prod_path=PROD_DATA_PATH,
        nut_path=NUT_DATA_PATH,
        output_path=OUTPUT_PATH,
        threshold=FUZZY_MATCH_THRESHOLD
    )