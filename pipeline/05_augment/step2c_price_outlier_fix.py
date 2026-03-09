"""
Step 2c: price 이상치 처리 (IQR 기반 탐지 + Naver webkr 재검색)

흐름:
  food_master (price 전체) → pandas IQR fence 계산 (카테고리별)
    → HIGH 이상치 (price > high_fence) 목록 추출
    → [Naver webkr 재검색] → [Gemini 2.5 Flash-Lite] price 파싱
    → 새 가격 ≤ fence AND ≥ 500: UPDATE / 실패·여전히 이상치: NULL

Phase 1 (LOW 이상치 16개): Supabase SQL Editor에서 직접 실행
  UPDATE food_master SET price = NULL WHERE price < 500;

Phase 2 (HIGH 이상치 126개): 이 스크립트로 처리

실행:
  python pipeline/05_augment/step2c_price_outlier_fix.py --test 5   # 5개 테스트
  python pipeline/05_augment/step2c_price_outlier_fix.py             # 전체 실행
  python pipeline/05_augment/step2c_price_outlier_fix.py --resume    # 중단 재개
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Windows cp949 터미널에서 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가 (CLAUDE.md §10)
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from google import genai
from google.genai import types as genai_types
from tqdm import tqdm

from db.client import get_client

# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

CHECKPOINT_FILE = Path(".checkpoint/step2c_done.json")
TABLE = "food_master"

# Tukey's Fence 계수 (표준값 1.5)
IQR_MULTIPLIER = 1.5

# 가격 하한 절대값 (단품 최소 가격 기준)
PRICE_FLOOR = 500

# ──────────────────────────────────────────────────────────────
# Gemini 설정
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


# ──────────────────────────────────────────────────────────────
# 체크포인트 (키: str(id))
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """처리 완료된 ID 집합 반환. 키 형식: str(id)."""
    if CHECKPOINT_FILE.exists():
        return set(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")))
    return set()


def save_checkpoint(done_ids: set[str]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(
        json.dumps(sorted(done_ids), ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
# Supabase 데이터 수집
# ──────────────────────────────────────────────────────────────

def fetch_all_prices() -> pd.DataFrame:
    """
    food_master에서 price IS NOT NULL인 전체 행을 DataFrame으로 반환.
    컬럼: id, product_name, brand_name, category_type, price
    """
    sb = get_client()
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table(TABLE)
            .select("id, product_name, brand_name, category_type, price")
            .not_.is_("price", "null")
            .not_.is_("category_type", "null")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        rows.extend(batch)
        offset += 1000
    df = pd.DataFrame(rows)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna(subset=["price"])


# ──────────────────────────────────────────────────────────────
# IQR Fence 계산
# ──────────────────────────────────────────────────────────────

def compute_fences(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """
    카테고리별 Tukey's Fence (IQR 1.5×) 계산.
    반환: {category_type: (low_fence, high_fence)}
    하한 fence는 PRICE_FLOOR(500)으로 clamp.
    """
    fences: dict[str, tuple[float, float]] = {}
    for cat, grp in df.groupby("category_type"):
        q1 = grp["price"].quantile(0.25)
        q3 = grp["price"].quantile(0.75)
        iqr = q3 - q1
        low_fence = max(PRICE_FLOOR, q1 - IQR_MULTIPLIER * iqr)
        high_fence = q3 + IQR_MULTIPLIER * iqr
        fences[str(cat)] = (low_fence, high_fence)
        print(f"  [{cat}] Q1={q1:,.0f} Q3={q3:,.0f} IQR={iqr:,.0f} "
              f"→ fence [{low_fence:,.0f} ~ {high_fence:,.0f}]")
    return fences


def get_high_outliers(df: pd.DataFrame, fences: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """HIGH 이상치 행(price > high_fence) 반환."""
    mask = pd.Series(False, index=df.index)
    for cat, (_, high_fence) in fences.items():
        cat_mask = (df["category_type"] == cat) & (df["price"] > high_fence)
        mask = mask | cat_mask
    outliers = df[mask].copy()
    outliers["high_fence"] = outliers["category_type"].map(
        lambda c: fences.get(c, (PRICE_FLOOR, float("inf")))[1]
    )
    return outliers.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────
# Naver webkr 검색 (step1c에서 재사용)
# ──────────────────────────────────────────────────────────────

def search_webkr(query: str, display: int = 5) -> list[str]:
    """Naver webkr 검색 → description(snippet) 리스트 반환."""
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/webkr.json",
            headers={
                "X-Naver-Client-Id":     os.environ["NAVER_CLIENT_ID"],
                "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
            },
            params={"query": query, "display": display},
            timeout=10,
        )
        res.raise_for_status()
        items = res.json().get("items", [])
        snippets = []
        for item in items:
            desc = item.get("description", "") or ""
            desc = re.sub(r"<[^>]+>", "", desc).strip()  # HTML 태그 제거
            if desc:
                snippets.append(desc)
        return snippets
    except Exception as e:
        print(f"  [Naver webkr] 검색 실패: {e}")
        return []


def get_snippets(product_name: str, brand_name: str) -> list[str]:
    """Primary 쿼리 → Fallback 쿼리 순으로 스니펫 수집."""
    brand = (brand_name or "").strip()
    if brand:
        snippets = search_webkr(f"{brand} {product_name} 가격")
    else:
        snippets = search_webkr(f"{product_name} 가격")
    if snippets:
        return snippets
    return search_webkr(f"{product_name} 단품 가격")


# ──────────────────────────────────────────────────────────────
# Gemini 가격 파싱 (step1c에서 재사용)
# ──────────────────────────────────────────────────────────────

def parse_price_from_snippets(
    product_name: str,
    brand_name: str,
    snippets: list[str],
) -> int | None:
    """웹 검색 스니펫에서 단품 price(원 정수) 추출. 없으면 None."""
    if not snippets:
        return None

    snippets_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(snippets[:5]))

    prompt = f"""[제품명] {product_name}
