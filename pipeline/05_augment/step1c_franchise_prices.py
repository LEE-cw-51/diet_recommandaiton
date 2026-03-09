"""
Step 1c: food_master 프랜차이즈 메뉴 가격 조회 (Naver webkr 검색)

흐름:
  food_master WHERE price IS NULL AND data_source = 'final_nutrition_db'
    → [Naver webkr 검색] 블로그/웹 스니펫에서 가격 패턴 추출
    → [Gemini 2.5 Flash-Lite] 스니펫 → price 파싱
    → food_master price UPDATE

Naver Shopping API에 미등록된 프랜차이즈 메뉴(McDonalds, BurgerKing 등)의
가격 정보를 블로그/웹 검색으로 보정.

실행:
  python pipeline/05_augment/step1c_franchise_prices.py --test 5   # 5개 테스트
  python pipeline/05_augment/step1c_franchise_prices.py             # 전체 실행
  python pipeline/05_augment/step1c_franchise_prices.py --resume    # 중단 재개
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

CHECKPOINT_FILE = Path(".checkpoint/step1c_done.json")
TABLE = "food_master"

# ──────────────────────────────────────────────────────────────
# Gemini 설정
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


# ──────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """처리 완료된 키 집합 반환. 키 형식: "product_name|brand_name"."""
    if CHECKPOINT_FILE.exists():
        return set(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")))
    return set()


def save_checkpoint(done_keys: set[str]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(
        json.dumps(sorted(done_keys), ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
# Naver webkr 검색
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
    snippets = search_webkr(f"{brand_name} {product_name} 메뉴 가격")
    if snippets:
        return snippets
    return search_webkr(f"{product_name} 가격")


# ──────────────────────────────────────────────────────────────
# Gemini 가격 파싱 (price only)
# ──────────────────────────────────────────────────────────────

def parse_price_from_snippets(
    product_name: str,
    brand_name: str,
    snippets: list[str],
) -> int | None:
    """웹 검색 스니펫에서 price(원 정수) 추출. 없으면 None."""
    if not snippets:
        return None

    snippets_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(snippets[:5]))

    prompt = f"""[제품명] {product_name}
[브랜드] {brand_name}

[Naver 웹 검색 결과 스니펫]
{snippets_text}

위 스니펫에서 "{product_name}"의 판매 가격을 찾아 추출하세요.
가격이 여러 개면 가장 최근 또는 대표적인 가격을 선택.

다음 JSON 형식으로만 응답 (다른 텍스트 금지):
{{"price": <정수(원), 없으면 null>}}

주의: 스니펫에 명확한 가격 정보가 없으면 반드시 null."""

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

def run_step1c(test_n: int | None = None, resume: bool = False) -> None:
    sb = get_client()
    done_keys = load_checkpoint() if resume else set()
    if done_keys:
        print(f"체크포인트 로드: {len(done_keys)}개 이미 처리됨")

    # 대상: price IS NULL AND data_source = 'final_nutrition_db'
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table(TABLE)
            .select("product_name, brand_name")
            .is_("price", "null")
            .eq("data_source", "final_nutrition_db")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        rows.extend(batch)
        offset += 1000

    print(f"대상 (price=NULL, 프랜차이즈): {len(rows)}개")

    if test_n:
        rows = rows[:test_n]

    updated = 0
    no_snippet = 0
    no_price = 0
    fail = 0

    for row in tqdm(rows, desc="Step 1c: 프랜차이즈 가격 조회"):
        key = f"{row['product_name']}|{row.get('brand_name', '')}"
        if key in done_keys:
            continue

        try:
            snippets = get_snippets(row["product_name"], row.get("brand_name") or "")
            time.sleep(0.3)  # Naver API 간격

            if not snippets:
                no_snippet += 1
                done_keys.add(key)
                save_checkpoint(done_keys)
                continue

            price = parse_price_from_snippets(
                row["product_name"],
                row.get("brand_name") or "",
                snippets,
            )

            if price is None:
                no_price += 1
                done_keys.add(key)
                save_checkpoint(done_keys)
                continue

            # price만 UPDATE (brand_name null 분기 처리)
            query = (
                sb.table(TABLE)
                .update({"price": price})
                .eq("product_name", row["product_name"])
            )
            if row.get("brand_name"):
                query = query.eq("brand_name", row["brand_name"])
            else:
                query = query.is_("brand_name", "null")
            query.execute()

            done_keys.add(key)
            save_checkpoint(done_keys)
            updated += 1

        except Exception as e:
            print(f"\n  FAIL [{row['product_name']}]: {e}")
            fail += 1

        time.sleep(3)  # Gemini Flash-Lite RPM 대응

    total = len(rows)
    print(f"\n완료 — 업데이트: {updated}/{total}")
    print(f"  스니펫 없음: {no_snippet}, Gemini price=null: {no_price}, 실패: {fail}")
    print(f"체크포인트: {CHECKPOINT_FILE} ({len(done_keys)}개)")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 1c: 프랜차이즈 메뉴 가격 조회 (Naver webkr → Gemini 파싱)"
    )
    parser.add_argument("--test", type=int, metavar="N", help="N개만 처리 (테스트 모드)")
    parser.add_argument("--resume", action="store_true", help="체크포인트 기반 재개")
    args = parser.parse_args()
    run_step1c(test_n=args.test, resume=args.resume)
