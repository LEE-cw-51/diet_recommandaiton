import pandas as pd
import os
import glob

# --- 설정 ---

# 1. CSV 파일이 저장된 폴더 경로 (사용자 지정 경로)
DATA_RAW_PATH = 'C:/Users/chanw/diet_recommendation/data/raw'

# 2. 통합할 파일 이름 목록 (사용자가 업로드한 모든 파일 기준)
#    (이 목록에 있는 파일만 찾아서 합칩니다)
file_list = [
    'gs25_products_price.csv',
    'cu_products_price.csv',
    'seven_products_price.csv',
    'emart24_products_price.csv',
    'burgerking_shuttle_delivery_menu.csv',
    'mcdonalds_shuttle_delivery_menu.csv',
    'momstouch_shuttle_delivery_menu.csv',
    'lotteria_menu.csv'
]

# 3. 통합 파일 이름 (이 이름으로 저장됩니다)
OUTPUT_FILENAME = os.path.join(DATA_RAW_PATH, 'all_products_combined.csv')

# --- ---

def merge_csv_files():
    """
    지정된 폴더(DATA_RAW_PATH)에서 file_list에 명시된
    모든 CSV 파일을 찾아 하나의 파일로 통합합니다.
    """
    print(f"📁 데이터 통합 시작...")
    print(f"   대상 폴더: {DATA_RAW_PATH}")
    
    all_dataframes = []
    
    for filename in file_list:
        file_path = os.path.join(DATA_RAW_PATH, filename)
        
        # 파일이 존재하는지 확인
        if os.path.exists(file_path):
            try:
                # CSV 파일을 DataFrame으로 읽기
                df = pd.read_csv(file_path)
                print(f"   ✅ 로드 성공: {filename} (데이터 {len(df)}개)")
                all_dataframes.append(df)
            except Exception as e:
                print(f"   ❌ 로드 실패: {filename} | 오류: {e}")
        else:
            print(f"   ⚠️ 파일을 찾을 수 없습니다: {filename}")

    if not all_dataframes:
        print("\n❌ 통합할 데이터가 없습니다. 파일 이름이나 경로를 확인하세요.")
        return

    # 4. 모든 DataFrame을 하나로 합치기
    try:
        # ignore_index=True: 각 파일의 원래 인덱스를 무시하고 새 인덱스를 생성
        # sort=False: 불필요한 열 정렬 방지 (성능 향상)
        merged_df = pd.concat(all_dataframes, ignore_index=True, sort=False)
        print(f"\n📊 총 {len(merged_df)}개의 데이터로 통합 중...")

        # 5. 통합된 파일 저장
        # encoding='utf-8-sig'는 Excel에서 한글이 깨지지 않도록 보장합니다.
        merged_df.to_csv(OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
        
        print("\n" + "=" * 50)
        print(f"🎉 통합 완료!")
        print(f"   저장 위치: {OUTPUT_FILENAME}")
        print(f"   총 브랜드 수: {merged_df['brand_name'].nunique()}개")
        print(f"   총 메뉴 수: {len(merged_df)}개")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 통합 중 오류 발생: {e}")

if __name__ == "__main__":
    # 이 스크립트를 실행하기 전에 pandas가 설치되어 있어야 합니다.
    # (venv) pip install pandas
    merge_csv_files()