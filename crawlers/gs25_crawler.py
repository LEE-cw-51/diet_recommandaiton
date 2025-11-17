"""
GS25 편의점 크롤러 (페이지네이션 클릭 방식)
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

# settings.py 파일이 상위 폴더에 있는 경우
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 'config' 폴더가 현재 폴더와 같은 위치에 있다면 위 라인은 주석 처리하고 아래를 사용하세요.
# from config.settings import settings
# --- settings 모듈 임시 설정 (테스트용) ---
# 실제 환경에서는 이 부분을 지우고 위의 import를 사용하세요.
class MockSettings:
    DATA_RAW = './data_raw'
settings = MockSettings()
# --- 임시 설정 끝 ---


class GS25Crawler:
    """GS25 편의점 크롤러"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (GS25)...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            print("   (브라우저 숨김 모드)")
        else:
            print("   (브라우저 표시 모드)")
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except ValueError as e:
            print(f"❌ ChromeDriverManager 오류: {e}")
            print("   Chrome 드라이버 수동 설치가 필요할 수 있습니다.")
            raise
            
        self.wait = WebDriverWait(self.driver, 10)
        
        print("✅ 브라우저 준비 완료\n")
    
    def get_categories(self):
        """크롤링할 카테고리 탭 ID"""
        return {
            '전체': 'productALL',
            '도시락': 'productLunch',
            '김밥/주먹밥': 'productRice',
            '햄버거/샌드위치': 'productBurger',
            '간편식': 'productSnack',
        }
    
    def crawl_category(self, category_name, tab_id):
        """
        카테고리별 크롤링 (페이지네이션 클릭 방식)
        
        Args:
            category_name: 카테고리명
            tab_id: 탭 버튼 ID
        """
        print(f"{'='*70}")
        print(f"🔍 크롤링: GS25 - {category_name}")
        print(f"{'='*70}")
        
        try:
            # 탭 클릭
            try:
                tab_button = self.wait.until(
                    EC.element_to_be_clickable((By.ID, tab_id))
                )
                self.driver.execute_script("arguments[0].click();", tab_button)
                print(f"   🖱️  '{category_name}' 탭 클릭")
                time.sleep(3)  # 콘텐츠 로딩 대기
            except Exception as e:
                print(f"   ❌ 탭 클릭 실패: {e}")
                return []
            
            all_products = []
            page_count = 1
            no_new_items_streak = 0
            
            # --- [수정됨] 스크롤 루프 대신 페이지네이션 루프 ---
            while True:
                print(f"   📄 페이지 {page_count} 파싱 중...")
                
                try:
                    # 상품 목록이 로드될 때까지 대기
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.prod_list > li")))
                    time.sleep(1) # JS가 DOM을 완전히 그릴 때까지 잠시 대기
                except TimeoutException:
                    print("   ⚠️ 상품 목록을 기다렸지만 로드되지 않았습니다.")
                    if page_count == 1:
                        print("   ⚠️ 이 카테고리에 상품이 없는 것 같습니다.")
                    break # 루프 종료

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # HTML 구조에 맞춰 셀렉터 구체화
                items = soup.select('ul.prod_list > li .prod_box')
                
                if not items and page_count == 1:
                    print("   ⚠️ 상품 태그(.prod_box)를 찾을 수 없습니다.")
                    break

                before_count = len(all_products)
                
                # 각 상품 파싱 (기존 코드와 동일)
                for item in items:
                    try:
                        name_elem = item.select_one('.tit')
                        if not name_elem: continue
                        name = name_elem.text.strip()
                        
                        price_elem = item.select_one('.cost')
                        if not price_elem: continue
                        price_text = price_elem.text.strip()
                        price = int(re.sub(r'[^0-9]', '', price_text))
                        
                        img_elem = item.select_one('.img img')
                        image_url = ''
                        if img_elem and img_elem.get('src'):
                            image_url = img_elem['src']
                        
                        product = {
                            'brand_name': 'GS25',
                            'item_name': name,
                            'category': category_name,
                            'price': price,
                            'image_url': image_url,
                        }
                        
                        # 중복 체크
                        if not any(p['item_name'] == name for p in all_products):
                            all_products.append(product)
                    
                    except Exception as e:
                        print(f"    - 상품 파싱 중 오류: {e}")
                        continue
                
                new_items_found = len(all_products) - before_count
                print(f"   📦 +{new_items_found}개 신규 상품 (총 {len(all_products)}개)")
                
                # --- [수정됨] 페이지네이션 로직 ---
                
                # 2페이지 연속으로 새 상품이 없으면 종료 (중복 페이지 방지)
                if new_items_found == 0 and page_count > 1:
                    no_new_items_streak += 1
                    if no_new_items_streak >= 2:
                        print("   ✅ 새로운 상품이 없어 크롤링을 종료합니다.")
                        break
                else:
                    no_new_items_streak = 0
                
                try:
                    # '다음' 버튼(>)을 찾습니다. (HTML: <a class="next" ...>)
                    next_button = self.driver.find_element(By.CSS_SELECTOR, "a.next[onclick*='moveControl']")
                    
                    # 다음 버튼 클릭
                    self.driver.execute_script("arguments[0].click();", next_button)
                    print(f"   ▶️ 다음 페이지({page_count + 1})로 이동...")
                    page_count += 1
                    time.sleep(3) # 새 페이지 AJAX 로드 대기

                except NoSuchElementException:
                    # '다음' 버튼이 더 이상 없으면 마지막 페이지입니다.
                    print(f"   ✅ 다음 페이지 버튼을 찾지 못했습니다. '{category_name}' 완료.")
                    break
                except Exception as e:
                    print(f"   ❌ 다음 페이지 클릭 중 오류: {e}")
                    break
            
            print(f"\n✅ {category_name} 완료: {len(all_products)}개\n")
            return all_products
        
        except Exception as e:
            print(f"\n❌ {category_name} 오류: {e}\n")
            import traceback
            traceback.print_exc()
            return []
    
    def crawl_all(self, skip_all=True):
        """
        전체 카테고리 크롤링
        
        Args:
            skip_all: True면 '전체' 탭 건너뛰기 (중복 방지)
        """
        main_url = "http://gs25.gsretail.com/gscvs/ko/products/youus-freshfood"
        
        print("=" * 70)
        print("🏪 GS25 전체 크롤링 시작")
        print("=" * 70)
        
        try:
            self.driver.get(main_url)
            print(f"📡 페이지 접속: {main_url}\n")
            time.sleep(3)
            
            categories = self.get_categories()
            all_products = []
            
            for cat_name, tab_id in categories.items():
                if skip_all and cat_name == '전체':
                    print(f"⏭️  '{cat_name}' 탭 건너뛰기 (중복 방지)\n")
                    continue
                
                # [수정됨] max_scrolls 인수 제거
                products = self.crawl_category(cat_name, tab_id)
                all_products.extend(products)
                time.sleep(2) # 탭 이동 간 간격
            
            if not all_products:
                 print("\n❌ 수집된 데이터가 없습니다.")
                 return pd.DataFrame()
                 
            df = pd.DataFrame(all_products)
            
            # 중복 제거
            df = df.drop_duplicates(subset=['item_name'], keep='first')
            
            print("\n" + "=" * 70)
            print(f"📊 GS25 전체 수집 완료")
            print("=" * 70)
            print(f"총 상품 수: {len(df)}개")
            print(f"\n카테고리별:")
            print(df['category'].value_counts())
            print(f"\n가격 통계:")
            print(df['price'].describe())
            
            return df
        
        except Exception as e:
            print(f"\n❌ 전체 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def save_to_csv(self, df, filename='gs25_products.csv'):
        """CSV 저장"""
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
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
    print("=" * 70)
    print("🚀 GS25 크롤러 시작")
    print("=" * 70)
    
    # headless=True로 변경하면 브라우저 창이 뜨지 않습니다.
    crawler = GS25Crawler(headless=False) 
    
    try:
        main_url = "http://gs25.gsretail.com/gscvs/ko/products/youus-freshfood"
        print(f"📡 페이지 접속: {main_url}\n")
        
        crawler.driver.get(main_url)
        time.sleep(3)
        
        # 테스트: 도시락 탭만
        print("📝 테스트 모드: 도시락 탭\n")
        
        # [수정됨] max_scrolls 인수 제거
        products = crawler.crawl_category('도시락', 'productLunch')
        
        if products:
            print(f"\n✅ 테스트 성공! {len(products)}개 제품")
            
            print("\n=== 수집된 데이터 샘플 ===")
            for i, p in enumerate(products[:5], 1):
                print(f"{i}. {p['item_name']} - {p['price']:,}원")
            
            print("\n" + "=" * 70)
            user_input = input("전체 카테고리 크롤링을 진행하시겠습니까? (y/n): ")
            
            if user_input.lower() == 'y':
                print("\n전체 크롤링 시작...\n")
                
                # crawl_all이 내부적으로 페이지를 새로 로드하므로
                # 여기서는 별도로 get()을 호출할 필요가 없습니다.
                df = crawler.crawl_all(skip_all=True)
                
                if not df.empty:
                    crawler.save_to_csv(df, 'gs25_fresh_food.csv')
            else:
                print("\n크롤링 종료")
        else:
            print("\n❌ 테스트 실패")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자가 중단했습니다.")
    
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        crawler.close()
        print("\n✅ 프로그램 종료")


if __name__ == "__main__":
    main()