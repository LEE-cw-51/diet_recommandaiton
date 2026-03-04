"""
Step 1: 가격 + 알레르기 데이터 증강 파이프라인

흐름:
  food_research_sample (2,524행)
    → [네이버 쇼핑 API + HACCP API] → data/raw/search_cache/{id}.json
    → [Gemini 1.5 Flash 파싱]
    → food_master UPSERT (price + allergens + raw_label_text)

실행:
  python pipeline/05_augment/step1_price_allergen.py --test 5   # 5개 테스트
  python pipeline/05_augment/step1_price_allergen.py             # 전체 실행
  python pipeline/05_augment/step1_price_allergen.py --resume    # 중단 재개
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Windows cp949 터미널에서 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from google import genai
from google.genai import types as genai_types
from tqdm import tqdm

from db.client import get_client

# pipeline/05_augment/ 은 숫자로 시작해 직접 import 불가 → 동일 디렉토리 경로 추가
sys.path.insert(0, str(Path(__file__).parent))
from search_clients import get_or_fetch  # noqa: E402

# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

ALLERGEN_22 = [
    "난류", "우유", "메밀", "땅콩", "대두", "밀", "고등어", "게",
    "새우", "돼지고기", "복숭아", "토마토", "아황산류", "호두",
    "닭고기", "쇠고기", "오징어", "조개류", "잣", "아몬드", "캐슈넛", "키위",
]

CHECKPOINT_FILE = Path(".checkpoint/step1_done.json")

# ──────────────────────────────────────────────────────────────
# Gemini 설정 (google-genai SDK)
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


# ──────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[int]:
    """처리 완료된 food_research_sample.id 집합 반환."""
    if CHECKPOINT_FILE.exists():
        return set(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")))
    return set()


def save_checkpoint(done_ids: set[int]) -> None:
    """처리 완료 ID 집합을 파일에 저장."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(
        json.dumps(sorted(done_ids), ensure_ascii=False),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
# Gemini 파싱
# ──────────────────────────────────────────────────────────────

def parse_with_gemini(
    product_name: str,
    brand_name: str,
    naver_results: list[dict],
    haccp_label: dict,
) -> dict:
    """Gemini 1.5 Flash로 검색 결과를 구조화 JSON으로 파싱.

    Returns:
        {
          "price": int | None,        # 최저판매가 (원)
          "allergens": {알레르기명: bool, ...},  # 22종 전부 포함
          "confidence": float         # 0.0~1.0 (HACCP 데이터 있으면 0.9 이상)
        }
    """
    raw_label    = haccp_label.get("rawmtrl", "") or ""      # 원재료명
    allergen_txt = haccp_label.get("allrgInfo", "") or raw_label  # 알레르기 표시

    allergen_fields = "\n".join(
        f'    "{a}": true 또는 false' for a in ALLERGEN_22
    )

    prompt = f"""[제품 정보]
제품명: {product_name} / 제조사: {brand_name}

[HACCP 공식 원재료명 및 알레르기 표시 (최우선 참고)]
원재료명: {raw_label[:1000]}
알레르기표시: {allergen_txt[:500]}

[네이버 쇼핑 가격 정보]
{json.dumps(naver_results[:3], ensure_ascii=False)}

다음 JSON 형식으로만 응답하세요 (다른 텍스트 금지):
{{
  "price": <최저판매가(원 정수), 없으면 null>,
  "allergens": {{
{allergen_fields}
  }},
  "confidence": <0.0~1.0 (HACCP 데이터 있으면 0.9 이상, 없으면 0.5 이하)>
}}

주의사항:
- HACCP 원재료명/알레르기 표시를 최우선 참고
- 원재료명에 명확히 나타난 성분만 true, 불확실하면 false
- 가격은 naver_results 중 lprice 최솟값 사용 (lprice는 원 단위 문자열)
"""

    response = _gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    parsed = json.loads(response.text)

    # allergens에 22종 키가 모두 있는지 보장 (누락 키 → false 기본값)
    allergens = parsed.get("allergens", {})
    for allergen in ALLERGEN_22:
        if allergen not in allergens:
            allergens[allergen] = False
    parsed["allergens"] = allergens

    return parsed


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

def run_step1(test_n: int | None = None, resume: bool = False) -> None:
    """Step 1 파이프라인 실행.

    Args:
        test_n: 처리할 최대 행 수 (None → 전체)
        resume: True면 체크포인트 기반 재개
    """
    sb = get_client()

    done_ids = load_checkpoint() if resume else set()
    if done_ids:
        print(f"체크포인트 로드: {len(done_ids)}개 이미 처리됨")

    # food_research_sample 에서 처리 대상 로드
    rows = (
        sb.table("food_research_sample")
        .select("id, product_name, brand_name")
        .execute()
        .data
    )
    if test_n:
        rows = rows[:test_n]

    print(f"처리 대상: {len(rows)}개 (전체 food_research_sample 중)")
    success = 0
    fail    = 0

    for row in tqdm(rows, desc="Step 1: 가격+알레르기"):
        if row["id"] in done_ids:
            continue

        try:
            # 1. 검색 (캐시 우선)
            data = get_or_fetch(row, delay=0.3)
            time.sleep(0.7)  # Naver 1,000 req/일 → 최소 0.086초 간격; 여유 있게

            # 2. Gemini 파싱
            result = parse_with_gemini(
                row["product_name"],
                row["brand_name"],
                data["naver_results"],
                data["haccp_label"],
            )

            # 3. Supabase UPSERT
            # allergens 컬럼이 스키마 캐시에 없으면 PGRST204 발생
            # → Supabase Dashboard > Settings > API > "Reload API Schema" 후 재시도
            upsert_data = {
                "product_name":   row["product_name"],
                "brand_name":     row["brand_name"],
                "price":          result.get("price"),
                "allergens":      result.get("allergens", {}),
                "raw_label_text": data["haccp_label"].get("rawmtrl", ""),
                "is_verified":    False,
                "data_source":    "haccp_naver_augmented",
                "augmented_at":   "now()",
            }
            resp = sb.table("food_master").upsert(
                upsert_data,
                on_conflict="product_name,brand_name",
            ).execute()
            # PostgREST는 에러 시 빈 data 반환하지 않고 예외를 던지므로
            # execute() 자체가 성공하면 정상 처리됨

            done_ids.add(row["id"])
            save_checkpoint(done_ids)
            success += 1

        except Exception as e:
            print(f"\n  FAIL [{row['id']}] {row['product_name']}: {e}")
            fail += 1

        time.sleep(0.5)  # Gemini rate limit 대응

    print(f"\n완료 — 성공: {success}, 실패: {fail}")
    print(f"체크포인트: {CHECKPOINT_FILE} ({len(done_ids)}개)")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 1: 가격+알레르기 데이터 증강 파이프라인"
    )
    parser.add_argument(
        "--test",
        type=int,
        metavar="N",
        help="N개만 처리 (테스트 모드)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="체크포인트 기반 재개",
    )
    args = parser.parse_args()
    run_step1(test_n=args.test, resume=args.resume)
