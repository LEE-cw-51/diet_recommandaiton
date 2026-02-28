import pandas as pd
import os
import glob
import sys

# 프로젝트 루트 경로 설정 (기존과 동일)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    # 스크립트 위치(data/) 기준: ../data_raw
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

# 최종 저장될 파일 경로 (data_raw 폴더에 저장)
FINAL_DB_FILE = os.path.join(DATA_RAW_DIR, 'final_nutrition_db.csv')

# 🎯 [수정된 부분] 파일 검색 패턴: data_raw 내의 'franchise' 폴더 지정
TARGET_SUBFOLDER = 'franchise'
TARGET_FILE_PATTERN = os.path.join(DATA_RAW_DIR, TARGET_SUBFOLDER, '*_products.csv')

# DB 표준 스키마
STANDARD_COLUMNS = [
    'store_name', 'menu_name', 'category', 'price', 
    'calories', 'protein', 'fat', 'carbs', 'sugars', 'sodium', 
    'saturated_fat', 'trans_fat', 'cholesterol', 'caffeine', 'allergens_scraped'
]

def merge_all_data():
    print("================================================")
    print(f" 🚀 [최종 단계] 통합 데이터베이스 구축 시작 (경로: {TARGET_SUBFOLDER})")
    print("================================================\n")
    
    # 1. 대상 경로에서 모든 파일 목록 확보
    csv_files = glob.glob(TARGET_FILE_PATTERN)

    if not csv_files:
        print(f"❌ 오류: 병합할 파일(*_products.csv)이 '{TARGET_SUBFOLDER}' 폴더에 없습니다.")
        return

    all_dataframes = []

    print(f"📂 총 {len(csv_files)}개의 데이터 파일을 발견했습니다.\n")

    # 2. 파일 읽기 및 표준화
    for f in csv_files:
        file_name = os.path.basename(f)
        try:
            df = pd.read_csv(f, encoding='utf-8-sig')
            
            # 컬럼 표준화 및 정렬 (향후 데이터 추가 대비)
            for col in STANDARD_COLUMNS:
                if col not in df.columns:
                    df[col] = '' if col in ['allergens_scraped', 'category'] else 0.0
            
            df = df[STANDARD_COLUMNS]
            
            all_dataframes.append(df)
            print(f"   ✅ 병합 성공: {file_name:<25} (메뉴 {len(df):>3}개)")
            
        except Exception as e:
            print(f"   ❌ 병합 실패: {file_name}. 오류: {e}")

    # 3. 최종 병합 및 저장
    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        final_df.to_csv(FINAL_DB_FILE, index=False, encoding='utf-8-sig')
        
        print("\n================================================")
        print(f"🎉 [성공] 7개 프랜차이즈 DB 통합 완료!")
        print(f"💾 최종 파일: {FINAL_DB_FILE}")
        print(f"📊 총 메뉴 수: {len(final_df)}개")
        print("================================================")
    else:
        print("⚠️ 병합할 유효한 데이터가 없습니다.")


if __name__ == '__main__':
    merge_all_data()