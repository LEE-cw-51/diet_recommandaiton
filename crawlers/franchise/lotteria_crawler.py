"""
롯데리아 메뉴 크롤러 (가격 추출 목적)
* 롯데잇츠(LOTTE EATZ) 롯데리아 메뉴 페이지에서 메뉴명, 가격, 이미지 URL을 크롤링합니다.
* JavaScript 변수(pList, cList)에서 직접 데이터를 추출하여 빠르고 정확합니다.
* 저장 경로: C:/Users/chanw/diet_recommendation/data/raw
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import pandas as pd
import time
import re
import os
import sys
import json # JSON 파싱을 위해 추가

# 프로젝트 루트 경로 설정 (settings.py 모듈을 찾기 위함)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ====================================================================
# --- [최종 경로 설정] settings 모듈 임시 설정 ---
# 요청하신 절대 경로로 변경되었습니다.
class MockSettings:
    DATA_RAW = 'C:/Users/chanw/diet_recommendation/data/raw'
settings = MockSettings()
# --- 임시 설정 끝 ---
# ====================================================================

class LotteriaCrawler:
    """롯데리아 메뉴 및 가격 크롤러 (JS 변수 추출 방식)"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (롯데리아)...")
        
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
        """전체 메뉴 및 가격 크롤링 (JS 변수 직접 추출)"""
        main_url = "https://www.lotteeatz.com/brand/ria" 
        
        print("=" * 70)
        print("🍔 롯데리아 메뉴 크롤링 시작 (JS 데이터 추출 방식)")
        print("=" * 70)
        
        all_products = []
        
        try:
            self.driver.get(main_url)
            print(f"📡 페이지 접속: {main_url}")
            
            # 팝업 닫기 시도 (오더 선택 팝업 등)
            time.sleep(3) 
            try:
                close_btn_selector = '#orderTypeSelectPopup .btn-pop-close'
                close_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, close_btn_selector)))
                close_button.click()
                print("   오더 선택 팝업 닫기 시도 완료.")
                time.sleep(1)
            except (NoSuchElementException, ElementClickInterceptedException, TimeoutException):
                pass
            
            # 1. 메뉴 목록 컨테이너가 로드될 때까지 대기
            self.wait.until(EC.presence_of_element_located((By.ID, 'productList')))
            print("   페이지 로드 완료. JavaScript 변수 추출 중...")

            # 2. [핵심] JavaScript 변수(cList, pList)에서 데이터 추출
            # cList: 카테고리 정보 (displayCategoryId, displayCategoryNm)
            # pList: 제품 정보 (presPrdNm, sellPrice, imgPath 등)
            
            cList_data = self.driver.execute_script("return window.cList;")
            pList_data = self.driver.execute_script("return window.pList;")

            if not cList_data or not pList_data:
                print("❌ JavaScript 변수(cList 또는 pList)를 찾을 수 없습니다. 크롤링을 중단합니다.")
                return pd.DataFrame()

            # 3. 카테고리 정보(cList)를 딕셔너리로 변환 (ID -> 이름)
            category_map = {}
            for category in cList_data:
                category_map[category.get('displayCategoryId')] = category.get('displayCategoryNm')

            print(f"   카테고리 {len(category_map)}개, 제품 {len(pList_data)}개 로드 완료. 파싱 시작...")

            # 4. 제품 정보(pList) 파싱
            for item in pList_data:
                try:
                    name = item.get('presPrdNm')
                    price = int(item.get('sellPrice', 0))
                    category_id = item.get('displayCategoryId')
                    category_name = category_map.get(category_id, '기타') # ID로 카테고리명 조회
                    
                    # 이미지 URL 조합
                    img_path = item.get('imgPath', '')
                    img_file = item.get('imgSystemFileNm', '')
                    img_ext = item.get('imgExtsn', '')
                    image_url = ""
                    if img_path and img_file and img_ext:
                        image_url = f"https://img.lotteeatz.com{img_path}{img_file}.{img_ext}"
                    
                    # 'NEW 미라클버거' 처럼 dispNm에 다른 이름이 있는 경우 사용
                    display_name = item.get('dispNm')
                    if display_name:
                        name = display_name
                    
                    product = {
                        'brand_name': '롯데리아',
                        'item_name': name,
                        'category': category_name,
                        'price': price,
                        'description': '롯데잇츠 공식 메뉴',
                        'image_url': image_url,
                    }
                    
                    if price > 0:
                        all_products.append(product)
                    
                except Exception as e:
                    print(f"    - [WARN] 개별 메뉴 파싱 오류: {e}")
                    continue

            if not all_products:
                 print("\n❌ 수집된 유효한 데이터가 없습니다.")
                 return pd.DataFrame()
                 
            df = pd.DataFrame(all_products)
            df = df.drop_duplicates(subset=['item_name'], keep='first')
            
            print("\n" + "=" * 70)
            print(f"📊 롯데리아 메뉴 및 가격 수집 완료")
            print("=" * 70)
            print(f"총 상품 수: {len(df)}개")
            print(f"\n카테고리별:")
            print(df['category'].value_counts())
            
            return df
        
        except TimeoutException:
            print("\n❌ 페이지 로드 시간 초과. (네트워크 문제 또는 사이트 변경)")
            return pd.DataFrame()
        except Exception as e:
            print(f"\n❌ 전체 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def save_to_csv(self, df, filename='lotteria_menu.csv'):
        """CSV 저장"""
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
        # [요청 경로 사용]
        os.makedirs(settings.DATA_RAW, exist_ok=True)
        filepath = os.path.join(settings.DATA_RAW, filename)
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"\n💾 저장 완료: {filepath}")
        print(f"\n=== 샘플 데이터 (처음 10개) ===")
        print(df[['item_name', 'category', 'price']].head(10).to_string(index=False))
    
    def close(self):
        """브라우저 종료"""
        try:
            self.driver.quit()
            print("\n🔒 브라우저 종료")
        except:
            pass


def main():
    """메인 실행"""
    crawler = LotteriaCrawler(headless=False) 
    
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