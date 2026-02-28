"""
전체 편의점 통합 크롤러
"""
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

from crawlers.convenience.cu_crawler import CUCrawler
from crawlers.convenience.gs25_crawler import GS25Crawler
from crawlers.convenience.seven_crawler import SevenElevenCrawler
from crawlers.convenience.emart24_crawler import Emart24Crawler


def crawl_all_stores():
    """모든 편의점 크롤링"""

    print("=" * 70)
    print("전체 편의점 크롤링 시작")
    print("=" * 70)
    print("대상: CU, GS25, 세븐일레븐, 이마트24")
    print("=" * 70)

    all_data = []
    save_dir = os.path.join(settings.DATA_RAW, 'convenience')
    os.makedirs(save_dir, exist_ok=True)

    # 1. CU
    print("\n[1/4] CU 크롤링...")
    cu = CUCrawler(headless=True)
    try:
        df_cu = cu.crawl_all_categories()
        if not df_cu.empty:
            all_data.append(df_cu)
            cu.save_to_csv(df_cu, os.path.join(save_dir, 'cu_products.csv'))
    except Exception as e:
        print(f"CU 오류: {e}")
    finally:
        cu.close()

    # 2. GS25
    print("\n[2/4] GS25 크롤링...")
    gs25 = GS25Crawler(headless=True)
    try:
        df_gs25 = gs25.crawl_all(skip_all=True)
        if not df_gs25.empty:
            all_data.append(df_gs25)
            gs25.save_to_csv(df_gs25, os.path.join(save_dir, 'gs25_products.csv'))
    except Exception as e:
        print(f"GS25 오류: {e}")
    finally:
        gs25.close()

    # 3. 세븐일레븐
    print("\n[3/4] 세븐일레븐 크롤링...")
    seven = SevenElevenCrawler(headless=True)
    try:
        df_seven = seven.crawl_all(skip_all=True)
        if not df_seven.empty:
            all_data.append(df_seven)
            seven.save_to_csv(df_seven, os.path.join(save_dir, 'seven_products.csv'))
    except Exception as e:
        print(f"세븐일레븐 오류: {e}")
    finally:
        seven.close()

    # 4. 이마트24
    print("\n[4/4] 이마트24 크롤링...")
    emart24 = Emart24Crawler(headless=True)
    try:
        df_emart24 = emart24.crawl_all(skip_all=True)
        if not df_emart24.empty:
            all_data.append(df_emart24)
            emart24.save_to_csv(df_emart24, os.path.join(save_dir, 'emart24_products.csv'))
    except Exception as e:
        print(f"이마트24 오류: {e}")
    finally:
        emart24.close()

    # 통합 데이터
    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=['brand_name', 'item_name'], keep='first')

        filepath = os.path.join(settings.DATA_RAW, 'all_stores_products.csv')
        df_all.to_csv(filepath, index=False, encoding='utf-8-sig')

        print("\n" + "=" * 70)
        print("전체 크롤링 완료")
        print("=" * 70)
        print(f"총 상품 수: {len(df_all)}개")
        print(f"\n편의점별:")
        print(df_all['brand_name'].value_counts())
        print(f"\n카테고리별:")
        print(df_all['category'].value_counts())
        print(f"\n가격 통계:")
        print(df_all['price'].describe())
        print(f"\n통합 파일: {filepath}")

        return df_all
    else:
        print("\n수집된 데이터가 없습니다.")
        return pd.DataFrame()


if __name__ == "__main__":
    crawl_all_stores()
