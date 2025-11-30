import pandas as pd
import os
import glob
import re
from bs4 import BeautifulSoup
import sys

# 프로젝트 루트 경로 설정 (상위 폴더 접근용)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 설정 파일 로드 시도
try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    # 설정 파일이 없을 경우 기본 경로 사용
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

# CSV 파일 경로
OUTPUT_CSV_FILE = os.path.join(DATA_RAW_DIR, 'burgerking_products.csv')

# 영양소 이름과 DB 컬럼명 매핑
NUTRITION_KEYWORDS = {
    '열량': 'calories', '탄수화물': 'carbs', '당류': 'sugars', '단백질': 'protein', 
    '지방': 'fat', '포화지방': 'saturated_fat', '트랜스지방': 'trans_fat', 
    '콜레스테롤': 'cholesterol', '나트륨': 'sodium'
}

def extract_data_from_local_html(file_path):
    """로컬 HTML 파일에서 메뉴명, 영양소, 알레르기 정보를 추출합니다."""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"❌ 파일이 없습니다: {file_path}")
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 파일명에서 메뉴명 추출 (예: debug_bk_modal_와퍼.html -> 와퍼)
    filename = os.path.basename(file_path)
    menu_name_raw = filename.replace('debug_bk_modal_', '').replace('.html', '')
    menu_name = menu_name_raw.replace('_', ' ')
    
    product_data = {
        'menu_name': menu_name
    }

    # 1. 모달 컨텐츠 찾기
    container = soup.select_one('.pop_cont')
    if not container:
        return product_data

    # 2. 영양 성분 추출: 테이블 파싱 (Thead 기반)
    tables = container.select('table')
    
    for table in tables:
        # 헤더(thead) 분석
        headers = [th.text.strip().replace('\n', '').replace(' ', '') for th in table.select('thead th')]
        
        # 헤더가 있는 경우 (영양성분 테이블)
        if headers:
            col_map = {}
            for idx, h in enumerate(headers):
                for key, db_col in NUTRITION_KEYWORDS.items():
                    if key in h:
                        col_map[idx] = db_col
                        break
            
            # 데이터(tbody) 추출
            rows = table.select('tbody tr')
            for row in rows:
                cells = row.select('td')
                
                # 데이터 셀 개수 보정 (첫 열이 이름인 경우 등)
                offset = 0
                if len(cells) < len(headers): 
                    offset = 1 

                for col_idx, db_col in col_map.items():
                    cell_index = col_idx - offset
                    
                    if 0 <= cell_index < len(cells):
                        val_text = cells[cell_index].text.strip()
                        # 숫자만 추출 (괄호 등 제거)
                        val_match = re.match(r'([\d.]+)', val_text)
                        if val_match:
                            product_data[db_col] = float(val_match.group(1))

        # 헤더가 없는 경우 (알레르기 테이블 가능성)
        else:
            rows = table.select('tbody tr')
            for row in rows:
                cols = row.select('td')
                if cols:
                    text_val = cols[0].text.strip()
                    # 알레르기 관련 키워드가 있으면 저장
                    if any(x in text_val for x in ['밀', '대두', '우유', '난류', '쇠고기']):
                        product_data['allergens_scraped'] = text_val

    # 3. 알레르기 정보 2차 확인 (텍스트 파싱)
    if 'allergens_scraped' not in product_data:
        full_text = container.get_text(separator=' | ', strip=True)
        if "알레르기" in full_text:
             product_data['allergens_scraped'] = full_text[:500]

    return product_data

def fill_nutrition_from_html():
    print(f"📂 데이터 폴더: {DATA_RAW_DIR}")
    
    # 1. 기존 CSV 파일 로드
    if not os.path.exists(OUTPUT_CSV_FILE):
        print(f"❌ 오류: 기존 CSV 파일({OUTPUT_CSV_FILE})을 찾을 수 없습니다.")
        print("   먼저 크롤러(burgerking_crawler.py)를 실행해 CSV를 생성해야 합니다.")
        return

    df = pd.read_csv(OUTPUT_CSV_FILE, encoding='utf-8-sig')
    print(f"📊 기존 데이터 로드 완료: {len(df)}개 메뉴")

    # 2. 모든 디버그 HTML 파일 찾기
    html_pattern = os.path.join(DATA_RAW_DIR, "debug_bk_modal_*.html")
    html_files = glob.glob(html_pattern)
    
    if not html_files:
        print(f"⚠️ 경고: '{html_pattern}' 패턴에 맞는 HTML 파일이 없습니다.")
        return

    print(f"📄 디버그 HTML 파일 {len(html_files)}개 발견. 분석 시작...")

    update_count = 0
    
    # 3. HTML 파일 순회하며 데이터 추출 및 병합
    for html_file in html_files:
        extracted_data = extract_data_from_local_html(html_file)
        
        if extracted_data:
            menu_name = extracted_data['menu_name']
            
            # 메뉴명이 일치하는 행 찾기
            # (공백 제거 등 정규화하여 비교 정확도 향상)
            mask = df['menu_name'].apply(lambda x: x.replace(' ', '') == menu_name.replace(' ', ''))
            
            if mask.any():
                # 추출된 영양소 및 알레르기 데이터로 덮어쓰기
                for key, val in extracted_data.items():
                    if key in df.columns and key != 'menu_name': 
                        df.loc[mask, key] = val
                update_count += 1
                print(f"   ✅ 업데이트 완료: {menu_name}")
            else:
                print(f"   ⚠️ 매칭 실패 (CSV에 없음): {menu_name}")
            
    # 4. 수정된 DataFrame을 CSV로 저장
    df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
    print(f"\n🎉 데이터 덮어쓰기 완료!")
    print(f"   - 총 업데이트된 메뉴: {update_count}개")
    print(f"   - 저장된 파일: {OUTPUT_CSV_FILE}")

if __name__ == '__main__':
    fill_nutrition_from_html()