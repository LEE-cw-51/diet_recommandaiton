import pandas as pd
import numpy as np
import os
import sys

# 앳워터 계수 (Atwater Factors)
ATWATER_PROTEIN = 4
ATWATER_CARB = 4
ATWATER_FAT = 9

# -----------------------------------------------------------
# [수정된 부분] BASE_DIR 정의를 먼저 수행
# -----------------------------------------------------------
# 현재 스크립트 위치의 부모 폴더(프로젝트 루트)를 기준으로 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 

# 파일 경로
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
FINAL_DB_FILE = os.path.join(INPUT_DIR, 'final_nutrition_db.csv')

def fix_nutrition_data():
    print(f"🔧 [통합 보정] 영양소 데이터 빈칸 채우기 시작: {FINAL_DB_FILE}\n")
    
    if not os.path.exists(FINAL_DB_FILE):
        print(f"❌ 오류: 데이터 파일이 없습니다. 경로를 확인해주세요: {FINAL_DB_FILE}")
        return

    df = pd.read_csv(FINAL_DB_FILE)
    
    # 1. 숫자형 변환 및 NaN -> 0.0 처리
    numeric_cols = ['calories', 'protein', 'fat', 'carbs', 'saturated_fat']
    for col in numeric_cols:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # ==========================================================================
    # 1단계: 3대 영양소 (탄/단/지) 상호 보정
    # (칼로리는 있는데 특정 영양소가 0인 경우 역산)
    # ==========================================================================
    
    count_carbs = 0
    count_fat = 0
    
    for idx, row in df.iterrows():
        cal = row['calories']
        p = row['protein']
        f = row['fat']
        c = row['carbs']
        
        if cal == 0: continue

        # Case A: 탄수화물(Carbs)이 비어있음
        if c == 0 and (p > 0 or f > 0):
            # Carbs = (Cal - (P*4 + F*9)) / 4
            estimated_c = (cal - (p * ATWATER_PROTEIN + f * ATWATER_FAT)) / ATWATER_CARB
            df.at[idx, 'carbs'] = max(0.0, round(estimated_c, 1))
            count_carbs += 1
            
        # Case B: 지방(Fat)이 비어있음
        elif f == 0 and (p > 0 or c > 0):
            # Fat = (Cal - (P*4 + C*4)) / 9
            estimated_f = (cal - (p * ATWATER_PROTEIN + c * ATWATER_CARB)) / ATWATER_FAT
            df.at[idx, 'fat'] = max(0.0, round(estimated_f, 1))
            count_fat += 1

    # ==========================================================================
    # 2단계: 포화지방 (Saturated Fat) 보정
    # (이제 지방(Fat) 값이 채워졌으므로, 그걸 기반으로 30% 계산)
    # ==========================================================================
    
    count_sat = 0
    SAT_RATIO = 0.3 # 평균 포화지방 비율 (30%)

    for idx, row in df.iterrows():
        f = row['fat']
        sat = row['saturated_fat']
        
        # 지방은 있는데 포화지방이 0인 경우만 타겟
        if f > 0 and sat == 0:
            df.at[idx, 'saturated_fat'] = round(f * SAT_RATIO, 1)
            count_sat += 1

    # ==========================================================================
    # 저장 및 출력
    # ==========================================================================
    
    # 최종 DB 덮어쓰기
    df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')

    print(f"🎉 영양소 보정 완료!")
    print(f"   - 탄수화물 보정: {count_carbs}개")
    print(f"   - 지방 보정    : {count_fat}개")
    print(f"   - 포화지방 보정: {count_sat}개")
    print(f"💾 저장 경로: {FINAL_DB_FILE}")


if __name__ == '__main__':
    fix_nutrition_data()