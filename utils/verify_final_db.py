import pandas as pd
import os
import sys

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import settings
    DATA_RAW_DIR = settings.DATA_RAW
except ImportError:
    DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data_raw')

FINAL_DB_FILE = os.path.join(DATA_RAW_DIR, 'final_nutrition_db.csv')

# 파트너님이 구축한 7개 프랜차이즈 목록 (CSV 파일 내 store_name과 일치해야 함)
TARGET_FRANCHISES = [
    'Momstouch', 'Lotteria', 'BurgerKing', 'McDonalds', 
    'Subway', 'Salady', 'Preppers'
]

def verify_database():
    print(f"📊 최종 데이터베이스 검증 시작: {FINAL_DB_FILE}\n")
    
    if not os.path.exists(FINAL_DB_FILE):
        print("❌ 오류: 최종 DB 파일이 없습니다. 'master_db_merge.py'를 먼저 실행하세요.")
        return

    df = pd.read_csv(FINAL_DB_FILE)
    
    print(f"   ✅ 총 데이터 개수: {len(df)}개")
    print("-------------------------------------------------------------")
    print(f"{'프랜차이즈 (Store)':<15} | {'메뉴 수':<8} | {'평균 가격':<10} | {'가격(0원) 경고'}")
    print("-------------------------------------------------------------")
    
    total_verified = 0
    
    # 각 프랜차이즈별 상태 점검
    for franchise in TARGET_FRANCHISES:
        # 해당 프랜차이즈 데이터 필터링
        franchise_df = df[df['store_name'] == franchise]
        count = len(franchise_df)
        
        if count == 0:
            print(f"❌ {franchise:<15} | 0        | -          | ⚠️ 데이터 없음 (CSV 확인 필요)")
            continue
            
        avg_price = franchise_df['price'].mean()
        zero_price_count = len(franchise_df[franchise_df['price'] == 0])
        
        # 상태 메시지
        status = "✅ 정상"
        if zero_price_count > 0:
            status = f"⚠️ {zero_price_count}개 메뉴 가격 0원!"
            
        print(f"✅ {franchise:<15} | {count:<8} | {int(avg_price):,}원     | {status}")
        total_verified += 1

    print("-------------------------------------------------------------")
    
    if total_verified == 7:
        print("\n🎉 [성공] 7개 프랜차이즈 데이터가 모두 완벽하게 통합되었습니다!")
        print("   이제 AI 식단 추천 알고리즘 개발로 넘어가셔도 좋습니다.")
    else:
        print(f"\n⚠️ [주의] {7 - total_verified}개 프랜차이즈 데이터가 누락되었습니다.")
        print("   data_raw 폴더에 해당 '프랜차이즈_products.csv' 파일이 있는지 확인해주세요.")

if __name__ == '__main__':
    verify_database()