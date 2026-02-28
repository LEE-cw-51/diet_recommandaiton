import pandas as pd
import os
import glob
import sys

# -----------------------------------------------------------
# [설정] 경로 및 파일명 설정
# -----------------------------------------------------------

# 현재 스크립트 위치의 부모 폴더(프로젝트 루트)를 기준으로 경로 설정
# 예: C:\Users\chanw\diet_recommendation
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. 읽어올 파일들이 있는 폴더 (입력)
# 경로: data/raw/franchise
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'raw', 'franchise')

# 2. 최종 저장될 파일 경로 (출력) -> 요청하신 processed 폴더로 변경
# 경로: data/processed
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'final_nutrition_db.csv')

# 3. 데이터베이스 표준 컬럼 (순서 및 항목 통일)
STANDARD_COLUMNS = [
    'store_name',       # 브랜드명
    'menu_name',        # 메뉴명
    'category',         # 카테고리
    'price',            # 가격
    'calories',         # 열량 (kcal)
    'protein',          # 단백질 (g)
    'fat',              # 지방 (g)
    'carbs',            # 탄수화물 (g)
    'sugars',           # 당류 (g)
    'sodium',           # 나트륨 (mg)
    'saturated_fat',    # 포화지방 (g)
    'trans_fat',        # 트랜스지방 (g)
    'cholesterol',      # 콜레스테롤 (mg)
    'caffeine',         # 카페인 (mg)
    'allergens_scraped' # 알레르기 정보
]

def merge_franchise_data():
    print("="*60)
    print(f"📂 입력 경로: {INPUT_DIR}")
    print(f"💾 출력 경로: {OUTPUT_DIR}")
    print("="*60)

    # 1. 파일 목록 가져오기
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 오류: 입력 폴더가 없습니다 -> {INPUT_DIR}")
        return

    csv_files = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    
    if not csv_files:
        print("❌ 오류: 폴더 안에 .csv 파일이 하나도 없습니다.")
        return

    print(f"📊 총 {len(csv_files)}개의 프랜차이즈 파일을 발견했습니다.\n")

    all_data = []

    # 2. 각 파일 읽어서 표준화
    for file_path in csv_files:
        filename = os.path.basename(file_path)
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # (1) 누락된 컬럼 0 또는 공란으로 채우기
            for col in STANDARD_COLUMNS:
                if col not in df.columns:
                    if col in ['category', 'allergens_scraped']:
                        df[col] = ""
                    else:
                        df[col] = 0.0
            
            # (2) 컬럼 순서 강제 통일
            df = df[STANDARD_COLUMNS]
            
            all_data.append(df)
            print(f"   ✅ 병합 성공: {filename:<25} (메뉴 {len(df):>3}개)")
            
        except Exception as e:
            print(f"   ❌ 병합 실패: {filename} - {e}")

    # 3. 최종 합치기 및 저장
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        
        # 저장 폴더(processed)가 없으면 생성
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        final_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        
        print("-" * 60)
        print(f"🎉 [완료] 7개 프랜차이즈 통합 성공!")
        print(f"   - 총 데이터 개수: {len(final_df)}개")
        print(f"   - 저장된 파일: {OUTPUT_FILE}")
        print("-" * 60)
    else:
        print("⚠️ 병합할 데이터가 없습니다.")

if __name__ == "__main__":
    merge_franchise_data()