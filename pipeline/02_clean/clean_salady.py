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

INPUT_EXCEL_FILE = os.path.join(DATA_RAW_DIR, 'salady_raw.xlsx')
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'salady_products.csv')

# Excel 원본 컬럼명과 DB 목표 컬럼명 매핑 (샐러디 원본 표에 맞춰 수정 필요)
# 파트너님이 Excel에 입력하신 컬럼명(한글)에 맞춰 매핑합니다. 
# 일반적인 샐러디 영양소 표를 기준으로 광범위하게 정의합니다.
COLUMN_MAPPING = {
    '제품명': 'menu_name',
    '열량': 'calories',
    '칼로리': 'calories',
    '탄수화물': 'carbs',
    '당류': 'sugars',
    '단백질': 'protein',
    '지방': 'fat',
    '포화지방': 'saturated_fat',
    '트랜스지방': 'trans_fat',
    '콜레스테롤': 'cholesterol',
    '나트륨': 'sodium',
    '알레르기': 'allergens_scraped'
}

def clean_salady_data():
    print(f"📂 샐러디 Excel 데이터 로드 시작: {INPUT_EXCEL_FILE}")
    
    if not os.path.exists(INPUT_EXCEL_FILE):
        print("❌ 오류: 'salady_raw.xlsx' 파일이 없습니다. 파일을 확인해주세요.")
        return

    # 1. Excel 파일 로드
    try:
        df = pd.read_excel(INPUT_EXCEL_FILE, dtype=str)
    except Exception as e:
        print(f"❌ Excel 파일 로드 중 오류 발생: {e}")
        return

    # 2. 컬럼명 매핑 및 정리
    # 띄어쓰기나 괄호가 다를 수 있으므로, 임시로 컬럼명 정규화 후 매핑 시도
    df.columns = df.columns.str.replace(r'[(\[].*?[)\]]', '', regex=True).str.replace(' ', '').str.strip()
    
    # DB 스키마에 맞게 이름 변경
    new_cols = {}
    for excel_col in df.columns:
        for kor_name, db_name in COLUMN_MAPPING.items():
            if kor_name == excel_col:
                new_cols[excel_col] = db_name
                break
    df.rename(columns=new_cols, inplace=True)
    
    # 3. 기본 정보 및 누락된 컬럼 처리
    df['store_name'] = 'Salady'
    df['price'] = 0 
    df['category'] = '건강식/샐러드'

    # 4. 숫자 데이터 클리닝 및 누락된 필수 컬럼 0으로 채우기
    final_cols = [
        'store_name', 'menu_name', 'category', 'price', 'calories', 'carbs', 'sugars', 
        'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
        'sodium', 'allergens_scraped'
    ]
    
    # 숫자형 데이터 정리 및 형 변환
    for col in final_cols:
        if col not in df.columns:
            df[col] = 0.0 if col not in ['store_name', 'menu_name', 'category', 'allergens_scraped'] else ''
        elif col not in ['menu_name', 'allergens_scraped', 'store_name', 'category']:
            df[col] = df[col].astype(str).str.replace(r'[a-zA-Z가-힣,\(\)\-]', '', regex=True).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # 5. 최종 CSV 저장
    df = df.reindex(columns=final_cols, fill_value='')

    df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 샐러디 데이터 변환 완료!")
    print(f"   - 총 메뉴 수: {len(df)}개")
    print(f"   - 저장 위치: {OUTPUT_CSV_FILE}")

if __name__ == '__main__':
    clean_salady_data()