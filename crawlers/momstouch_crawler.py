"""
맘스터치 셔틀 딜리버리 크롤러 (가격 추출 목적)
* 셔틀 딜리버리 페이지는 카테고리 이동 없이 모든 메뉴가 한 페이지에 로드됩니다.
* 저장 경로: C:/Users/chanw/diet_recommendation/data/raw
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ====================================================================
# --- [수정된] settings 모듈 임시 설정 ---
# 요청하신 절대 경로로 변경했습니다.
class MockSettings:
    DATA_RAW = 'C:/Users/chanw/diet_recommendation/data/raw'
settings = MockSettings()
# --- 임시 설정 끝 ---
# ====================================================================

class MomsTouchShuttleCrawler:
    """맘스터치 셔틀 딜리버리 메뉴 및 가격 크롤러"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (맘스터치 셔틀 딜리버리)...")
        
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
        # 셔틀 딜리버리 맘스터치 메뉴 페이지 URL (ID: 2309)
        main_url = "https://www.shuttledelivery.co.kr/ko/restaurant/menu/2309/%EB%A7%98%EC%8A%A4%ED%84%B0%EC%B9%98"
        
        print("=" * 70)
        print("🍗 맘스터치 셔틀 딜리버리 메뉴 크롤링 시작")
        print("=" * 70)
        
        all_products = []
        
        try:
            self.driver.get(main_url)
            print(f"📡 페이지 접속: {main_url}")
            
            # 팝업 대기 및 닫기 시도 (지역 선택 팝업)
            try:
                # 팝업이 있다면 닫기 버튼을 찾아서 클릭 시도
                close_btn_selector = '#menu-locationpopup .modal-header .close'
                self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, close_btn_selector))).click()
                print("   팝업 닫기 시도 완료.")
                time.sleep(1)
            except TimeoutException:
                print("   지역 선택 팝업 없음. 바로 메뉴 로딩 시도.")
            except NoSuchElementException:
                 print("   팝업은 있지만 닫기 버튼을 찾지 못했습니다. 계속 진행합니다.")
            
            # 1. 메뉴 목록 컨테이너가 로드될 때까지 대기
            self.wait.until(EC.presence_of_element_located((By.ID, 'leftBasketColumn')))
            time.sleep(3) # 추가 로딩 대기

            # 2. HTML 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 3. 카테고리별 섹션 추출 
            menu_sections = soup.select('#leftBasketColumn .single-menu')
            
            if not menu_sections:
                print("❌ 메뉴 섹션을 찾을 수 없습니다. (선택자: #leftBasketColumn .single-menu)")
                return pd.DataFrame()

            print(f"📦 총 {len(menu_sections)}개 메뉴 섹션 발견. 파싱 시작...")

            for section in menu_sections:
                # 카테고리명 추출 (예: "맘스세트", "버거", "치킨" 등)
                category_elem = section.select_one('.headingTitle')
                category_name = category_elem.text.strip() if category_elem else "기타"
                
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
                        
                        # 설명: p 태그 
                        description_elem = item.select_one('.titlecol p')
                        description = description_elem.text.strip() if description_elem else ''

                        # 이미지 URL: menupage-thumbnail의 data-original 속성
                        img_anchor = item.select_one('.menupage-thumbnail')
                        image_url = img_anchor.get('data-original', '') if img_anchor else ''
                        
                        product = {
                            'brand_name': '맘스터치',
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
            print(f"📊 맘스터치 딜리버리 메뉴 및 가격 수집 완료")
            print("=" * 70)
            print(f"총 상품 수: {len(df)}개")
            print(f"\n카테고리별:")
            print(df['category'].value_counts())
            
            return df
        
        except TimeoutException:
            print("\n❌ 페이지 로드 시간 초과. (네트워크 문제 또는 팝업 제어 문제일 수 있습니다.)")
            return pd.DataFrame()
        except Exception as e:
            print(f"\n❌ 전체 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def save_to_csv(self, df, filename='momstouch_shuttle_delivery_menu.csv'):
        """CSV 저장"""
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
        # [수정된 경로 사용]
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
    crawler = MomsTouchShuttleCrawler(headless=False) 
    
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