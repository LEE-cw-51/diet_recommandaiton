import pandas as pd
import os
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

INPUT_EXCEL_FILE = os.path.join(DATA_RAW_DIR, 'preps_raw.xlsx')
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'preps_products.csv')

# Excel 헤더 -> DB 컬럼 매핑
COLUMN_MAPPING = {
    '제품명': 'menu_name',
    '열량(kcal)': 'calories',
    '탄수화물(g)': 'carbs',
    '단백질(g)': 'protein',
    '지방(g)': 'fat'
}

def clean_preps_data():
    print(f"📂 프레퍼스 데이터 변환 시작: {INPUT_EXCEL_FILE}")
    
    if not os.path.exists(INPUT_EXCEL_FILE):
        print("❌ 오류: 'data_raw/preps_raw.xlsx' 파일이 없습니다.")
        return

    try:
        # 문자열로 로드하여 데이터 정리 용이하게 함
        df = pd.read_excel(INPUT_EXCEL_FILE, dtype=str)
    except Exception as e:
        print(f"❌ 엑셀 로드 실패: {e}")
        return

    # 1. 컬럼명 변경
    df.rename(columns=COLUMN_MAPPING, inplace=True)

    # 2. 기본 정보 추가
    df['store_name'] = 'Preppers'
    df['category'] = '건강식/샐러드'
    df['price'] = 0

    # 3. 없는 영양소 컬럼 0으로 초기화 (이미지에 없는 정보들)
    missing_cols = ['sugars', 'saturated_fat', 'trans_fat', 'cholesterol', 'sodium']
    for col in missing_cols:
        df[col] = 0.0
    
    df['allergens_scraped'] = ''

    # 4. 숫자 데이터 클리닝
    numeric_cols = ['calories', 'carbs', 'protein', 'fat']
    for col in numeric_cols:
        if col in df.columns:
            # 콤마 제거 및 숫자로 변환
            df[col] = df[col].str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # 5. 최종 저장
    final_cols = [
        'store_name', 'menu_name', 'category', 'price', 'calories', 'carbs', 'sugars', 
        'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
        'sodium', 'allergens_scraped'
    ]
    
    df = df.reindex(columns=final_cols, fill_value='')
    
    df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 프레퍼스 변환 완료!")
    print(f"   - 파일: {OUTPUT_CSV_FILE}")
    print(f"   - 메뉴 수: {len(df)}개")

if __name__ == '__main__':
    clean_preps_data()