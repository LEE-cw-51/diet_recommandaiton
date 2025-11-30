import pandas as pd
import numpy as np
import os
import sys

# 앳워터 계수 (Atwater Factors)
ATWATER_PROTEIN = 4
ATWATER_CARB = 4
ATWATER_FAT = 9
SAT_RATIO = 0.3 # 포화지방 평균 비율 (30%)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
FINAL_DB_FILE = os.path.join(INPUT_DIR, 'final_nutrition_db.csv')

def fix_fat_imputation():
    print(f"🔧 최종 지방/포화지방 집중 보정 시작: {FINAL_DB_FILE}\n")
    
    if not os.path.exists(FINAL_DB_FILE):
        print("❌ 오류: 최종 DB 파일이 없습니다. 경로를 확인해주세요.")
        return

    df = pd.read_csv(FINAL_DB_FILE)
    
    # 1. 초기 데이터 클리닝 및 숫자형 변환
    numeric_cols = ['calories', 'protein', 'carbs', 'fat', 'saturated_fat']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # ---------------------------------------------------------
    # 1단계: 총 지방 (Fat) 추정
    # (이미 채워진 Carbs, Protein 값을 활용하여 Atwater 역산)
    # ---------------------------------------------------------
    mask_fat_missing = (df['fat'] == 0.0) & (df['calories'] > 0.0) & (df['protein'] > 0.0) & (df['carbs'] > 0.0)
    
    def estimate_total_fat(row):
        non_fat_cal = (row['protein'] * ATWATER_PROTEIN) + (row['carbs'] * ATWATER_CARB)
        residual_cal = row['calories'] - non_fat_cal
        
        # 지방 칼로리가 양수일 때만 계산
        if residual_cal > 0:
            estimated_fat = residual_cal / ATWATER_FAT
            return round(estimated_fat, 1)
        return 0.0

    df.loc[mask_fat_missing, 'fat'] = df.loc[mask_fat_missing].apply(estimate_total_fat, axis=1)
    fat_imputed_count = mask_fat_missing.sum()
    print(f"   ✅ 1단계: 총 지방(Fat) 추정 완료: {fat_imputed_count}개 메뉴")

    # ---------------------------------------------------------
    # 2단계: 포화지방 (Saturated Fat) 추정
    # (새롭게 채워진 Total Fat 값을 즉시 활용하여 Saturated Fat 보정)
    # ---------------------------------------------------------
    # 조건: 포화지방이 0.0이고, 총 지방(Fat)이 0.1 이상인 경우 (계산이 가능해진 경우 포함)
    mask_sat_missing = (df['saturated_fat'] == 0.0) & (df['fat'] > 0.1)
    
    # 포화지방 = 총 지방 * 30% 비율 적용
    df.loc[mask_sat_missing, 'saturated_fat'] = (df.loc[mask_sat_missing, 'fat'] * SAT_RATIO).round(1)
    
    sat_imputed_count = mask_sat_missing.sum()
    print(f"   ✅ 2단계: 포화지방(Saturated Fat) 추정 완료: {sat_imputed_count}개 메뉴")


    # 최종 저장
    df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 지방 데이터 최종 보정 완료! ({FINAL_DB_FILE})")

if __name__ == '__main__':
    fix_fat_imputation()