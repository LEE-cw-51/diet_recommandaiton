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
# [설정] 버거킹 전용 파일 설정
HTML_FILENAME = 'shuttle_burgerking_price.html'
CSV_FILENAME = 'burgerking_products.csv'
# -----------------------------------------------------------

def parse_burgerking_html(html_file):
    html_path = os.path.join(DATA_RAW_DIR, html_file)
    print(f"📂 버거킹 HTML 읽기: {html_path}")
    
    if not os.path.exists(html_path):
        print(f"❌ 오류: 파일 없음 -> {html_path}")
        return {}

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    price_dict = {}
    items = soup.select('div.menuitem')
    
    for item in items:
        try:
            title = item.select_one('.itemtitle').text.strip()
            price_str = item.select_one('.price').text.strip()
            price = int(re.sub(r'[^\d]', '', price_str))
            
            # 공백 제거 후 저장 (예: "와퍼 세트" -> "와퍼세트")
            clean_name = title.replace(' ', '')
            price_dict[clean_name] = price
        except:
            continue
            
    print(f"   ✅ 가격 정보 추출 완료: {len(price_dict)}개 메뉴")
    return price_dict

def update_burgerking_prices():
    real_prices = parse_burgerking_html(HTML_FILENAME)
    if not real_prices: return

    csv_path = os.path.join(DATA_RAW_DIR, CSV_FILENAME)
    df = pd.read_csv(csv_path)
    updated_count = 0
    
    print(f"   📊 매칭 시작 (대상: {len(df)}개 메뉴)...")

    for idx, row in df.iterrows():
        # CSV 메뉴명 (공백 제거)
        csv_name = str(row['menu_name']).replace(' ', '')
        
        # 1. 완전 일치 (Best)
        if csv_name in real_prices:
            df.at[idx, 'price'] = real_prices[csv_name]
            updated_count += 1
            continue

        # 2. 부분 일치 (단, '세트' 글자 유무가 같아야 함)
        for html_key, price in real_prices.items():
            # 세트 메뉴끼리만, 단품끼리만 매칭 (가격 왜곡 방지)
            if ('세트' in csv_name) == ('세트' in html_key):
                # 서로 이름이 포함되는 관계라면 매칭 (예: "갈릭불고기와퍼" <-> "갈릭불고기와퍼세트"는 위에서 걸러짐)
                if csv_name in html_key or html_key in csv_name:
                    # 이름 길이 차이가 너무 크지 않은 경우만 (오매칭 방지)
                    if abs(len(csv_name) - len(html_key)) < 4:
                        df.at[idx, 'price'] = price
                        updated_count += 1
                        break

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"🎉 [버거킹] 업데이트 완료! 총 {updated_count}개 메뉴 가격 반영됨.")

if __name__ == '__main__':
    update_burgerking_prices()