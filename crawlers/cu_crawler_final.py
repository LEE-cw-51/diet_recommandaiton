"""
CU 편의점 크롤러 (최종 버전)
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


class CUCrawler:
    """CU 편의점 크롤러"""
    
    def __init__(self, headless=False):
        """
        초기화
        
        Args:
            headless: True면 브라우저 숨김
        """
        print("🔧 Chrome 설정 중...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
            print("   (브라우저 숨김 모드)")
        else:
            print("   (브라우저 표시 모드)")
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ 브라우저 준비 완료\n")
        except Exception as e:
            print(f"❌ 브라우저 설정 실패: {e}")
            raise
        
        self.base_url = "https://cu.bgfretail.com"
    
    def get_category_name_from_url(self, url):
        """URL에서 카테고리 이름 추정"""
        if 'depth2=4' in url:
            if 'depth3=1' in url:
                return '도시락'
            elif 'depth3=2' in url:
                return '샌드위치'
            elif 'depth3=3' in url:
                return '햄버거'
            elif 'depth3=4' in url:
                return '주먹밥'
            elif 'depth3=5' in url:
                return '김밥'
            else:
                return '간편식사'
        return '기타'
    
    def crawl_page(self, url, category_name=None, max_clicks=20):
        """
        페이지 크롤링
        
        Args:
            url: 크롤링할 URL
            category_name: 카테고리명 (None이면 URL에서 추정)
            max_clicks: 최대 더보기 클릭 횟수
        
        Returns:
            list: 상품 정보 리스트
        """
        if category_name is None:
            category_name = self.get_category_name_from_url(url)
        
        print(f"{'='*70}")
        print(f"🔍 크롤링: {category_name}")
        print(f"{'='*70}")
        print(f"URL: {url}\n")
        
        try:
            # 페이지 접속
            self.driver.get(url)
            time.sleep(3)
            
            all_products = []
            click_count = 0
            no_new_items = 0
            
            while click_count < max_clicks:
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # 상품 목록 - 확인된 선택자 사용
                items = soup.select('.prod_item')
                
                if not items:
                    print("❌ 상품을 찾을 수 없습니다.")
                    # 디버깅용 HTML 출력
                    print("\n=== HTML 샘플 ===")
                    print(soup.prettify()[:1500])
                    break
                
                before_count = len(all_products)
                
                # 각 상품 파싱
                for item in items:
                    try:
                        # 상품명
                        name_elem = item.select_one('.prod_text .name p')
                        if not name_elem:
                            continue
                        name = name_elem.text.strip()
                        
                        # 가격
                        price_elem = item.select_one('.prod_text .price strong')
                        if not price_elem:
                            continue
                        price_text = price_elem.text.strip()
                        # 쉼표 제거 후 숫자만
                        price = int(re.sub(r'[^0-9]', '', price_text))
                        
                        # 이미지
                        img_elem = item.select_one('.prod_img img')
                        image_url = ''
                        if img_elem and img_elem.get('src'):
                            image_url = img_elem['src']
                            # //로 시작하면 https: 추가
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif not image_url.startswith('http'):
                                image_url = self.base_url + image_url
                        
                        # 상품 데이터
                        product = {
                            'brand_name': 'CU',
                            'item_name': name,
                            'category': category_name,
                            'price': price,
                            'image_url': image_url,
                        }
                        
                        # 중복 체크
                        if not any(p['item_name'] == name for p in all_products):
                            all_products.append(product)
                    
                    except Exception as e:
                        # 개별 상품 파싱 실패는 조용히 넘어감
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
                
                print(f"  📦 시도 {click_count + 1}: +{new_items}개 (총 {len(all_products)}개)")
                
                # 더보기 버튼 찾기 및 클릭
                try:
                    more_btn = None
                    
                    # 여러 선택자 시도
                    btn_selectors = [
                        'a.btn_more',
                        'button.btn_more',
                        '.prodListBtn a',
                        'a[onclick*="more"]',
                    ]
                    
                    for selector in btn_selectors:
                        try:
                            more_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if more_btn.is_displayed():
                                break
                        except:
                            continue
                    
                    if not more_btn:
                        print(f"  ✅ 더보기 버튼 없음 - 모든 상품 로드 완료")
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
                    
                except Exception as e:
                    print(f"  ✅ 더보기 종료")
                    break
            
            print(f"\n✅ {category_name} 완료: {len(all_products)}개 상품\n")
            return all_products
        
        except Exception as e:
            print(f"\n❌ {category_name} 크롤링 오류: {e}\n")
            import traceback
            traceback.print_exc()
            return []
    
    def crawl_all_categories(self):
        """전체 카테고리 크롤링"""
        categories = {
            '도시락': f'{self.base_url}/product/product.do?category=product&depth2=4&depth3=1&sf=N',
            '샌드위치': f'{self.base_url}/product/product.do?category=product&depth2=4&depth3=2&sf=N',
            '햄버거': f'{self.base_url}/product/product.do?category=product&depth2=4&depth3=3&sf=N',
            '주먹밥': f'{self.base_url}/product/product.do?category=product&depth2=4&depth3=4&sf=N',
            '김밥': f'{self.base_url}/product/product.do?category=product&depth2=4&depth3=5&sf=N',
        }
        
        all_products = []
        
        print("=" * 70)
        print("🏪 CU 편의점 전체 크롤링 시작")
        print("=" * 70)
        
        for cat_name, cat_url in categories.items():
            products = self.crawl_page(cat_url, cat_name)
            all_products.extend(products)
            time.sleep(2)  # 카테고리 간 대기
        
        # DataFrame 변환
        df = pd.DataFrame(all_products)
        
        if df.empty:
            print("\n❌ 수집된 데이터가 없습니다.")
            return df
        
        # 중복 제거
        df = df.drop_duplicates(subset=['item_name'], keep='first')
        
        print("\n" + "=" * 70)
        print(f"📊 전체 수집 완료")
        print("=" * 70)
        print(f"총 상품 수: {len(df)}개")
        print(f"\n카테고리별:")
        print(df['category'].value_counts())
        print(f"\n가격 통계:")
        print(df['price'].describe())
        
        return df
    
    def save_to_csv(self, df, filename='cu_products.csv'):
        """
        CSV 저장
        
        Args:
            df: 저장할 DataFrame
            filename: 파일명
        """
        if df.empty:
            print("⚠️ 저장할 데이터가 없습니다.")
            return
        
        # data/raw 폴더에 저장
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
    print("🚀 CU 크롤러 시작")
    print("=" * 70)
    
    # 크롤러 생성 (브라우저 보려면 headless=False)
    crawler = CUCrawler(headless=False)
    
    try:
        # 테스트: 도시락만
        print("\n📝 테스트 모드: 도시락 카테고리\n")
        test_url = "https://cu.bgfretail.com/product/product.do?category=product&depth2=4&depth3=1&sf=N"
        products = crawler.crawl_page(test_url, max_clicks=3)
        
        if products:
            print(f"\n✅ 테스트 성공! {len(products)}개 제품 수집")
            
            # 샘플 데이터 확인
            print("\n=== 수집된 데이터 샘플 ===")
            for i, p in enumerate(products[:5], 1):
                print(f"{i}. {p['item_name']} - {p['price']:,}원")
            
            # 전체 크롤링 여부
            print("\n" + "=" * 70)
            user_input = input("전체 카테고리 크롤링을 진행하시겠습니까? (y/n): ")
            
            if user_input.lower() == 'y':
                print("\n전체 크롤링 시작...\n")
                df = crawler.crawl_all_categories()
                
                if not df.empty:
                    crawler.save_to_csv(df)
            else:
                print("\n크롤링 종료")
        else:
            print("\n❌ 테스트 실패: 상품을 찾을 수 없습니다.")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자가 중단했습니다.")
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        crawler.close()
        print("\n✅ 프로그램 종료")


if __name__ == "__main__":
    main()