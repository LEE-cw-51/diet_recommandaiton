"""
세븐일레븐 크롤러 (최종 버전)
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings


class SevenElevenCrawler:
    """세븐일레븐 크롤러"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (세븐일레븐)...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            print("   (브라우저 숨김 모드)")
        else:
            print("   (브라우저 표시 모드)")
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.base_url = "https://www.7-eleven.co.kr"
        
        print("✅ 브라우저 준비 완료\n")
    
    def get_categories(self):
        """크롤링할 카테고리 탭 (URL 파라미터)"""
        return {
            '전체': '?',
            '도시락/조리면': '?pTab=mini',
            '삼각김밥/김밥': '?pTab=noodle',
            '샌드위치/햄버거': '?pTab=d_group',
        }
    
    def crawl_category(self, category_name, url_param, max_clicks=20):
        """
        카테고리별 크롤링
        
        Args:
            category_name: 카테고리명
            url_param: URL 파라미터 (예: ?pTab=mini)
            max_clicks: 최대 더보기 클릭 횟수
        """
        print(f"{'='*70}")
        print(f"🔍 크롤링: 세븐일레븐 - {category_name}")
        print(f"{'='*70}")
        
        # ✅ URL 수정
        url = f"{self.base_url}/product/bestdosirakList.asp{url_param}"
        print(f"URL: {url}\n")
        
        try:
            self.driver.get(url)
            time.sleep(3)
            
            all_products = []
            click_count = 0
            no_new_items = 0
            
            while click_count < max_clicks:
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # 상품 목록 - 확인된 선택자
                items = soup.select('.dosirak_list ul li')
                
                # btn_more 제외
                items = [item for item in items if 'btn_more' not in item.get('class', [])]
                
                if not items:
                    print("  ⚠️ 상품을 찾을 수 없습니다.")
                    break
                
                before_count = len(all_products)
                
                # 각 상품 파싱
                for item in items:
                    try:
                        # 상품명
                        name_elem = item.select_one('.infowrap .name')
                        if not name_elem:
                            continue
                        name = name_elem.text.strip()
                        
                        # 가격
                        price_elem = item.select_one('.infowrap .price span')
                        if not price_elem:
                            continue
                        price_text = price_elem.text.strip()
                        price = int(re.sub(r'[^0-9]', '', price_text))
                        
                        # 이미지
                        img_elem = item.select_one('.pic_product img')
                        image_url = ''
                        if img_elem and img_elem.get('src'):
                            image_url = img_elem['src']
                            if not image_url.startswith('http'):
                                image_url = self.base_url + image_url
                        
                        # 상품 데이터
                        product = {
                            'brand_name': '세븐일레븐',
                            'item_name': name,
                            'category': category_name,
                            'price': price,
                            'image_url': image_url,
                        }
                        
                        # 중복 체크
                        if not any(p['item_name'] == name for p in all_products):
                            all_products.append(product)
                    
                    except:
                        continue
                
                # 새로 추가된 상품 수
                new_items = len(all_products) - before_count
                
                if new_items == 0:
                    no_new_items += 1
                    if no_new_items >= 2:
                        print(f"  ✅ 더 이상 새로운 상품이 없습니다.")
                        break
                else:
                    no_new_items = 0
                
                print(f"  📦 클릭 {click_count + 1}: +{new_items}개 (총 {len(all_products)}개)")
                
                # 더보기 버튼 찾기 및 클릭
                try:
                    more_btn = None
                    selectors = [
                        '.btn_more a',
                        '#moreImg a',
                        'a[href*="fncMore"]',
                    ]
                    
                    for selector in selectors:
                        try:
                            more_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if more_btn.is_displayed():
                                break
                        except:
                            continue
                    
                    if not more_btn:
                        print(f"  ✅ 더보기 버튼 없음")
                        break
                    
                    # 버튼 위치로 스크롤
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        more_btn
                    )
                    time.sleep(1)
                    
                    # 클릭
                    self.driver.execute_script("arguments[0].click();", more_btn)
                    print(f"     🖱️  더보기 클릭")
                    
                    # 로딩 대기
                    time.sleep(2)
                    click_count += 1
                    
                except:
                    print(f"  ✅ 더보기 종료")
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
        categories = self.get_categories()
        all_products = []
        
        print("=" * 70)
        print("🏪 세븐일레븐 전체 크롤링 시작")
        print("=" * 70)
        
        for cat_name, url_param in categories.items():
            # '전체' 탭은 건너뛰기 (다른 탭 합치면 중복)
            if skip_all and cat_name == '전체':
                print(f"⏭️  '{cat_name}' 탭 건너뛰기 (중복 방지)\n")
                continue
            
            products = self.crawl_category(cat_name, url_param)
            all_products.extend(products)
            time.sleep(2)
        
        # DataFrame 변환
        df = pd.DataFrame(all_products)
        
        if df.empty:
            print("\n❌ 수집된 데이터가 없습니다.")
            return df
        
        # 중복 제거
        df = df.drop_duplicates(subset=['item_name'], keep='first')
        
        print("\n" + "=" * 70)
        print(f"📊 세븐일레븐 전체 수집 완료")
        print("=" * 70)
        print(f"총 상품 수: {len(df)}개")
        print(f"\n카테고리별:")
        print(df['category'].value_counts())
        print(f"\n가격 통계:")
        print(df['price'].describe())
        
        return df
    
    def save_to_csv(self, df, filename='seven_products.csv'):
        """CSV 저장"""
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
        filepath = os.path.join(settings.DATA_RAW, filename)
        os.makedirs(settings.DATA_RAW, exist_ok=True)
        
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
    print("🚀 세븐일레븐 크롤러 시작")
    print("=" * 70)
    
    crawler = SevenElevenCrawler(headless=False)
    
    try:
        # 테스트: 도시락/조리면 탭
        print("\n📝 테스트 모드: 도시락/조리면\n")
        products = crawler.crawl_category('도시락/조리면', '?pTab=mini', max_clicks=5)
        
        if products:
            print(f"\n✅ 테스트 성공! {len(products)}개 제품")
            
            # 샘플 데이터
            print("\n=== 수집된 데이터 샘플 ===")
            for i, p in enumerate(products[:5], 1):
                print(f"{i}. {p['item_name']} - {p['price']:,}원")
            
            # 전체 크롤링 여부
            print("\n" + "=" * 70)
            user_input = input("전체 카테고리 크롤링을 진행하시겠습니까? (y/n): ")
            
            if user_input.lower() == 'y':
                print("\n전체 크롤링 시작...\n")
                df = crawler.crawl_all(skip_all=True)
                
                if not df.empty:
                    crawler.save_to_csv(df)
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