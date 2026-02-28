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

# -----------------------------------------------------------
HTML_FILENAME = 'shuttle_momstouch_price.html'
CSV_FILENAME = 'momstouch_products.csv'
# -----------------------------------------------------------

def parse_shuttle_html(html_file):
    """셔틀 딜리버리 HTML에서 메뉴명과 가격을 추출합니다."""
    html_path = os.path.join(DATA_RAW_DIR, html_file)
    print(f"📂 HTML 파일 읽기 시작: {html_path}")
    
    if not os.path.exists(html_path):
        print(f"❌ 오류: 파일을 찾을 수 없습니다 -> {html_path}")
        return {}

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    price_dict = {}
    items = soup.select('div.menuitem')
    
    for item in items:
        try:
            title_tag = item.select_one('.itemtitle')
            price_tag = item.select_one('.price')
            
            if title_tag and price_tag:
                name = title_tag.text.strip()
                price_text = price_tag.text.strip()
                price = int(re.sub(r'[^\d]', '', price_text))
                
                # 매칭 정확도를 높이기 위해 공백 제거 후 키로 사용
                clean_name = name.replace(' ', '')
                price_dict[clean_name] = price
                
        except Exception:
            continue
            
    print(f"   ✅ 총 {len(price_dict)}개 메뉴의 가격 정보 추출 완료 (세트 포함)")
    return price_dict

def update_csv_prices(target_franchise):
    """추출한 가격 정보를 기존 CSV 파일에 업데이트합니다."""
    real_prices = parse_shuttle_html(HTML_FILENAME)
    
    if not real_prices: return

    csv_path = os.path.join(DATA_RAW_DIR, CSV_FILENAME)
    df = pd.read_csv(csv_path)

    updated_count = 0
    
    # ------------------------------------------------------------------
    # [핵심 로직] "단품" 가격만 필터링하여 CSV 메뉴명과 매칭 시도
    # ------------------------------------------------------------------
    
    # 1. HTML에서 추출된 메뉴를 순회하며 "단품" 메뉴 가격만 정리
    single_item_prices = {}
    for html_key, price in real_prices.items():
        if "단품" in html_key:
            # HTML 키에서 '단품'을 제거한 후 순수 메뉴명으로 매핑 (예: "싸이버거단품" -> "싸이버거")
            core_name = html_key.replace('단품', '')
            single_item_prices[core_name] = price
            
    if not single_item_prices:
        print("❌ 오류: HTML에서 '단품' 메뉴가 발견되지 않았습니다. 매칭을 시도할 가격 데이터가 없습니다.")
        return
        
    print(f"   ✅ [단품 전용 가격 DB] {len(single_item_prices)}개 단품 메뉴 가격 확보.")

    # 2. CSV 메뉴를 순회하며 단품 가격으로 업데이트
    for idx, row in df.iterrows():
        # CSV 메뉴명도 공백 제거 (예: '슈퍼싸이버거' -> '슈퍼싸이버거')
        csv_menu_key = str(row['menu_name']).replace(' ', '')
        
        # CSV 키가 단품 DB에 있는지 확인하여 가격 업데이트
        if csv_menu_key in single_item_prices:
            df.at[idx, 'price'] = single_item_prices[csv_menu_key]
            updated_count += 1
        
        # CSV 메뉴명에 '버거'가 포함되어 있고, 단품 DB의 키가 CSV 키의 일부인 경우 (유연성 확보)
        elif '버거' in csv_menu_key and csv_menu_key in single_item_prices:
             df.at[idx, 'price'] = single_item_prices[csv_menu_key]
             updated_count += 1


    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n🎉 [{target_franchise}] 업데이트 완료!")
    print(f"   - 총 {updated_count}개 단품 메뉴 가격 변경됨.")


if __name__ == '__main__':
    update_csv_prices('Momstouch')