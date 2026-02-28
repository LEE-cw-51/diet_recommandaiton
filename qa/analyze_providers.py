import pandas as pd
import os
import sys

# --- 1. 설정 ---
# 프로젝트의 루트 디렉토리를 기준으로 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ⭐ 파일 경로를 'data/processed'로 지정합니다. ⭐
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

FILE_NAME = 'final_cleaned_nutrition_db.csv'
FILE_PATH = os.path.join(PROCESSED_DIR, FILE_NAME)

PROVIDER_COLUMN = 'PROVIDER_NAME'
OUTPUT_FILE = 'full_provider_list.csv'
OUTPUT_PATH = os.path.join(PROCESSED_DIR, OUTPUT_FILE)
# -----------------------------

def analyze_all_providers():
    """
    정리된 영양 데이터에서 모든 유니크 제공업체 목록과 개수를 추출하여 CSV로 저장합니다.
    """
    
    print(f"✅ 분석 파일 경로: {FILE_PATH}")
    
    if not os.path.exists(FILE_PATH):
        print(f"❌ 오류: 분석 파일이 없습니다. '{FILE_NAME}'을 '{PROCESSED_DIR}' 폴더에 두었는지 확인하십시오.")
        sys.exit(1)

    try:
        # 1. 파일 로드 (깨끗하게 정리된 파일)
        df = pd.read_csv(FILE_PATH, encoding='utf-8-sig', low_memory=False)

        # 2. 필수 컬럼 확인
        if PROVIDER_COLUMN not in df.columns:
            print(f"❌ 오류: 데이터프레임에 필수 컬럼 '{PROVIDER_COLUMN}'이 없습니다. 컬럼명을 다시 확인하십시오.")
            print(f"현재 컬럼명: {df.columns.tolist()}")
            sys.exit(1)

        # 3. 전체 빈도 분석
        provider_counts = df[PROVIDER_COLUMN].value_counts()
        total_unique_providers = len(provider_counts)

        # 4. 결과를 DataFrame으로 변환하여 CSV로 저장
        df_providers = provider_counts.reset_index()
        df_providers.columns = [PROVIDER_COLUMN, 'DATA_COUNT']
        
        # 파일이 저장될 위치에 저장 (data/processed/full_provider_list.csv)
        df_providers.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        
        print(f"\n--- 📊 전체 제공업체 목록 추출 완료 ---")
        print(f"총 유니크 제공업체/제조사 수: {total_unique_providers}개")
        print(f"💾 전체 목록은 '{OUTPUT_FILE}' 파일로 저장되었습니다.")
        print(f"   저장 위치: {OUTPUT_PATH}")
        print("\n이 파일을 열어 'DATA_COUNT'가 높은 순서대로 크롤링할 프랜차이즈 목록을 확정하십시오.")
        
    except Exception as e:
        print(f"분석 중 치명적 오류 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(PROCESSED_DIR):
        print(f"❌ 데이터 폴더가 없습니다. {PROCESSED_DIR} 폴더를 생성하고 파일을 넣어주세요.")
        sys.exit(1)
        
    analyze_all_providers()