[브랜드] {brand_name or "미상"}

[Naver 웹 검색 결과 스니펫]
{snippets_text}

위 스니펫에서 "{product_name}"의 단품 판매 가격을 찾아 추출하세요.
- 세트 메뉴, 묶음 할인, 다수량 패키지 가격은 제외하고 단품 가격만 추출
- 가격이 여러 개면 가장 최근 또는 대표적인 단품 가격 선택

다음 JSON 형식으로만 응답 (다른 텍스트 금지):
{{"price": <정수(원), 없으면 null>}}

주의: 단품 가격이 명확하지 않으면 반드시 null."""

    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        try:
            response = _gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                m = re.search(r"retry[^\d]*(\d+)", str(e), re.IGNORECASE)
                delay = int(m.group(1)) + 5 if m else 35
                print(f"\n  [Gemini] Rate limit, {delay}s 대기 후 재시도 ({attempt + 1}/{MAX_RETRIES - 1})...")
                time.sleep(delay)
            else:
                raise

    parsed = json.loads(response.text)
    price = parsed.get("price")
    if price is None:
        return None
    try:
        return int(price)
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

def run_step2c(test_n: int | None = None, resume: bool = False) -> None:
    sb = get_client()
    done_ids = load_checkpoint() if resume else set()
    if done_ids:
        print(f"체크포인트 로드: {len(done_ids)}개 이미 처리됨")

    # 1. 전체 price 데이터 fetch → pandas IQR 계산
    print("\n[1/3] food_master price 데이터 수집 중...")
    df = fetch_all_prices()
    print(f"  유효 price 행: {len(df)}개")

    print("\n[2/3] 카테고리별 IQR Fence 계산:")
    fences = compute_fences(df)

    # 2. HIGH 이상치 추출
    outliers = get_high_outliers(df, fences)
    print(f"\n  HIGH 이상치 탐지: {len(outliers)}개")
    for cat in outliers["category_type"].value_counts().index:
        cnt = (outliers["category_type"] == cat).sum()
        print(f"    {cat}: {cnt}개")

    if test_n:
        outliers = outliers.head(test_n)
        print(f"  테스트 모드: {test_n}개만 처리")

    # 3. 각 이상치 Naver 재검색
    print(f"\n[3/3] HIGH 이상치 {len(outliers)}개 재검색 시작...")

    updated = 0       # fence 내 새 가격으로 UPDATE
    nulled = 0        # NULL 처리 (재검색 실패 또는 여전히 이상치)
    no_snippet = 0    # 스니펫 없음
    no_price = 0      # Gemini price=null
    still_high = 0    # 새 가격도 fence 초과
    fail = 0          # 예외

    for _, row in tqdm(outliers.iterrows(), total=len(outliers), desc="Step 2c: 이상치 재검색"):
        row_id = str(row["id"])
        if row_id in done_ids:
            continue

        product_name = row["product_name"]
        brand_name   = row.get("brand_name") or ""
        old_price    = int(row["price"])
        high_fence   = row["high_fence"]
        category     = row["category_type"]

        try:
            snippets = get_snippets(product_name, brand_name)
            time.sleep(0.3)  # Naver API 간격

            if not snippets:
                print(f"  [스니펫 없음] {product_name} ({category}, 기존: {old_price:,}원) → NULL")
                sb.table(TABLE).update({"price": None}).eq("id", row["id"]).execute()
                no_snippet += 1
                nulled += 1
                done_ids.add(row_id)
                save_checkpoint(done_ids)
                continue

            new_price = parse_price_from_snippets(product_name, brand_name, snippets)

            if new_price is None:
                print(f"  [Gemini null] {product_name} ({category}, 기존: {old_price:,}원) → NULL")
                sb.table(TABLE).update({"price": None}).eq("id", row["id"]).execute()
                no_price += 1
                nulled += 1
                done_ids.add(row_id)
                save_checkpoint(done_ids)
                time.sleep(1)
                continue

            # fence 판정
            if PRICE_FLOOR <= new_price <= high_fence:
                print(f"  [UPDATE] {product_name}: {old_price:,} → {new_price:,}원 (fence ≤ {high_fence:,.0f})")
                sb.table(TABLE).update({"price": new_price}).eq("id", row["id"]).execute()
                updated += 1
            else:
                print(f"  [NULL] {product_name}: new={new_price:,}원 여전히 이상치 (fence ≤ {high_fence:,.0f}) → NULL")
                sb.table(TABLE).update({"price": None}).eq("id", row["id"]).execute()
                still_high += 1
                nulled += 1

            done_ids.add(row_id)
            save_checkpoint(done_ids)

        except Exception as e:
            print(f"\n  FAIL [{product_name}]: {e}")
            fail += 1

        time.sleep(1)  # Gemini Flash-Lite RPM 대응

    total = len(outliers)
    print(f"\n완료 — 총 {total}개 처리")
    print(f"  UPDATE (fence 내 새 가격): {updated}개")
    print(f"  NULL 처리 합계:            {nulled}개")
    print(f"    - 스니펫 없음:           {no_snippet}개")
    print(f"    - Gemini price=null:     {no_price}개")
    print(f"    - 새 가격도 이상치:       {still_high}개")
    print(f"  예외/실패:                 {fail}개")
    print(f"체크포인트: {CHECKPOINT_FILE} ({len(done_ids)}개)")

    # Phase 3 브라우저 확인 대상 안내
    print("\n[Phase 3 브라우저 확인 대상]")
    print("재검색 후 NULL 처리된 항목 중 고가 의심 우선순위:")
    print("  - 162,360원 × 3개 (SOUP, 같은 가격 반복 → 묶음 의심)")
    print("  - 960,000원 (DRINK → 와인/고급 음료 가능성)")
    print("  - 229,100원 (SNACK → 세트 상품 가능성)")
    print("  → Claude in Chrome MCP: https://search.shopping.naver.com/search/all?query={제품명}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 2c: price HIGH 이상치 재검색 (Naver webkr → Gemini 파싱)"
    )
    parser.add_argument("--test", type=int, metavar="N", help="N개만 처리 (테스트 모드)")
    parser.add_argument("--resume", action="store_true", help="체크포인트 기반 재개")
    args = parser.parse_args()
    run_step2c(test_n=args.test, resume=args.resume)
