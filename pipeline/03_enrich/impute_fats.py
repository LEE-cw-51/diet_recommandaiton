import pandas as pd
import numpy as np
import os
import sys

# 앳워터 계수
ATWATER_PROTEIN = 4
ATWATER_CARB = 4
ATWATER_FAT = 9

# 프로젝트 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
FINAL_DB_FILE = os.path.join(OUTPUT_DIR, 'final_nutrition_db.csv')

def impute_missing_fats():
    print(f"🔬 지방 데이터 보정 시작: {FINAL_DB_FILE}\n")
    
    if not os.path.exists(FINAL_DB_FILE):
        print(f"❌ 오류: 파일이 없습니다. 'impute_nutrition.py'를 먼저 실행했는지 확인하세요.")
        return

    df = pd.read_csv(FINAL_DB_FILE)
    
    # 숫자형 변환 및 NaN 처리
    numeric_cols = ['calories', 'protein', 'fat', 'carbs', 'saturated_fat']
    for col in numeric_cols:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # ---------------------------------------------------------
    # 1. 총 지방 (Fat) 추정: 앳워터 공식 역산
    # ---------------------------------------------------------
    # 조건: 지방이 0이고, 칼로리/단백질/탄수화물은 있는 경우
    mask_fat = (df['fat'] == 0.0) & (df['calories'] > 0.0) & (df['protein'] > 0.0) & (df['carbs'] > 0.0)
    
    def estimate_fat(row):
        # 단백질과 탄수화물이 낸 칼로리를 뺌
        non_fat_cal = (row['protein'] * ATWATER_PROTEIN) + (row['carbs'] * ATWATER_CARB)
        residual_cal = row['calories'] - non_fat_cal
        
        # 남은 칼로리를 지방(9kcal/g)으로 나눔
        estimated_fat = residual_cal / ATWATER_FAT
        return max(0.0, round(estimated_fat, 1))

    df.loc[mask_fat, 'fat'] = df.loc[mask_fat].apply(estimate_fat, axis=1)
    fat_imputed_count = mask_fat.sum()
    print(f"   ✅ 총 지방(Total Fat) 추정 완료: {fat_imputed_count}개 메뉴")

    # ---------------------------------------------------------
    # 2. 포화지방 (Saturated Fat) 추정: 평균 비율 적용
    # ---------------------------------------------------------
    # 데이터가 온전한 메뉴들(지방과 포화지방이 모두 0보다 큰 경우)에서 비율 계산
    valid_fat_mask = (df['fat'] > 0.1) & (df['saturated_fat'] > 0.1)
    
    if valid_fat_mask.sum() > 0:
        # 평균 비율 계산 (포화지방 / 총지방)
        avg_ratio = (df.loc[valid_fat_mask, 'saturated_fat'] / df.loc[valid_fat_mask, 'fat']).mean()
        # 비율이 비정상적으로 높으면(1.0 초과) 1.0으로 제한, 너무 낮으면 0.3(30%) 정도로 보정
        avg_ratio = min(1.0, max(0.3, avg_ratio))
        
        print(f"   ℹ️  평균 포화지방 비율 계산됨: {avg_ratio*100:.1f}% (기존 데이터 기반)")
        
        # 포화지방이 0이고 총 지방은 있는 경우에 적용
        mask_sat = (df['saturated_fat'] == 0.0) & (df['fat'] > 0.0)
        df.loc[mask_sat, 'saturated_fat'] = (df.loc[mask_sat, 'fat'] * avg_ratio).round(1)
        
        sat_imputed_count = mask_sat.sum()
        print(f"   ✅ 포화지방(Saturated Fat) 추정 완료: {sat_imputed_count}개 메뉴")
    else:
        print("   ⚠️ 경고: 포화지방 비율을 계산할 샘플 데이터가 부족합니다.")

    # 최종 저장
    df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 모든 지방 데이터 보정 완료! 저장됨: {FINAL_DB_FILE}")

if __name__ == '__main__':
    impute_missing_fats()