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

INPUT_EXCEL_FILE = os.path.join(DATA_RAW_DIR, 'momstouch_raw.xlsx')
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'momstouch_products.csv')

# Excel 원본 컬럼명과 DB 목표 컬럼명 매핑
COLUMN_MAPPING = {
    '제품명': 'menu_name',
    '열량(Kcal)': 'calories',
    '단백질(g)': 'protein',
    '지방(g)': 'fat',
    '포화지방(g)': 'saturated_fat',
    '트랜스지방(g)': 'trans_fat',
    '콜레스테롤(mg)': 'cholesterol',
    '나트륨(mg)': 'sodium',
    '탄수화물(g)': 'carbs',
    '당류(g)': 'sugars',
    '알레르기 유발성분': 'allergens_scraped'
}

def clean_and_format_momstouch_data():
    print(f"📂 맘스터치 Excel 데이터 로드 시작: {INPUT_EXCEL_FILE}")
    
    if not os.path.exists(INPUT_EXCEL_FILE):
        print("❌ 오류: Excel 원본 파일이 없습니다.")
        print("   'momstouch_raw.xlsx' 파일을 'data_raw' 폴더에 생성해주세요.")
        return

    # 1. Excel 파일 로드
    try:
        # 모든 데이터를 문자열로 로드하여 정리 용이하게 함
        df = pd.read_excel(INPUT_EXCEL_FILE, dtype=str)
    except Exception as e:
        print(f"❌ Excel 파일 로드 중 오류 발생: {e}")
        return

    # 2. 컬럼명 매핑 및 정리
    df.rename(columns=COLUMN_MAPPING, inplace=True)
    
    # 3. 필수 컬럼 확인 및 데이터 클리닝
    required_cols = list(COLUMN_MAPPING.values())
    
    # 데이터베이스에 필요한 컬럼이 없으면 초기화
    for col in ['store_name', 'price', 'category']:
        if col not in df.columns:
            df[col] = ''
    
    df['store_name'] = 'Momstouch'
    df['price'] = 0 
    df['category'] = '외식/프랜차이즈' 

    # 숫자형 데이터 정리
    for col in required_cols:
        if col in ['menu_name', 'allergens_scraped']: continue
        if col not in df.columns:
            df[col] = 0.0 
            continue
            
        # 데이터 정리: 쉼표 제거, 괄호 안의 % 제거 등
        # 예: "15(2%)" -> "15", "1,200" -> "1200"
        if df[col].dtype == object:
            df[col] = df[col].str.replace(r'\(.*?\)', '', regex=True) 
            df[col] = df[col].str.replace(',', '', regex=False)
        
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # 4. 최종 CSV 저장
    final_cols = [
        'store_name', 'menu_name', 'category', 'price', 'calories', 'carbs', 'sugars', 
        'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
        'sodium', 'allergens_scraped'
    ]
    
    # 없는 컬럼은 빈 값으로 채워서 구조 맞추기
    df = df.reindex(columns=final_cols, fill_value='')

    df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 맘스터치 데이터 클리닝 및 CSV 변환 완료!")
    print(f"   - 총 메뉴 수: {len(df)}개")
    print(f"   - 저장 위치: {OUTPUT_CSV_FILE}")

if __name__ == '__main__':
    clean_and_format_momstouch_data()