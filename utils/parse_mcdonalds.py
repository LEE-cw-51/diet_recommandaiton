import pandas as pd
from bs4 import BeautifulSoup
import os
import re
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

INPUT_HTML_FILE = os.path.join(DATA_RAW_DIR, 'mcdonalds_raw.html')
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'mcdonalds_products.csv')

def clean_mcdonalds_number(text):
    """
    텍스트에서 숫자만 추출합니다.
    예: "5.0g(33%)" -> 5.0
    예: "677mg(34%)" -> 677.0
    """
    if not text or text.strip() == '-':
        return 0.0
    
    # 괄호와 그 안의 내용 제거 (예: (33%))
    text = re.sub(r'\(.*?\)', '', text)
    # 단위(g, mg, kcal, ml) 및 쉼표 제거
    text = re.sub(r'[a-zA-Z가-힣,]', '', text)
    
    try:
        return float(text.strip())
    except ValueError:
        return 0.0

def parse_mcdonalds_html():
    print(f"📂 맥도날드 HTML 파싱 시작: {INPUT_HTML_FILE}")
    
    if not os.path.exists(INPUT_HTML_FILE):
        print("❌ 오류: HTML 파일이 없습니다. 'data_raw/mcdonalds_raw.html' 파일을 생성해주세요.")
        return

    with open(INPUT_HTML_FILE, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 맥도날드 페이지 구조: div.w-full 안에 h3(카테고리)와 table이 있음
    sections = soup.select('div.w-full')
    
    products = []
    
    for section in sections:
        # 1. 카테고리 확인
        header = section.select_one('h3')
        if not header:
            continue
            
        category_name = header.text.strip()
        
        # ❌ 제외 조건: "세트"가 포함된 카테고리는 건너뜀 (세트메뉴, 라지 세트메뉴)
        if "세트" in category_name:
            # 해피밀은 '해피밀'이라는 이름으로 되어있으나 구성이 세트일 수 있음. 
            # 하지만 요청하신 '세트메뉴', '라지 세트메뉴' 섹션은 명확히 제외됨.
            # 만약 해피밀도 제외하고 싶다면 조건을 추가하세요.
            # 여기서는 명시된 '세트메뉴', '라지 세트메뉴' 텍스트가 포함된 헤더를 제외합니다.
            if category_name in ["세트메뉴", "라지 세트메뉴"]:
                print(f"   ⏭️ 제외된 카테고리: {category_name}")
                continue

        # 2. 테이블 데이터 추출
        table = section.select_one('table')
        if not table:
            continue
            
        rows = table.select('tbody tr')
        for row in rows:
            try:
                # th: 메뉴명, td: 영양소 값들
                menu_name_tag = row.select_one('th')
                if not menu_name_tag: continue
                
                menu_name = menu_name_tag.text.strip()
                
                cols = row.select('td')
                # HTML 테이블 순서: 중량, 열량, 포화지방, 당, 단백질, 나트륨, 카페인
                # 인덱스:       0     1      2        3     4       5       6
                
                if len(cols) < 7: continue

                calories = clean_mcdonalds_number(cols[1].text)
                saturated_fat = clean_mcdonalds_number(cols[2].text)
                sugars = clean_mcdonalds_number(cols[3].text)
                protein = clean_mcdonalds_number(cols[4].text)
                sodium = clean_mcdonalds_number(cols[5].text)
                caffeine = clean_mcdonalds_number(cols[6].text)

                # DB 스키마 매핑
                product = {
                    'store_name': 'McDonalds',
                    'menu_name': menu_name,
                    'category': category_name,
                    'price': 0, # 가격 정보 없음
                    'calories': calories,
                    'protein': protein,
                    'fat': 0.0, # 총 지방 정보 없음
                    'saturated_fat': saturated_fat,
                    'trans_fat': 0.0, # 트랜스지방 정보 없음
                    'cholesterol': 0.0, # 콜레스테롤 정보 없음
                    'sodium': sodium,
                    'carbs': 0.0, # 탄수화물 정보 없음
                    'sugars': sugars,
                    'caffeine': caffeine,
                    'allergens_scraped': '' # 테이블에 알레르기 정보 없음
                }
                
                products.append(product)
                
            except Exception as e:
                print(f"⚠️ 파싱 에러 ({menu_name}): {e}")
                continue

    # CSV 저장
    if products:
        df = pd.DataFrame(products)
        
        columns = [
            'store_name', 'menu_name', 'category', 'price', 'calories', 'carbs', 'sugars', 
            'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
            'sodium', 'caffeine', 'allergens_scraped'
        ]
        
        # 없는 컬럼은 0.0 또는 빈 문자열로 채움
        for col in columns:
            if col not in df.columns:
                df[col] = 0.0 if col != 'allergens_scraped' else ''

        df.to_csv(OUTPUT_CSV_FILE, index=False, columns=columns, encoding='utf-8-sig')
        print(f"\n🎉 맥도날드 데이터 변환 완료!")
        print(f"   - 총 메뉴 수: {len(df)}개")
        print(f"   - 저장 위치: {OUTPUT_CSV_FILE}")
    else:
        print("⚠️ 추출된 데이터가 없습니다.")

if __name__ == '__main__':
    parse_mcdonalds_html()