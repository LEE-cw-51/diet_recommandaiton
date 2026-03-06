"""
Step 0: food_research_sample → food_master 영양성분 bulk copy

흐름:
  food_research_sample (2,524행)
    → food_master INSERT (ON CONFLICT DO NOTHING)
    → 영양성분(calories, protein, fat, carbs, sugar, sodium) + food_group 복사

실행:
  python pipeline/05_augment/step0_bulk_copy.py --test 5   # 5개 테스트
  python pipeline/05_augment/step0_bulk_copy.py             # 전체 실행
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows cp949 터미널에서 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from tqdm import tqdm

from db.client import get_client

# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

BATCH_SIZE = 100  # PostgREST payload 한도 대응

SELECT_COLS = (
    "id,product_name,brand_name,"
    "calories,protein,fat,carbs,sugar,sodium,"
    "main_category"
)


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

def run_step0(test_n: int | None = None, table: str = "food_master") -> None:
    sb = get_client()

    # 1. food_research_sample 전체 로드 (pagination for 2,524 rows)
    rows = []
    limit = 1000
    offset = 0
    while True:
        batch = sb.table("food_research_sample").select(SELECT_COLS).range(offset, offset + limit - 1).execute().data
        if not batch:
            break
        rows.extend(batch)
        offset += limit

    # 배치 내 중복으로 인한 UPSERT 오류 방지: (product_name, brand_name) 기준 중복 제거
    seen: set = set()
    deduped = []
    for r in rows:
        key = (r["product_name"], r["brand_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    if len(deduped) < len(rows):
        print(f"중복 제거: {len(rows)} → {len(deduped)}개")
    rows = deduped

    if test_n:
        rows = rows[:test_n]

    print(f"복사 대상: {len(rows)}개  →  {table}")

    # 2. 배치 변환 및 UPSERT (ignore_duplicates=True → ON CONFLICT DO NOTHING)
    success = 0
    fail = 0
    batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Step 0: bulk copy"):
        records = []
        for r in batch:
            records.append({
                "product_name": r["product_name"],
                "brand_name":   r.get("brand_name"),
                "calories":     r.get("calories"),
                "protein":      r.get("protein"),
                "fat":          r.get("fat"),
                "carbs":        r.get("carbs"),
                "sugar":        r.get("sugar"),
                "sodium":       r.get("sodium"),
                "food_group":   r.get("main_category"),
                "data_source":  "food_research_sample",
                "is_verified":  False,
            })

        try:
            sb.table(table).upsert(
                records,
                on_conflict="product_name,brand_name",
            ).execute()
            success += len(records)
        except Exception as e:
            print(f"\n  BATCH FAIL: {e}")
            fail += len(records)

    # 3. 결과 확인
    count = sb.table(table).select("id", count="exact").execute().count
    print(f"\n완료 — 삽입 시도: {success}, 실패: {fail}")
    print(f"{table} 현재 행 수: {count}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 0: food_research_sample → food_master 영양성분 bulk copy"
    )
    parser.add_argument(
        "--test",
        type=int,
        metavar="N",
        help="N개만 처리 (테스트 모드)",
    )
    parser.add_argument(
        "--table",
        default="food_master",
        help="대상 테이블명 (기본값: food_master)",
    )
    args = parser.parse_args()
    run_step0(test_n=args.test, table=args.table)
