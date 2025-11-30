import pandas as pd
from bs4 import BeautifulSoup
import os
import re
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 설정 파일 로드
try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    # 설정 파일이 없을 경우 기본 경로 사용
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

INPUT_HTML_FILE = os.path.join(DATA_RAW_DIR, 'lotteria_raw.html')
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'lotteria_products.csv')

def clean_number(text):
    """
    텍스트에서 숫자만 추출합니다.
    예: "12(23%)" -> 12.0
    예: "1g 미만" -> 0.0
    예: "684kcal ~ 1,370kcal" -> 684.0 (세트의 경우 최소값 기준)
    """
    if not text:
        return 0.0
    
    text = text.replace(',', '').strip()
    
    if '미만' in text:
        return 0.0
    
    # 범위(~)가 있는 경우 앞의 숫자만 가져옴 (최소 칼로리 기준)
    if '~' in text:
        text = text.split('~')[0]

    # 숫자와 소수점만 추출
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        return float(match.group(1))
    return 0.0

def parse_lotteria_html():
    print(f"📂 롯데리아 HTML 파싱 시작: {INPUT_HTML_FILE}")
    
    if not os.path.exists(INPUT_HTML_FILE):
        print("❌ 오류: HTML 파일이 없습니다. 'data_raw/lotteria_raw.html' 파일을 생성해주세요.")
        return

    with open(INPUT_HTML_FILE, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.select_one('table')
    
    if not table:
        print("❌ 테이블을 찾을 수 없습니다.")
        return

    products = []
    
    # tbody 별로 (버거세트, 버거메뉴, 디저트 등) 처리
    tbodies = table.select('tbody')
    
    for tbody in tbodies:
        rows = tbody.select('tr')
        category_name = "기타"
        
        for i, row in enumerate(rows):
            cols = row.select('td')
            
            # 카테고리 가져오기 (rowspan이 있는 첫 번째 행 처리)
            col_offset = 0
            if i == 0 and len(cols) >= 11:
                # 첫 번째 td가 카테고리일 가능성이 높음
                category_name = cols[0].text.strip().replace('\n', ' ')
                col_offset = 1 
            
            # 데이터 추출 (인덱스는 col_offset을 기준으로 계산)
            try:
                # 제품명 (Name Index)
                name_idx = 0 + col_offset
                menu_name = cols[name_idx].text.strip()
                
                # 알레르기 (Allergens Index)
                allergy_idx = 1 + col_offset
                allergens = cols[allergy_idx].text.strip()
                
                # 중량(g) : 2 + col_offset
                # 열량(kcal) : 3 + col_offset
                # 단백질(g) : 4 + col_offset
                # 나트륨(mg) : 5 + col_offset
                # 당류(g) : 6 + col_offset
                # 포화지방(g) : 7 + col_offset
                # 카페인(mg) : 8 + col_offset

                calories = clean_number(cols[3 + col_offset].text)
                protein = clean_number(cols[4 + col_offset].text)
                sodium = clean_number(cols[5 + col_offset].text)
                sugars = clean_number(cols[6 + col_offset].text)
                saturated_fat = clean_number(cols[7 + col_offset].text)
                
                # 카페인 (없는 경우도 있음)
                caffeine_text = cols[8 + col_offset].text if len(cols) > (8 + col_offset) else "0"
                caffeine = clean_number(caffeine_text)

                # DB 스키마에 맞지 않는 항목은 0으로 임시 처리
                product = {
                    'store_name': 'Lotteria',
                    'menu_name': menu_name,
                    'category': category_name,
                    'calories': calories,
                    'protein': protein,
                    'fat': 0.0, # 표에 없음
                    'saturated_fat': saturated_fat,
                    'trans_fat': 0.0, # 표에 없음
                    'cholesterol': 0.0, # 표에 없음
                    'sodium': sodium,
                    'carbs': 0.0, # 표에 없음
                    'sugars': sugars,
                    'caffeine': caffeine,
                    'allergens_scraped': allergens
                }
                
                products.append(product)
                # print(f"✅ 추출: {menu_name} ({category_name})")

            except IndexError:
                # 데이터 행의 길이가 맞지 않아 발생하는 오류는 무시
                continue

    # CSV 저장
    if products:
        df = pd.DataFrame(products)
        
        # 컬럼 순서 정렬 (DB 스키마 기준)
        columns = [
            'store_name', 'menu_name', 'category', 'calories', 'carbs', 'sugars', 
            'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
            'sodium', 'caffeine', 'allergens_scraped'
        ]
        
        # 누락된 컬럼 처리
        for col in columns:
            if col not in df.columns:
                df[col] = 0.0 if col != 'allergens_scraped' and col != 'category' else ''

        df.to_csv(OUTPUT_CSV_FILE, index=False, columns=columns, encoding='utf-8-sig')
        print(f"\n🎉 롯데리아 데이터 변환 완료!")
        print(f"   - 총 메뉴 수: {len(df)}개")
        print(f"   - 저장 위치: {OUTPUT_CSV_FILE}")
    else:
        print("⚠️ 추출된 데이터가 없습니다.")

if __name__ == '__main__':
    parse_lotteria_html()