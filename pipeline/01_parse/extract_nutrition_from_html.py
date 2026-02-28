import pandas as pd
import os
import glob
import re
from bs4 import BeautifulSoup
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 설정 파일 로드 (경로 설정)
try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

# 대상 CSV 파일 경로
CSV_FILE_PATH = os.path.join(DATA_RAW_DIR, 'burgerking_products.csv')

# 영양소 헤더 매핑 (HTML 헤더 이름 -> DB 컬럼 이름)
NUTRITION_MAP = {
    '열량': 'calories',
    '당류': 'sugars', '당': 'sugars',
    '단백질': 'protein',
    '포화지방': 'saturated_fat',
    '나트륨': 'sodium',
    '카페인': 'caffeine'
    # 탄수화물, 지방 등은 표에 없으면 0으로 남음
}

def parse_html_file(file_path):
    """HTML 파일 하나를 파싱하여 메뉴별 영양소 정보 리스트를 반환합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 파일 읽기 실패 ({os.path.basename(file_path)}): {e}")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    extracted_items = []

    # 1. 영양성분 테이블 찾기
    tables = soup.select('table')
    
    for table in tables:
        # 헤더 분석 (컬럼 인덱스 찾기)
        headers = [th.text.strip().replace('\n', '').replace(' ', '') for th in table.select('thead th')]
        
        # 영양소 컬럼 인덱스 맵핑
        col_indices = {}
        for idx, header in enumerate(headers):
            for key, db_col in NUTRITION_MAP.items():
                if key in header:
                    col_indices[idx] = db_col
                    break
        
        if not col_indices:
            continue # 영양소 테이블이 아님 (알레르기 테이블 등)

        # 2. 데이터 행(Row) 분석
        rows = table.select('tbody tr')
        for row in rows:
            # 제품명 찾기 (보통 첫 번째 th나 td에 있음)
            name_elem = row.select_one('th') or row.select_one('td')
            if not name_elem: continue
            
            menu_name = name_elem.text.strip()
            
            # 해당 행의 데이터 셀(td) 가져오기
            cells = row.select('td')
            
            # 데이터 저장소 초기화
            item_data = {
                'menu_name': menu_name,
                'calories': 0.0, 'carbs': 0.0, 'sugars': 0.0, 'protein': 0.0, 
                'fat': 0.0, 'saturated_fat': 0.0, 'trans_fat': 0.0, 
                'cholesterol': 0.0, 'sodium': 0.0
            }
            
            # 셀 데이터 매핑
            # (헤더 개수와 셀 개수가 다를 수 있음. 제품명 컬럼을 제외하고 계산)
            # 보통 제품명(th) + 값(td, td...) 구조임
            
            for header_idx, db_col in col_indices.items():
                # 제품명 컬럼(인덱스 0)을 제외하고 매핑해야 함 -> index - 1
                cell_idx = header_idx - 1
                
                if 0 <= cell_idx < len(cells):
                    val_text = cells[cell_idx].text.strip()
                    # 숫자만 추출 (괄호 안의 % 수치 제거)
                    # 예: "271(14)" -> 271
                    val_match = re.match(r'([\d.]+)', val_text)
                    if val_match:
                        item_data[db_col] = float(val_match.group(1))
            
            extracted_items.append(item_data)

    # 3. 알레르기 정보 텍스트 추출 (보너스)
    allergens = ""
    pop_cont = soup.select_one('.pop_cont')
    if pop_cont:
        full_text = pop_cont.get_text(separator=' ', strip=True)
        if "알레르기" in full_text:
            # 간단하게 텍스트 일부만 가져옴 (정교한 파싱은 어려움)
            allergens = full_text[:300]

    # 모든 아이템에 알레르기 정보 공통 적용 (모달 하나에 여러 메뉴가 있는 경우 애매하지만 일단 넣음)
    for item in extracted_items:
        item['allergens_scraped'] = allergens

    return extracted_items

def merge_html_data_to_csv():
    print(f"📂 HTML 파일 검색 경로: {DATA_RAW_DIR}")
    
    # 1. 기존 CSV 로드 (없으면 생성)
    if os.path.exists(CSV_FILE_PATH):
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8-sig')
        print(f"📊 기존 CSV 로드 완료: {len(df)}개 메뉴")
    else:
        print("⚠️ 기존 CSV가 없습니다. 새 파일 생성 모드.")
        df = pd.DataFrame(columns=['store_name', 'menu_name', 'price', 'calories', 'protein', 'sodium', 'sugars', 'saturated_fat', 'allergens_scraped'])

    # 2. 모든 HTML 파일 찾기
    html_files = glob.glob(os.path.join(DATA_RAW_DIR, "*.html"))
    print(f"📄 처리할 HTML 파일: {len(html_files)}개")

    updated_count = 0
    
    for html_file in html_files:
        extracted_list = parse_html_file(html_file)
        
        for data in extracted_list:
            name = data['menu_name']
            
            # CSV에서 메뉴명 매칭 (공백 제거 후 비교)
            # '와퍼 세트' vs '와퍼세트' 같은 차이를 줄이기 위함
            match_mask = df['menu_name'].str.replace(' ', '') == name.replace(' ', '')
            
            if match_mask.any():
                # 기존 행 업데이트
                for col, val in data.items():
                    if col in df.columns and col != 'menu_name':
                        df.loc[match_mask, col] = val
                updated_count += 1
                # print(f"   ✅ 업데이트: {name}")
            else:
                # 신규 메뉴 추가 (선택 사항: 원치 않으면 주석 처리)
                new_row = data.copy()
                new_row['store_name'] = 'BurgerKing'
                new_row['price'] = 0 # 가격 정보는 HTML에 없음
                # df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                # print(f"   ➕ 신규 추가: {name}")
                pass

    # 3. 저장
    df.to_csv(CSV_FILE_PATH, index=False, encoding='utf-8-sig')
    print(f"\n🎉 작업 완료! 총 {updated_count}개 메뉴 데이터가 업데이트되었습니다.")
    print(f"💾 저장 경로: {CSV_FILE_PATH}")

if __name__ == '__main__':
    merge_html_data_to_csv()