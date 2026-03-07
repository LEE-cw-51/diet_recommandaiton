"""
Step 1b: food_master에서 price=null인 항목 가격 보정

Step 1 실행 중 네이버 미조회로 price=null이 된 항목들에 대해
standard_product_name으로 fallback 검색 후 가격만 업데이트.

실행:
  python pipeline/05_augment/step1b_fix_null_prices.py --test 5
  python pipeline/05_augment/step1b_fix_null_prices.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Windows cp949 터미널에서 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tqdm import tqdm

from db.client import get_client
from search_clients import get_or_fetch
from step1_price_allergen import parse_with_gemini


def run_step1b(test_n: int | None = None) -> None:
    """price=null 항목에 대해 fallback 검색 후 가격 보정."""
    sb = get_client()

    # 1. food_research_sample 전체 로드 → (product_name, brand_name) → row 매핑
    print("food_research_sample 로드 중...")
    sample_rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table("food_research_sample")
            .select("id, product_name, brand_name, main_category, standard_product_name")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        sample_rows.extend(batch)
        offset += 1000
    sample_map = {(r["product_name"], r["brand_name"]): r for r in sample_rows}
    print(f"  → {len(sample_rows)}개 로드")

    # 2. food_master에서 price=null 항목 로드
    print("food_master price=null 항목 로드 중...")
    null_price_rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table("food_master")
            .select("product_name, brand_name")
            .is_("price", "null")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        null_price_rows.extend(batch)
        offset += 1000
    print(f"  → price=null 항목: {len(null_price_rows)}개")

    if test_n:
        null_price_rows = null_price_rows[:test_n]

    updated = 0
    no_naver = 0  # 네이버 결과 없어서 스킵
    no_price = 0  # Gemini가 price=null로 판단
    no_match = 0  # food_research_sample에 없는 항목

    for fm_row in tqdm(null_price_rows, desc="Step 1b: 가격 보정"):
        key = (fm_row["product_name"], fm_row["brand_name"])
        sample_row = sample_map.get(key)
        if not sample_row:
            no_match += 1
            continue

        try:
            # 캐시에 없으면 API 호출, 있으면 fallback 결과 추가
            data = get_or_fetch(sample_row, delay=0.3)
            time.sleep(0.5)

            best_naver = data.get("naver_results") or data.get("naver_fallback_results", [])
            if not best_naver:
                no_naver += 1
                continue

            result = parse_with_gemini(
                sample_row["product_name"],
                sample_row["brand_name"],
                best_naver,
                data["haccp_label"],
                main_category=sample_row.get("main_category") or "",
                standard_product_name=sample_row.get("standard_product_name") or "",
            )

            price = result.get("price")
            if price is None:
                no_price += 1
                continue

            # price만 업데이트 (allergens 등 기존 값 유지)
            query = (
                sb.table("food_master")
                .update({"price": price})
                .eq("product_name", fm_row["product_name"])
            )
            if fm_row.get("brand_name"):
                query = query.eq("brand_name", fm_row["brand_name"])
            else:
                query = query.is_("brand_name", "null")
            query.execute()

            updated += 1

        except Exception as e:
            print(f"\n  FAIL [{fm_row['product_name']}]: {e}")

        time.sleep(3)  # Flash-Lite RPM 제한 대응

    total = len(null_price_rows)
    print(f"\n완료 — 업데이트: {updated}/{total}")
    print(f"  네이버 결과 없음: {no_naver}, Gemini price=null: {no_price}, 매핑 없음: {no_match}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 1b: price=null 가격 보정")
    parser.add_argument("--test", type=int, metavar="N", help="N개만 처리 (테스트 모드)")
    args = parser.parse_args()
    run_step1b(test_n=args.test)
