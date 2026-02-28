"""
버거킹 통합 크롤러 (최종 완성본 - 영양성분 파싱 로직 강화)
* 모달 팝업 내부를 스크롤하고, 테이블을 찾아 9가지 영양소를 정확히 추출합니다.
* 영양소 항목이 누락된 경우를 대비해 딕셔너리를 사용하여 안정성을 확보했습니다.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
except ImportError:
    class MockSettings:
        DATA_RAW = './data_raw'
    settings = MockSettings()

# 영양소 이름과 DB 컬럼명 매핑 (정규식 처리를 위해 키워드만 사용)
NUTRITION_KEYWORDS = {
    '열량': 'calories', '탄수화물': 'carbs', '당류': 'sugars', '단백질': 'protein', 
    '지방': 'fat', '포화지방': 'saturated_fat', '트랜스지방': 'trans_fat', 
    '콜레스테롤': 'cholesterol', '나트륨': 'sodium'
}

class BurgerKingCrawler:
    def __init__(self, headless=True):
        print("🔧 Chrome 설정 중 (버거킹 - 최종 파싱)...")
        chrome_options = Options()
        if headless: 
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15) 
        self.base_url = "https://www.burgerking.co.kr"
        print("✅ 브라우저 준비 완료")

    def scrape_nutrition_modal(self, menu_name, category_name):
        """모달 내 스크롤 및 데이터 수집을 실행합니다."""
        product = {
            'store_name': 'BurgerKing',
            'menu_name': menu_name,
            'price': 0, 'category': category_name,
            'calories': 0.0, 'carbs': 0.0, 'sugars': 0.0, 'protein': 0.0, 'fat': 0.0,
            'saturated_fat': 0.0, 'trans_fat': 0.0, 'cholesterol': 0.0, 'sodium': 0.0,
            'ingredients_raw': '', 'allergens_scraped': ''
        }
        
        MODAL_WRAPPER_SELECTOR = ".modalWrap:not([style*='display: none'])"
        MODAL_CONTENT_SELECTOR = f"{MODAL_WRAPPER_SELECTOR} .pop_cont"

        try:
            # 1. 영양성분 버튼 클릭
            btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_info_link")))
            self.driver.execute_script("arguments[0].click();", btn)
            
            # 2. 모달 콘텐츠가 로드될 때까지 대기
            self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, MODAL_CONTENT_SELECTOR)))
            time.sleep(1)

            # 3. 모달 내부를 끝까지 스크롤하여 Lazy Loading 데이터 로드
            modal_content_element = self.driver.find_element(By.CSS_SELECTOR, MODAL_CONTENT_SELECTOR)
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", modal_content_element)
            time.sleep(1)
            
            # 4. 데이터 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            target_modal = soup.select_one(MODAL_CONTENT_SELECTOR.split(" .pop_cont")[0]) 
            
            if target_modal:
                container = target_modal.select_one('.pop_cont')
                
                # --- 영양 성분 추출: 테이블 파싱 ---
                # 모달 내 모든 테이블을 찾습니다. (가장 넓은 범위의 탐색)
                tables = container.select('table')
                
                # 테이블이 없는 경우를 대비하여 일반적인 리스트 구조 탐색 (.tit02와 값)
                nutrition_items = container.select('.pop_cont .tit02') 
                
                # 딕셔너리 리스트를 만들어 모든 영양소 정보를 담습니다.
                all_nutrition_items = []

                # 4.1. 테이블 기반 추출 (가장 흔한 형태)
                for table in tables:
                    rows = table.select('tr')
                    for row in rows:
                        # cols = 행 내의 모든 td/th 요소
                        cols = row.select('td, th')
                        
                        if len(cols) >= 2 and cols[0].text:
                            all_nutrition_items.append((cols[0].text.strip(), cols[1].text.strip()))
                            
                # 4.2. 리스트 기반 추출 (테이블이 아닌 경우)
                # 이 로직은 테이블이 아닌 경우에만 사용되지만, 일단 모든 텍스트 쌍을 찾습니다.
                # (이 부분은 디버깅 파일 확인 후 가장 정확한 선택자로 대체 가능)

                # 추출된 항목을 최종 product 딕셔너리에 매핑
                for name_raw, val_raw in all_nutrition_items:
                    for keyword, db_col in NUTRITION_KEYWORDS.items():
                        if keyword in name_raw:
                            # 숫자만 추출 (예: '570 kcal' -> 570)
                            val = float(re.sub(r'[^\d.]', '', val_raw)) if re.search(r'\d', val_raw) else 0.0
                            product[db_col] = val
                            break
                
                # --- 알레르기 정보 추출 ---
                full_text = container.get_text(separator=' | ', strip=True)
                product['allergens_scraped'] = full_text[:500]

        except Exception as e:
            print(f"   ⚠️ 모달 데이터 수집 실패: {e}")

        # 5. 모달 닫기
        finally:
            try:
                # 하단 '확인' 버튼 클릭을 통해 모달 닫기
                close_btn_script = "document.querySelector('.modalWrap:not([style*=\"none\"]) .pop_foot button').click();"
                self.driver.execute_script(close_btn_script)
                self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, MODAL_WRAPPER_SELECTOR)), timeout=3)
            except:
                pass

        return product

    def run(self):
        self.driver.get("https://www.burgerking.co.kr/menu/main")
        time.sleep(3)
        
        all_products = []
        
        category_selectors = [
            'input[value="cat_K200003"] + .txt_box', 'input[value="cat_K200004"] + .txt_box', 
            'input[value="cat_K200005"] + .txt_box', 'input[value="cat_K200006"] + .txt_box', 
            'input[value="cat_K200010"] + .txt_box', 'input[value="cat_K200020"] + .txt_box',
        ]

        category_names = ['프리미엄', '와퍼&주니어', '치킨&슈림프버거', '올데이스낵&올데이킹', '사이드', '음료&디저트']
        
        print(f"🔎 크롤링 시작: 총 {len(category_names)}개 카테고리")

        # 1. 전체 스크롤 및 메뉴 로딩
        self.scroll_to_bottom()

        # 2. 그룹별 순회 (탭 클릭은 이제 필요 없음, 전체 리스트에서 그룹별로 처리)
        # 모든 메뉴가 로드된 상태에서, 페이지 내의 모든 메뉴 리스트 컨테이너를 찾습니다.
        groups = self.driver.find_elements(By.CSS_SELECTOR, ".menu_list_wrap .divide_group")
        group_count = len(groups)
        print(f"🔎 총 {group_count}개의 메뉴 그룹 발견")
        
        for g_idx in range(group_count):
            try:
                # DOM 재탐색: 그룹 요소 다시 찾기
                groups = self.driver.find_elements(By.CSS_SELECTOR, ".menu_list_wrap .divide_group")
                current_group = groups[g_idx]
                
                try:
                    cat_name = current_group.find_element(By.CSS_SELECTOR, ".tit01").text.strip()
                except:
                    cat_name = "기타"
                
                cards = current_group.find_elements(By.CSS_SELECTOR, ".menu_list li .menu_card")
                card_count = len(cards)
                print(f"\n📂 [{cat_name}] 진입 - {card_count}개 메뉴")

                for i in range(card_count):
                    try:
                        # DOM 재탐색: 카드 요소 다시 찾기
                        current_cards = current_group.find_elements(By.CSS_SELECTOR, ".menu_list li .menu_card")
                        if i >= len(current_cards): break
                        
                        card = current_cards[i]
                        menu_name = card.find_element(By.CSS_SELECTOR, ".tit").text.strip()
                        
                        print(f"   ✅ 수집 중 ({i+1}/{card_count}): {menu_name}", end="\r")
                        
                        # 화면 중앙으로 스크롤 (클릭 오류 방지)
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        time.sleep(0.5)

                        # 상세 페이지 진입 및 데이터 수집
                        detail_btn = card.find_element(By.CSS_SELECTOR, "button.btn_detail")
                        self.driver.execute_script("arguments[0].click();", detail_btn)
                        
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".prd_detailWrap")))
                        time.sleep(1)
                        
                        # 데이터 수집 (모달 처리)
                        product_data = self.scrape_nutrition_modal(menu_name, cat_name)
                        
                        # 원재료명(설명) 추가 수집
                        try:
                            desc = self.driver.find_element(By.CSS_SELECTOR, ".description span").text.strip()
                            product_data['ingredients_raw'] = desc
                        except:
                            pass
                            
                        all_products.append(product_data)
                        
                        # 리스트로 복귀
                        self.driver.back()
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".menu_list_wrap")))
                        time.sleep(1.5)
                        
                    except Exception as e:
                        print(f"\n   ❌ 메뉴 에러: {menu_name} - {e}")
                        try: self.driver.back(); time.sleep(2)
                        except: pass
                        continue

            except Exception as e:
                print(f"❌ 그룹 처리 에러: {e}")
                continue

        # CSV 저장
        if all_products:
            df = pd.DataFrame(all_products)
            os.makedirs(settings.DATA_RAW, exist_ok=True)
            filepath = os.path.join(settings.DATA_RAW, 'burgerking_products.csv')
            
            columns = [
                'store_name', 'menu_name', 'price', 'calories', 'carbs', 'sugars', 
                'protein', 'fat', 'saturated_fat', 'trans_fat', 'cholesterol', 
                'sodium', 'allergens_scraped', 'ingredients_raw', 'category'
            ]
            
            for col in columns:
                if col not in df.columns: df[col] = 0 if col not in ['store_name', 'menu_name', 'allergens_scraped', 'ingredients_raw', 'category'] else ''
                
            df.to_csv(filepath, index=False, columns=columns, encoding='utf-8-sig')
            print(f"\n\n🎉 버거킹 저장 완료: {filepath} (총 {len(df)}개 메뉴)")
        else:
            print("\n⚠️ 수집된 데이터가 없습니다.")

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    crawler = BurgerKingCrawler(headless=False)
    try:
        crawler.run()
    except KeyboardInterrupt:
        print("\n사용자 중단")
    finally:
        crawler.close()