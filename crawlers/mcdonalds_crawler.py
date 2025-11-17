"""
맥도날드 셔틀 딜리버리 크롤러 (가격 추출 목적)
* 셔틀 딜리버리에 등록된 맥도날드 메뉴 페이지를 크롤링합니다.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- settings 모듈 임시 설정 (실제 환경에 맞게 수정 필요) ---
class MockSettings:
    DATA_RAW = './data_raw'
settings = MockSettings()
# --- 임시 설정 끝 ---

class McDonaldsShuttleCrawler:
    """맥도날드 셔틀 딜리버리 메뉴 및 가격 크롤러"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (맥도날드 셔틀 딜리버리)...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            print("   (브라우저 숨김 모드)")
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"❌ ChromeDriverManager 오류: {e}")
            raise
            
        self.wait = WebDriverWait(self.driver, 15)
        print("✅ 브라우저 준비 완료\n")
        
    def crawl_all(self):
        """전체 메뉴 및 가격 크롤링"""
        # 셔틀 딜리버리 맥도날드 메뉴 페이지 URL (버거킹과 ID만 다름)
        main_url = "https://www.shuttledelivery.co.kr/ko/restaurant/menu/2679/%EB%A7%A5%EB%8F%84%EB%82%A0%EB%93%9C"
        
        print("=" * 70)
        print("🍟 맥도날드 셔틀 딜리버리 메뉴 크롤링 시작")
        print("=" * 70)
        
        all_products = []
        
        try:
            self.driver.get(main_url)
            print(f"📡 페이지 접속: {main_url}")
            
            # 팝업 대기 및 닫기 시도 (지역 선택 팝업)
            try:
                # 팝업이 있는지 확인 (Modal: #menu-locationpopup)
                self.wait.until(EC.visibility_of_element_located((By.ID, 'menu-locationpopup')))
                print("   ⚠️ 지역 선택 팝업이 감지되었습니다. 크롤링 진행을 위해 팝업을 닫아야 합니다.")
                # 팝업 닫기 버튼은 없으므로, 지역 선택 없이 메뉴가 로드되기를 기대하며 기다립니다.
                # 그러나 이 페이지는 지역 설정 없이는 메뉴 로드가 안 될 가능성이 높습니다.
                # 크롤링을 위해 팝업을 수동으로 닫거나, 주소를 강제로 설정하는 코드를 추가해야 합니다.
                
                # --- 임시 조치: 팝업 대충 닫기 ---
                close_btn_selector = '#menu-locationpopup .modal-header .close'
                close_btn = self.driver.find_element(By.CSS_SELECTOR, close_btn_selector)
                self.driver.execute_script("arguments[0].click();", close_btn)
                print("   팝업 닫기 시도 완료 (메뉴 로드 실패 가능성 있음).")
                time.sleep(2)
                # --- 임시 조치 끝 ---
                
            except TimeoutException:
                print("   지역 선택 팝업 없음. 바로 메뉴 로딩 시도.")
            
            # 1. 메뉴 목록 컨테이너가 로드될 때까지 대기
            self.wait.until(EC.presence_of_element_located((By.ID, 'leftBasketColumn')))
            time.sleep(3) # 추가 로딩 대기

            # 2. HTML 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 3. 카테고리별 섹션 추출 (예: 버거, 세트메뉴, 스낵 & 사이드, 음료, 커피)
            menu_sections = soup.select('#leftBasketColumn .single-menu')
            
            if not menu_sections or len(menu_sections) < 3:
                # 지역 설정 팝업 때문에 메뉴가 로드 안 된 것일 수 있습니다.
                print("❌ 메뉴 섹션을 찾을 수 없습니다. (지역 설정 문제일 수 있습니다.)")
                return pd.DataFrame()

            print(f"📦 총 {len(menu_sections)}개 메뉴 섹션 발견. 파싱 시작...")

            for section in menu_sections:
                # 카테고리명 추출 (예: "버거")
                category_elem = section.select_one('.headingTitle')
                if not category_elem:
                    continue
                category_name = category_elem.text.strip()
                
                print(f"  > 카테고리: {category_name}")

                # 해당 섹션 내의 모든 메뉴 아이템 추출
                items = section.select('.items .menuitem')
                
                for item in items:
                    try:
                        # 메뉴명: .itemtitle
                        name_elem = item.select_one('.itemtitle')
                        name = name_elem.text.strip() if name_elem else "이름 없음"
                        
                        # 가격: .price
                        price_elem = item.select_one('.price')
                        price_text = price_elem.text.strip() if price_elem else None
                        
                        price = None
                        if price_text:
                            price = int(re.sub(r'[^\d]', '', price_text))
                        
                        # 설명: p 태그 (메뉴 상세 설명)
                        description_elem = item.select_one('.titlecol p')
                        description = description_elem.text.strip() if description_elem else ''

                        # 이미지 URL: menupage-thumbnail의 data-original 속성
                        img_anchor = item.select_one('.menupage-thumbnail')
                        image_url = img_anchor.get('data-original', '') if img_anchor else ''
                        
                        product = {
                            'brand_name': '맥도날드',
                            'item_name': name,
                            'category': category_name,
                            'price': price,
                            'description': description,
                            'image_url': image_url,
                        }
                        
                        if price is not None and price > 0:
                            all_products.append(product)
                        else:
                            print(f"    - [SKIP] 가격 정보가 없어 건너뜁니다: {name}")

                    except Exception as e:
                        print(f"    - [WARN] 개별 메뉴 파싱 오류 (이전 메뉴: {name if 'name' in locals() else 'Unknown'}): {e}")
                        continue

            if not all_products:
                 print("\n❌ 수집된 유효한 데이터가 없습니다.")
                 return pd.DataFrame()
                 
            df = pd.DataFrame(all_products)
            df = df.drop_duplicates(subset=['item_name'], keep='first')
            
            print("\n" + "=" * 70)
            print(f"📊 맥도날드 딜리버리 메뉴 및 가격 수집 완료")
            print("=" * 70)
            print(f"총 상품 수: {len(df)}개")
            print(f"\n카테고리별:")
            print(df['category'].value_counts())
            
            return df
        
        except TimeoutException:
            print("\n❌ 페이지 로드 시간 초과. (지역 설정 문제일 가능성이 높습니다.)")
            return pd.DataFrame()
        except Exception as e:
            print(f"\n❌ 전체 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def save_to_csv(self, df, filename='mcdonalds_shuttle_delivery_menu.csv'):
        """CSV 저장"""
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
        os.makedirs(settings.DATA_RAW, exist_ok=True)
        filepath = os.path.join(settings.DATA_RAW, filename)
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"\n💾 저장 완료: {filepath}")
        print(f"\n=== 샘플 데이터 (처음 10개) ===")
        print(df[['item_name', 'category', 'price', 'description']].head(10).to_string(index=False))
    
    def close(self):
        """브라우저 종료"""
        try:
            self.driver.quit()
            print("\n🔒 브라우저 종료")
        except:
            pass


def main():
    """메인 실행"""
    crawler = McDonaldsShuttleCrawler(headless=False) 
    
    try:
        df = crawler.crawl_all()
        
        if not df.empty:
            crawler.save_to_csv(df)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 메인 실행 오류: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        crawler.close()
        print("\n✅ 프로그램 종료")


if __name__ == "__main__":
    main()