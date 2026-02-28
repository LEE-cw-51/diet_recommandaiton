# check_standard_duplicates.py 파일 (최종적으로 코드가 실행될 내용)
import pandas as pd
import os
import sys

# --- 1. 설정 (사용자 지정 부분) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

FILE_NAMES = [
    'standard_nutrition_db_raw1.csv', 
    'standard_nutrition_db_raw2.csv', 
    'standard_nutrition_db_raw3.csv'
]

KEY_COLUMN = 'FOOD_CODE' 
# -----------------------------

def merge_and_clean_nutrition_data():
    """세 개의 CSV 파일을 통합하고, 'FOOD_CODE'를 기준으로 중복을 제거합니다."""
    all_data = []
    
    print("--- 📚 표준 영양 DB 통합 및 중복 제거 시작 ---")
    
    for filename in FILE_NAMES:
        filepath = os.path.join(RAW_DIR, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️ 경고: 파일을 찾을 수 없습니다: {filename}. 다음 파일로 넘어갑니다.")
            continue
            
        try:
            try:
                df = pd.read_csv(filepath, encoding='utf-8-sig', low_memory=False) 
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding='cp949', low_memory=False)
            
            if KEY_COLUMN not in df.columns:
                print(f"❌ 오류: {filename} 파일에 필수 컬럼 '{KEY_COLUMN}'이 없습니다. 컬럼명을 재확인하십시오.")
                continue

            df['Source_File'] = filename
            all_data.append(df)
            print(f"✅ {filename} 파일 로드 완료. ({len(df)} 행)")
            
        except Exception as e:
            print(f"❌ {filename} 로드 중 치명적 오류 발생: {e}")
            continue 

    if not all_data:
        print("\n로드된 데이터가 없어 통합을 진행할 수 없습니다. 파일을 확인하십시오.")
        return None

    combined_df = pd.concat(all_data, ignore_index=True)
    total_rows = len(combined_df)

    df_cleaned = combined_df.drop_duplicates(subset=[KEY_COLUMN], keep='first')
    
    duplicates_removed = total_rows - len(df_cleaned)
    
    print(f"\n--- 통합 결과 요약 ---")
    print(f"총 통합 행 개수: {total_rows}개")
    print(f"✅ '{KEY_COLUMN}' 기준 중복 제거된 행 개수: {duplicates_removed}개")
    print(f"✅ 최종 유니크(Unique) 데이터 개수: {len(df_cleaned)}개")

    CLEAN_CSV_PATH = os.path.join(RAW_DIR, 'final_cleaned_nutrition_db.csv')
    df_cleaned.to_csv(CLEAN_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"\n💾 정리된 최종 영양 데이터가 '{os.path.basename(CLEAN_CSV_PATH)}'에 저장되었습니다.")
    
    return df_cleaned

if __name__ == "__main__":
    if not os.path.exists(RAW_DIR):
        print(f"❌ 데이터 폴더가 없습니다. {RAW_DIR} 폴더를 생성하고 파일을 넣어주세요.")
        sys.exit(1)
        
    final_nutrition_df = merge_and_clean_nutrition_data()
    
    if final_nutrition_df is not None:
        print("\n--- 통합 및 중복 제거 완료 ---")
        print("이제 'final_cleaned_nutrition_db.csv' 파일을 사용하여 SQLite DB의 'nutrition' 테이블을 구축할 수 있습니다.")