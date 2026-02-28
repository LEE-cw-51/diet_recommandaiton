import pandas as pd
import numpy as np
import os
import sys

# 앳워터 계수 (Atwater Factors)
ATWATER_PROTEIN = 4
ATWATER_FAT = 9
ATWATER_CARB = 4

# 프로젝트 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed') # 최종 DB가 저장된 위치
FINAL_DB_FILE = os.path.join(OUTPUT_DIR, 'final_nutrition_db.csv')

def impute_missing_carbs():
    print(f"🔬 영양소 보정 시작: {FINAL_DB_FILE}\n")
    
    if not os.path.exists(FINAL_DB_FILE):
        print(f"❌ 오류: 최종 DB 파일이 없습니다. 'merge_franchise_db.py'를 먼저 실행해주세요.")
        return

    df = pd.read_csv(FINAL_DB_FILE)
    
    # 필수 컬럼이 모두 숫자인지 확인 (클리닝 단계에서 이미 처리됨)
    required_cols = ['calories', 'protein', 'fat', 'carbs']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    imputation_count = 0

    # 탄수화물(carbs)이 0이고, 열량/단백질/지방은 존재하는 메뉴 필터링
    mask = (df['carbs'] == 0.0) & (df['calories'] > 0.0) & ((df['protein'] > 0.0) | (df['fat'] > 0.0))
    
    # 탄수화물 추정 함수
    def estimate_carbs(row):
        # Calories - (Protein * 4) - (Fat * 9)
        non_carb_cal = (row['protein'] * ATWATER_PROTEIN) + (row['fat'] * ATWATER_FAT)
        
        # 잔여 칼로리 (탄수화물에 해당되는 열량)
        residual_cal = row['calories'] - non_carb_cal
        
        # 탄수화물 g 추정
        estimated_carbs = residual_cal / ATWATER_CARB
        
        # 결과가 음수이거나 너무 작으면 0으로 처리 (오차 허용 범위)
        return max(0.0, round(estimated_carbs, 1))

    # 추정값 적용
    df.loc[mask, 'carbs_estimated'] = df.loc[mask].apply(estimate_carbs, axis=1)
    
    # 추정된 값이 0 이상이고 기존 값이 0일 때만 업데이트
    updated_mask = (df['carbs'] == 0.0) & (df['carbs_estimated'] > 0.1)
    df.loc[updated_mask, 'carbs'] = df.loc[updated_mask, 'carbs_estimated']
    
    imputation_count = updated_mask.sum()
    
    # 임시 컬럼 삭제 및 최종 저장
    if 'carbs_estimated' in df.columns:
        df = df.drop(columns=['carbs_estimated'])

    # 최종 DB 덮어쓰기
    df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')

    print(f"🎉 영양소 보정 완료!")
    print(f"   - 총 {imputation_count}개 메뉴의 탄수화물(Carbs) 값이 추정되었습니다.")
    print(f"   - 최종 DB 파일 업데이트 완료: {FINAL_DB_FILE}")

if __name__ == '__main__':
    impute_missing_carbs()