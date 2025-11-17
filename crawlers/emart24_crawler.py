"""
이마트24 크롤러 (최종 버전)
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


class Emart24Crawler:
    """이마트24 크롤러"""
    
    def __init__(self, headless=False):
        print("🔧 Chrome 설정 중 (이마트24)...")
        
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
        self.base_url = "https://emart24.co.kr"
        
        print("✅ 브라우저 준비 완료\n")
    
    def get_categories(self):
        """크롤링할 카테고리 (base_category_seq 파라미터)"""
        return {
            '전체': '',
            '도시락': '41',
            '김밥': '42',
            '햄버거': '43',
            '주먹밥': '45',
            '샌드위치': '46',
            '즉석식': '47',
        }
    
    def crawl_category(self, category_name, base_category_seq, max_pages=10):
        """
        카테고리별 크롤링 (페이지네이션)
        
        Args:
            category_name: 카테고리명
            base_category_seq: 카테고리 ID (41=도시락, 42=김밥 등)
            max_pages: 최대 페이지 수
        """
        print(f"{'='*70}")
        print(f"🔍 크롤링: 이마트24 - {category_name}")
        print(f"{'='*70}")
        
        all_products = []
        
        for page in range(1, max_pages + 1):
            # URL 생성
            if base_category_seq:
                url = f"{self.base_url}/goods/ff?search=&category_seq=&base_category_seq={base_category_seq}&align=&page={page}"
            else:
                url = f"{self.base_url}/goods/ff?search=&category_seq=&align=&page={page}"
            
            print(f"  📄 페이지 {page}: {url}")
            
            try:
                self.driver.get(url)
                time.sleep(3)
                
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # 상품 목록
                items = soup.select('.itemList .itemWrap')
                
                if not items:
                    print(f"  ✅ 페이지 {page}에 상품 없음 - 크롤링 종료")
                    break
                
                before_count = len(all_products)
                
                # 각 상품 파싱
                for item in items:
                    try:
                        # 상품명
                        name_elem = item.select_one('.itemtitle p a')
                        if not name_elem:
                            continue
                        name = name_elem.text.strip()
                        
                        # 가격
                        price_elem = item.select_one('.price')
                        if not price_elem:
                            continue
                        price_text = price_elem.text.strip()
                        # "2,400 원" → 2400
                        price = int(re.sub(r'[^0-9]', '', price_text))
                        
                        # 이미지
                        img_elem = item.select_one('.itemSpImg img')
                        image_url = ''
                        if img_elem and img_elem.get('src'):
                            image_url = img_elem['src']
                        
                        # 상품 데이터
                        product = {
                            'brand_name': '이마트24',
                            'item_name': name,
                            'category': category_name,
                            'price': price,
                            'image_url': image_url,
                        }
                        
                        # 중복 체크
                        if not any(p['item_name'] == name for p in all_products):
                            all_products.append(product)
                    
                    except Exception as e:
                        continue
                
                new_items = len(all_products) - before_count
                print(f"     +{new_items}개 (총 {len(all_products)}개)")
                
                # 상품이 없으면 종료
                if new_items == 0:
                    print(f"  ✅ 더 이상 상품 없음")
                    break
                
                time.sleep(2)  # 페이지 간 대기
                
            except Exception as e:
                print(f"  ❌ 페이지 {page} 오류: {e}")
                break
        
        print(f"\n✅ {category_name} 완료: {len(all_products)}개\n")
        return all_products
    
    def crawl_all(self, skip_all=True):
        """
        전체 카테고리 크롤링
        
        Args:
            skip_all: True면 '전체' 카테고리 건너뛰기 (중복 방지)
        """
        categories = self.get_categories()
        all_products = []
        
        print("=" * 70)
        print("🏪 이마트24 전체 크롤링 시작")
        print("=" * 70)
        
        for cat_name, base_seq in categories.items():
            # '전체' 카테고리 건너뛰기
            if skip_all and cat_name == '전체':
                print(f"⏭️  '{cat_name}' 카테고리 건너뛰기 (중복 방지)\n")
                continue
            
            products = self.crawl_category(cat_name, base_seq, max_pages=10)
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
        print(f"📊 이마트24 전체 수집 완료")
        print("=" * 70)
        print(f"총 상품 수: {len(df)}개")
        print(f"\n카테고리별:")
        print(df['category'].value_counts())
        print(f"\n가격 통계:")
        print(df['price'].describe())
        
        return df
    
    def save_to_csv(self, df, filename='emart24_products.csv'):
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
    print("🚀 이마트24 크롤러 시작")
    print("=" * 70)
    
    crawler = Emart24Crawler(headless=False)
    
    try:
        # 테스트: 도시락 카테고리
        print("\n📝 테스트 모드: 도시락 카테고리\n")
        products = crawler.crawl_category('도시락', '41', max_pages=3)
        
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