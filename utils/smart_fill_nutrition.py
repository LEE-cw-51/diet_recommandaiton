import pandas as pd
import numpy as np
import os
import sys

# -----------------------------------------------------------
# [설정] 경로 설정
# -----------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
FINAL_DB_FILE = os.path.join(INPUT_DIR, 'final_nutrition_db.csv')

# 앳워터 계수
ATWATER_P = 4  # 단백질 4kcal/g
ATWATER_C = 4  # 탄수화물 4kcal/g
ATWATER_F = 9  # 지방 9kcal/g

def smart_fill():
    print(f"🧠 [Smart Fill] 영양소 결측치 정밀 보정 시작\n📂 대상 파일: {FINAL_DB_FILE}")

    if not os.path.exists(FINAL_DB_FILE):
        print("❌ 오류: 파일이 없습니다.")
        return

    df = pd.read_csv(FINAL_DB_FILE)

    # 1. 숫자형 변환 및 0 처리
    cols = ['calories', 'protein', 'fat', 'carbs', 'saturated_fat']
    for col in cols:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # -----------------------------------------------------------
    # [사전 작업] 데이터셋 전체의 영양소 비율 계산 (2개 이상 결측 시 사용)
    # -----------------------------------------------------------
    # 탄/단/지가 모두 있는 데이터만 뽑아서 평균 비율을 구함
    valid_mask = (df['protein'] > 0) & (df['carbs'] > 0) & (df['fat'] > 0)
    
    if valid_mask.sum() > 0:
        total_p_cal = (df.loc[valid_mask, 'protein'] * ATWATER_P).sum()
        total_c_cal = (df.loc[valid_mask, 'carbs'] * ATWATER_C).sum()
        total_f_cal = (df.loc[valid_mask, 'fat'] * ATWATER_F).sum()
        total_cal_sum = total_p_cal + total_c_cal + total_f_cal
        
        # 전체 데이터의 평균 에너지 기여도 (비율)
        RATIO_P = total_p_cal / total_cal_sum
        RATIO_C = total_c_cal / total_cal_sum
        RATIO_F = total_f_cal / total_cal_sum
        
        print(f"📊 [데이터 통계] 평균 영양 비율 -> 단백질: {RATIO_P*100:.1f}%, 탄수화물: {RATIO_C*100:.1f}%, 지방: {RATIO_F*100:.1f}%")
    else:
        # 데이터가 너무 없으면 일반적인 비율 적용 (5:3:2)
        RATIO_P, RATIO_C, RATIO_F = 0.2, 0.5, 0.3
        print("⚠️ [주의] 유효 데이터 부족으로 기본 비율(2:5:3)을 사용합니다.")

    counts = {1: 0, 2: 0, 3: 0, 'sat': 0}

    # -----------------------------------------------------------
    # [메인 로직] 행 단위 순회 및 보정
    # -----------------------------------------------------------
    for idx, row in df.iterrows():
        cal = row['calories']
        p, c, f = row['protein'], row['carbs'], row['fat']
        
        # 칼로리가 없으면 아예 추정 불가 (패스)
        if cal <= 0: continue

        # 결측 상태 확인 (0이면 없는 것으로 간주)
        missing_macros = []
        if p == 0: missing_macros.append('protein')
        if c == 0: missing_macros.append('carbs')
        if f == 0: missing_macros.append('fat')
        
        missing_cnt = len(missing_macros)

        # =======================================================
        # Case A: 1개만 없을 때 (완벽한 역산 가능)
        # =======================================================
        if missing_cnt == 1:
            target = missing_macros[0]
            current_cal = (p * ATWATER_P) + (c * ATWATER_C) + (f * ATWATER_F)
            remain_cal = max(0, cal - current_cal)
            
            if target == 'protein':
                df.at[idx, 'protein'] = round(remain_cal / ATWATER_P, 1)
            elif target == 'carbs':
                df.at[idx, 'carbs'] = round(remain_cal / ATWATER_C, 1)
            elif target == 'fat':
                df.at[idx, 'fat'] = round(remain_cal / ATWATER_F, 1)
            
            counts[1] += 1

        # =======================================================
        # Case B: 2개가 없을 때 (남은 칼로리를 비율대로 배분)
        # =======================================================
        elif missing_cnt == 2:
            # 존재하는 영양소의 칼로리를 뺌
            known_cal = 0
            if 'protein' not in missing_macros: known_cal += p * ATWATER_P
            if 'carbs' not in missing_macros: known_cal += c * ATWATER_C
            if 'fat' not in missing_macros: known_cal += f * ATWATER_F
            
            remain_cal = max(0, cal - known_cal)
            
            # 결측된 두 영양소의 상대적 비율 계산
            # 예: 탄수화물(Missing) vs 지방(Missing) -> 전체 통계 비율 가져오기
            ratio_sum = 0
            if 'protein' in missing_macros: ratio_sum += RATIO_P
            if 'carbs' in missing_macros: ratio_sum += RATIO_C
            if 'fat' in missing_macros: ratio_sum += RATIO_F
            
            # 비율대로 할당
            if 'protein' in missing_macros:
                alloc_cal = remain_cal * (RATIO_P / ratio_sum)
                df.at[idx, 'protein'] = round(alloc_cal / ATWATER_P, 1)
            
            if 'carbs' in missing_macros:
                alloc_cal = remain_cal * (RATIO_C / ratio_sum)
                df.at[idx, 'carbs'] = round(alloc_cal / ATWATER_C, 1)
                
            if 'fat' in missing_macros:
                alloc_cal = remain_cal * (RATIO_F / ratio_sum)
                df.at[idx, 'fat'] = round(alloc_cal / ATWATER_F, 1)

            counts[2] += 1

        # =======================================================
        # Case C: 3개 다 없을 때 (칼로리만 있음 -> 전체 평균 비율 적용)
        # =======================================================
        elif missing_cnt == 3:
            df.at[idx, 'protein'] = round((cal * RATIO_P) / ATWATER_P, 1)
            df.at[idx, 'carbs'] = round((cal * RATIO_C) / ATWATER_C, 1)
            df.at[idx, 'fat'] = round((cal * RATIO_F) / ATWATER_F, 1)
            
            counts[3] += 1

        # =======================================================
        # [공통] 포화지방 채우기 (지방이 채워진 후 실행)
        # =======================================================
        # 지방은 있는데 포화지방이 0이면 -> 지방의 30%로 설정
        final_fat = df.at[idx, 'fat']
        if final_fat > 0 and df.at[idx, 'saturated_fat'] == 0:
            df.at[idx, 'saturated_fat'] = round(final_fat * 0.3, 1)
            counts['sat'] += 1

    # 저장
    df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')

    print("-" * 50)
    print(f"🎉 보정 완료! 업데이트 상세:")
    print(f"   🔹 [Case 1] 1개 누락 (완벽 역산)    : {counts[1]}개 메뉴")
    print(f"   🔸 [Case 2] 2개 누락 (비율 배분)    : {counts[2]}개 메뉴")
    print(f"   🔺 [Case 3] 3개 누락 (전체 추정)    : {counts[3]}개 메뉴")
    print(f"   🧀 [Bonus]  포화지방 추가 보정      : {counts['sat']}개 메뉴")
    print("-" * 50)

if __name__ == '__main__':
    smart_fill()