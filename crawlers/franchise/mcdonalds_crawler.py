"""
맥도날드 통합 크롤러 (영양성분 + 알레르기 정보)
* 영양정보 페이지와 알레르기 정보 페이지를 모두 크롤링하여 데이터를 병합합니다.
* 생성된 데이터는 DB의 Menu_Master 테이블 구조와 호환됩니다.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
except ImportError:
    class MockSettings:
        DATA_RAW = './data/raw'
    settings = MockSettings()

class McDonaldsCrawler:
    def __init__(self, headless=True):
        print("🔧 Chrome 설정 중 (맥도날드 통합 크롤러)...")
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('user-agent=Mozilla/5.0')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.base_url = "https://www.mcdonalds.co.kr"

    def crawl_nutrition_table(self):
        """영양정보 페이지 크롤링"""
        url = f"{self.base_url}/kor/menu/information/nutrition"
        print(f"\n1️⃣ 영양정보 수집 시작: {url}")
        self.driver.get(url)
        time.sleep(2) # 페이지 로딩 대기
        
        products = {} # Key: 메뉴명, Value: 데이터 딕셔너리
        
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            # 모든 카테고리 테이블 순회
            tables = soup.select('table')
            
            for table in tables:
                # 헤더 매핑 확인
                headers = [th.text.strip() for th in table.select('thead th')]
                col_map = {}
                for idx, h in enumerate(headers):
                    if '열량' in h: col_map[idx] = 'calories'
                    elif '당' in h: col_map[idx] = 'sugars'
                    elif '단백질' in h: col_map[idx] = 'protein'
                    elif '포화지방' in h: col_map[idx] = 'saturated_fat'
                    elif '나트륨' in h: col_map[idx] = 'sodium'
                
                # 행 데이터 추출
                for row in table.select('tbody tr'):
                    cols = row.select('th, td')
                    if not cols: continue
                    
                    name = cols[0].text.strip()
                    product_data = {
                        'menu_name': name,
                        'store_name': 'McDonalds',
                        'price': 0, # 가격 정보 없음
                        # 9대 영양소 초기화
                        'calories': 0.0, 'carbs': 0.0, 'sugars': 0.0, 'protein': 0.0, 'fat': 0.0,
                        'saturated_fat': 0.0, 'trans_fat': 0.0, 'cholesterol': 0.0, 'sodium': 0.0,
                        'ingredients_raw': '',
                        'allergens_scraped': ''
                    }
                    
                    # 매핑된 영양소 값 추출
                    for idx, col in enumerate(cols):
                        if idx in col_map:
                            text = col.text.strip()
                            # 숫자만 추출 (범위 값인 경우 최소값 사용)
                            nums = re.findall(r'[\d.]+', text)
                            if nums:
                                product_data[col_map[idx]] = float(nums[0])
                    
                    products[name] = product_data
                    
            print(f"   👉 {len(products)}개 메뉴 영양정보 확보")
            return products
            
        except Exception as e:
            print(f"❌ 영양정보 크롤링 실패: {e}")
            return {}

    def crawl_allergy_table(self):
        """알레르기 정보 페이지 크롤링"""
        url = f"{self.base_url}/kor/menu/information/allergens"
        print(f"\n2️⃣ 알레르기 정보 수집 시작: {url}")
        self.driver.get(url)
        time.sleep(2)
        
        allergy_map = {} # Key: 메뉴명, Value: 알레르기 정보 문자열
        
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            tables = soup.select('table')
            
            for table in tables:
                # 알레르기 테이블은 보통 [메뉴명, 알레르기 유발 식재료] 구조임
                for row in table.select('tbody tr'):
                    cols = row.select('th, td')
                    if len(cols) < 2: continue
                    
                    name = cols[0].text.strip()
                    allergens = cols[1].text.strip()
                    
                    allergy_map[name] = allergens
            
            print(f"   👉 {len(allergy_map)}개 메뉴 알레르기 정보 확보")
            return allergy_map
            
        except Exception as e:
            print(f"❌ 알레르기 정보 크롤링 실패: {e}")
            return {}

    def run(self):
        # 1. 영양정보 수집
        products = self.crawl_nutrition_table()
        
        # 2. 알레르기 정보 수집
        allergens = self.crawl_allergy_table()
        
        # 3. 데이터 병합 (메뉴명 기준)
        print("\n3️⃣ 데이터 병합 중...")
        merged_list = []
        
        for name, data in products.items():
            # 알레르기 정보가 있으면 추가
            if name in allergens:
                data['allergens_scraped'] = allergens[name]
            
            # 카테고리 추정 (단순 로직)
            if '버거' in name: data['category'] = '버거'
            elif '세트' in name: data['category'] = '세트'
            elif '머핀' in name: data['category'] = '맥모닝'
            elif '아메리카노' in name or '라떼' in name or '쉐이크' in name: data['category'] = '음료'
            else: data['category'] = '사이드/디저트'
            
            merged_list.append(data)
            
        # 4. CSV 저장
        if merged_list:
            df = pd.DataFrame(merged_list)
            
            # DB 컬럼 순서대로 정렬
            columns = [
                'store_name', 'menu_name', 'price', 'calories', 'carbs', 'sugars', 
                'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
                'sodium', 'ingredients_raw', 'allergens_scraped', 'category'
            ]
            
            # 없는 컬럼은 0이나 빈 값으로 채움
            for col in columns:
                if col not in df.columns:
                    df[col] = 0 if 'fat' in col or 'chol' in col else ''
            
            os.makedirs(settings.DATA_RAW, exist_ok=True)
            filepath = os.path.join(settings.DATA_RAW, 'mcdonalds_products.csv')
            df[columns].to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"\n💾 저장 완료: {filepath} (총 {len(df)}개 메뉴)")
        else:
            print("\n⚠️ 저장할 데이터가 없습니다.")

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    crawler = McDonaldsCrawler(headless=True)
    crawler.run()
    crawler.close()