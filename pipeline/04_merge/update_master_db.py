import pandas as pd
import os
import sys

def merge_databases():
    """
    [기능]
    1. 크롤링 매칭된 데이터(matched_nutrition_db.csv)를 읽어옵니다.
    2. 마스터 DB(final_nutrition_db.csv)를 읽어옵니다.
    3. 매칭된 데이터를 마스터 DB 형식에 맞춰 변환한 뒤 '병합(Append)'합니다.
    4. 결과를 마스터 DB 파일에 덮어씁니다 (Update).
    """
    
    # ---------------------------------------------------------
    # 1. 파일 경로 자동 설정
    # ---------------------------------------------------------
    # 현재 스크립트(utils/update_master_db.py)의 위치
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 프로젝트 루트 (diet_recommendation/)
    project_root = os.path.dirname(current_dir)
    # 데이터 폴더 (data/processed/)
    data_dir = os.path.join(project_root, 'data', 'processed')
    
    # [수정됨] 마스터 DB 파일명을 final_nutrition_db.csv로 지정
    master_filename = 'final_nutrition_db.csv'
    matched_filename = 'matched_nutrition_db.csv'
    
    master_path = os.path.join(data_dir, master_filename)
    matched_path = os.path.join(data_dir, matched_filename)
    
    print(f"📂 데이터 폴더 경로: {data_dir}")
    print(f"target(Master): {master_filename}")
    print(f"source(Matched): {matched_filename}")

    # ---------------------------------------------------------
    # 2. 데이터 로드
    # ---------------------------------------------------------
    if not os.path.exists(master_path):
        print(f"❌ 오류: 마스터 DB 파일이 없습니다 -> {master_path}")
        # 파일이 없을 경우를 대비해 빈 파일 생성 여부를 물을 수도 있지만, 
        # 여기서는 오류를 출력하고 종료합니다.
        return
        
    if not os.path.exists(matched_path):
        print(f"❌ 오류: 매칭 DB 파일이 없습니다 -> {matched_path}")
        return

    try:
        master_df = pd.read_csv(master_path)
        matched_df = pd.read_csv(matched_path)
    except Exception as e:
        print(f"❌ 데이터 로드 중 오류 발생: {e}")
        return
    
    print(f"✅ 로드 완료!")
    print(f"   - Master DB ({master_filename}): {len(master_df)}건")
    print(f"   - Matched DB ({matched_filename}): {len(matched_df)}건")

    # ---------------------------------------------------------
    # 3. 데이터 병합 (Matched -> Master)
    # ---------------------------------------------------------
    
    # 3-1. Master DB에 'price' 컬럼이 없으면 생성 (기존 데이터는 0 처리)
    if 'price' not in master_df.columns:
        print("ℹ️ Master DB에 'price' 컬럼이 없어 생성합니다.")
        master_df['price'] = 0

    # 3-2. Matched DB를 Master DB 컬럼명에 맞게 변환
    append_df = pd.DataFrame(columns=master_df.columns)
    
    # 컬럼 매핑 (Left: Matched, Right: Master)
    col_mapping = {
        'cleaned_item_name': '식품명',
        'brand_name': '제조사명',
        'price': 'price',
        'FOOD_CODE': 'FOOD_CODE',
        '에너지(kcal)': '에너지(kcal)',
        '단백질(g)': '단백질(g)',
        '지방(g)': '지방(g)',
        '탄수화물(g)': '탄수화물(g)',
        '당류(g)': '당류(g)',
        '나트륨(mg)': '나트륨(mg)',
        '포화지방산(g)': '포화지방산(g)',
        '트랜스지방산(g)': '트랜스지방산(g)',
        '콜레스테롤(mg)': '콜레스테롤(mg)'
    }

    # 매핑 데이터 채우기
    for src, dst in col_mapping.items():
        if src in matched_df.columns and dst in append_df.columns:
            append_df[dst] = matched_df[src]

    # 필수 정보 채우기
    if '데이터구분명' in append_df.columns:
        append_df['데이터구분명'] = append_df['데이터구분명'].fillna('편의점가공식품')
    
    # 3-3. 병합 실행 (Append)
    print("🔄 데이터 병합 중...")
    merged_df = pd.concat([master_df, append_df], ignore_index=True)
    
    # 숫자 컬럼 결측치(NaN) 0으로 채우기
    numeric_cols = ['price', '에너지(kcal)', '단백질(g)', '지방(g)', '탄수화물(g)', '당류(g)', '나트륨(mg)']
    for col in numeric_cols:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce').fillna(0)

    # ---------------------------------------------------------
    # 4. 저장 (덮어쓰기)
    # ---------------------------------------------------------
    # 안전을 위해 백업 파일 생성
    backup_path = master_path.replace('.csv', '_backup.csv')
    master_df.to_csv(backup_path, index=False, encoding='utf-8-sig')
    print(f"📦 원본 백업 완료: {os.path.basename(backup_path)}")

    # 최종 파일 저장 (final_nutrition_db.csv 업데이트)
    merged_df.to_csv(master_path, index=False, encoding='utf-8-sig')
    
    print("=" * 50)
    print(f"✅ 병합 및 업데이트 완료!")
    print(f"📂 저장 파일: {master_path}")
    print(f"📊 최종 데이터 건수: {len(merged_df)}건 (+{len(matched_df)}건 추가됨)")
    print("=" * 50)

if __name__ == "__main__":
    merge_databases()