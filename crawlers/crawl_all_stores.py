"""
전체 편의점 통합 크롤러
"""
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

from cu_crawler_final import CUCrawler
from gs25_crawler import GS25Crawler
from seven_crawler import SevenElevenCrawler
from emart24_crawler import Emart24Crawler  # 추가


def crawl_all_stores():
    """모든 편의점 크롤링"""
    
    print("=" * 70)
    print("🏪 전체 편의점 크롤링 시작")
    print("=" * 70)
    print("대상: CU, GS25, 세븐일레븐, 이마트24")  # 수정
    print("=" * 70)
    
    all_data = []
    
    # 1. CU
    print("\n[1/4] CU 크롤링...")
    cu = CUCrawler(headless=True)
    try:
        df_cu = cu.crawl_all_categories()
        if not df_cu.empty:
            all_data.append(df_cu)
            cu.save_to_csv(df_cu, 'cu_products.csv')
    except Exception as e:
        print(f"❌ CU 오류: {e}")
    finally:
        cu.close()
    
    # 2. GS25
    print("\n[2/4] GS25 크롤링...")
    gs25 = GS25Crawler(headless=True)
    try:
        df_gs25 = gs25.crawl_all(skip_all=True)
        if not df_gs25.empty:
            all_data.append(df_gs25)
            gs25.save_to_csv(df_gs25, 'gs25_products.csv')
    except Exception as e:
        print(f"❌ GS25 오류: {e}")
    finally:
        gs25.close()
    
    # 3. 세븐일레븐
    print("\n[3/4] 세븐일레븐 크롤링...")
    seven = SevenElevenCrawler(headless=True)
    try:
        df_seven = seven.crawl_all(skip_all=True)
        if not df_seven.empty:
            all_data.append(df_seven)
            seven.save_to_csv(df_seven, 'seven_products.csv')
    except Exception as e:
        print(f"❌ 세븐일레븐 오류: {e}")
    finally:
        seven.close()
    
    # 4. 이마트24 (추가)
    print("\n[4/4] 이마트24 크롤링...")
    emart24 = Emart24Crawler(headless=True)
    try:
        df_emart24 = emart24.crawl_all(skip_all=True)
        if not df_emart24.empty:
            all_data.append(df_emart24)
            emart24.save_to_csv(df_emart24, 'emart24_products.csv')
    except Exception as e:
        print(f"❌ 이마트24 오류: {e}")
    finally:
        emart24.close()
    
    # 통합 데이터
    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=['brand_name', 'item_name'], keep='first')
        
        # 통합 파일 저장
        filepath = os.path.join(settings.DATA_RAW, 'all_stores_products.csv')
        df_all.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print("\n" + "=" * 70)
        print("📊 전체 크롤링 완료")
        print("=" * 70)
        print(f"총 상품 수: {len(df_all)}개")
        print(f"\n편의점별:")
        print(df_all['brand_name'].value_counts())
        print(f"\n카테고리별:")
        print(df_all['category'].value_counts())
        print(f"\n가격 통계:")
        print(df_all['price'].describe())
        print(f"\n💾 통합 파일: {filepath}")
        
        return df_all
    else:
        print("\n❌ 수집된 데이터가 없습니다.")
        return pd.DataFrame()


if __name__ == "__main__":
    crawl_all_stores()
```

---

## 최종 완성! 🎉

### 크롤러 목록 ✅
```
crawlers/
├── cu_crawler_final.py       ✅ CU
├── gs25_crawler.py            ✅ GS25
├── seven_crawler.py           ✅ 세븐일레븐
├── emart24_crawler.py         ✅ 이마트24 (NEW!)
└── crawl_all_stores.py        ✅ 통합 (4개 편의점)