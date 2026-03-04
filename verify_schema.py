"""
Supabase food_master 스키마 검증 스크립트
SQL 마이그레이션 실행 후 이 파일을 실행해 컬럼이 정상 추가됐는지 확인

실행: python verify_schema.py
"""
import sys
import os
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]

print("Supabase food_master 스키마 확인 중...\n")

# PostgREST OpenAPI 스키마에서 컬럼 목록 확인
resp = requests.get(f"{url}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"})
cols = list(resp.json()["definitions"]["food_master"]["properties"].keys())

print(f"현재 컬럼 ({len(cols)}개):")
for c in cols:
    print(f"  - {c}")

required = ["allergens", "raw_label_text", "augmented_at", "classified_at"]
print()
for col in required:
    status = "✅" if col in cols else "❌ 없음 - SQL 마이그레이션 필요"
    print(f"  {col}: {status}")

all_ok = all(c in cols for c in required)
print()
if all_ok:
    print("✅ 스키마 OK - Step 1 실행 가능")
    print("   python pipeline/05_augment/step1_price_allergen.py --test 5")
else:
    print("❌ SQL 마이그레이션 필요 - supabase/migrations/001_add_allergens.sql 실행 후 재확인")
