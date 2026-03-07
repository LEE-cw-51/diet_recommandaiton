"""
검색 클라이언트 모듈
- 네이버 쇼핑 API: 가격 검색 (무료 1,000 req/일)
- HACCP 포장지표기정보 API: 알레르기/원재료 공식 데이터 (무료)
- 검색 결과 JSON 캐싱: data/raw/search_cache/{id}.json
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path("data/raw/search_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# A. 네이버 쇼핑 API (가격)
# ──────────────────────────────────────────────────────────────

def search_naver_price(query: str, display: int = 5) -> list[dict]:
    """네이버 쇼핑 API로 판매 가격 검색.

    Args:
        query: 검색어 (예: "CJ 비비고 김치볶음밥")
        display: 최대 결과 수 (기본 5)

    Returns:
        [{"title": str, "lprice": str, "mall": str}, ...]
        빈 리스트: API 오류 또는 결과 없음
    """
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id":     os.environ["NAVER_CLIENT_ID"],
                "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
            },
            params={"query": query, "display": display, "sort": "sim"},
            timeout=10,
        )
        res.raise_for_status()
        items = res.json().get("items", [])
        return [
            {
                "title":  item.get("title", ""),
                "lprice": item.get("lprice", ""),
                "mall":   item.get("mallName", ""),
            }
            for item in items
        ]
    except requests.RequestException as e:
        print(f"  [Naver] 오류: {e}")
        return []


# ──────────────────────────────────────────────────────────────
# B. HACCP 포장지표기정보 API (알레르기/원재료 공식 데이터)
# ──────────────────────────────────────────────────────────────

HACCP_BASE_URL = "https://apis.data.go.kr/B553748/CertImgListServiceV3"
# ↑ V3 서비스 베이스 URL (2026-03-04 확정)
# TODO: data.go.kr에서 V3 오퍼레이션 전체 경로 확인 필요
#       V1 예시: /B553748/CertImgListService/getCertImgList
#       V3 예시(추정): /B553748/CertImgListServiceV3/getCertImgListV3
#       → 실제 오퍼레이션 경로 확인 후 URL 끝에 추가 필요할 수 있음


def search_haccp_label(product_name: str, brand_name: str) -> dict:
    """식품안전정보원 HACCP 포장지표기정보 API 조회.

    Args:
        product_name: 제품명 (food_research_sample.product_name)
        brand_name:   제조사/업소명 (food_research_sample.brand_name)

    Returns:
        dict 항목 예시:
        {
          "prdlstNm": "제품명",
          "bsshNm":   "업소명",
          "rawmtrl":  "원재료명 및 함량 전문",
          "allrgInfo": "알레르기 표시 문구",
          ...
        }
        빈 dict: 제품 미조회 또는 API 오류 (Fallback: Gemini가 제품명으로 추론)
    """
    try:
        res = requests.get(
            HACCP_BASE_URL,
            params={
                "serviceKey": os.environ["HACCP_API_KEY"],
                "prdlstNm":   product_name,
                "bsshNm":     brand_name,
                "pageNo":     1,
                "numOfRows":  5,
                "returnType": "json",
            },
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()

        # 응답 구조: body.items.item (단일 dict 또는 list)
        body = data.get("body", {})
        if not body:
            # 일부 에러 응답은 body 없이 resultCode만 반환
            return {}

        items_wrapper = body.get("items")
        if not items_wrapper:
            return {}

        items = items_wrapper.get("item", [])
        if isinstance(items, dict):
            items = [items]  # 단일 결과 → 리스트 변환

        return items[0] if items else {}

    except requests.RequestException as e:
        print(f"  [HACCP] 오류: {e}")
        return {}
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"  [HACCP] 파싱 오류: {e}")
        return {}


# ──────────────────────────────────────────────────────────────
# 캐시 관리
# ──────────────────────────────────────────────────────────────

def get_or_fetch(row: dict, delay: float = 0.5) -> dict:
    """캐시 우선 → 없으면 두 API 모두 호출 후 JSON 저장.

    Args:
        row:   {"id": int, "product_name": str, "brand_name": str,
                "standard_product_name": str (optional, fallback용)}
        delay: API 호출 간 대기 시간 (초)

    Returns:
        {
          "id": int,
          "query": str,
          "naver_results": [...],
          "naver_fallback_results": [...],  # standard_product_name 재시도 결과
          "haccp_label": {...}
        }
    """
    cache_file = CACHE_DIR / f"{row['id']}.json"

    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        # 이미 fallback 시도됨 → 그대로 반환
        if "naver_fallback_results" in cached:
            return cached
        # primary 결과 없고 standard_product_name으로 재시도 가능
        std_name = row.get("standard_product_name") or ""
        if not cached.get("naver_results") and std_name:
            print(f"  [Naver] fallback: {std_name}")
            cached["naver_fallback_results"] = search_naver_price(std_name)
            time.sleep(delay)
            cache_file.write_text(
                json.dumps(cached, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return cached

    query = f"{row['brand_name']} {row['product_name']}"
    naver_results = search_naver_price(query)
    time.sleep(delay)
    haccp_label = search_haccp_label(row["product_name"], row["brand_name"])

    result = {
        "id":            row["id"],
        "query":         query,
        "naver_results": naver_results,
        "haccp_label":   haccp_label,
    }

    # primary 결과 없으면 standard_product_name으로 fallback
    std_name = row.get("standard_product_name") or ""
    if not naver_results and std_name:
        print(f"  [Naver] fallback: {std_name}")
        time.sleep(delay)
        result["naver_fallback_results"] = search_naver_price(std_name)

    cache_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


# ──────────────────────────────────────────────────────────────
# 단독 실행 테스트
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    test_row = {
        "id":           99999,
        "product_name": "비비고 왕교자",
        "brand_name":   "CJ제일제당",
    }
    print(f"Testing with: {test_row['brand_name']} {test_row['product_name']}")
    result = get_or_fetch(test_row)
    print(f"Naver results ({len(result['naver_results'])}): {result['naver_results'][:1]}")
    print(f"HACCP label keys: {list(result['haccp_label'].keys())}")
    cache_path = CACHE_DIR / f"{test_row['id']}.json"
    print(f"Cache file: {cache_path}")
