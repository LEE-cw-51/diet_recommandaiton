"""
Step 0 (pipeline/06): food_master cuisine_type 식문화 분류 (Gemini 3.1 Flash-Lite)

흐름:
  food_master WHERE price IS NOT NULL AND cuisine_type IS NULL
    -> [Gemini 3.1 Flash-Lite] product_name + category_type -> 식문화 분류
    -> food_master cuisine_type UPDATE

식문화 분류 기준:
  한식   : 한국 전통 음식 (비빔밥, 김치찌개, 삼겹살, 김밥 등)
  일식   : 일본 음식 (초밥, 라멘, 우동, 돈부리, 가라아게 등)
  중식   : 중국 음식 (짜장면, 짬뽕, 마라탕, 탕수육 등)
  양식   : 서양 음식 (버거, 피자, 파스타, 스테이크, 샌드위치 등)
  분식   : 한국 분식/간식 (떡볶이, 순대, 튀김, 핫도그, 토스트 등)
  카페   : 카페/디저트 (커피, 케이크, 마카롱, 음료, 빵 등)
  기타   : 위 분류에 해당하지 않는 경우 (건강식품, 분류 불가 등)

실행:
  python pipeline/06_cuisine_classify/step0_classify_cuisine.py --test 5
  python pipeline/06_cuisine_classify/step0_classify_cuisine.py
  python pipeline/06_cuisine_classify/step0_classify_cuisine.py --resume
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Windows cp949 터미널 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from google import genai
from google.genai import types as genai_types
from tqdm import tqdm

from db.client import get_client

# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

CHECKPOINT_FILE = Path(".checkpoint/cuisine_classify_done.json")
TABLE = "food_master"
BATCH_SIZE = 100

VALID_CUISINES = {"한식", "일식", "중식", "양식", "분식", "카페", "기타"}

SYSTEM_PROMPT = """한국 식품 및 외식 문화 전문가입니다.
주어진 메뉴 목록의 각 항목에 대해 식문화(cuisine_type)를 분류해주세요.

분류 기준:
- 한식 : 한국 전통 음식. 예) 비빔밥, 된장찌개, 삼겹살, 김밥, 갈비, 순두부찌개, 냉면
- 일식 : 일본 음식. 예) 초밥, 라멘, 우동, 돈부리, 가라아게, 돈카츠, 야키토리
- 중식 : 중국 음식. 예) 짜장면, 짬뽕, 마라탕, 탕수육, 훠궈, 딤섬, 볶음밥(중화)
- 양식 : 서양 음식. 예) 버거, 피자, 파스타, 스테이크, 샌드위치, 핫도그, 타코
- 분식 : 한국 분식/길거리 간식. 예) 떡볶이, 순대, 튀김, 어묵, 핫도그, 토스트, 붕어빵
- 카페 : 카페/베이커리/디저트. 예) 커피, 케이크, 마카롱, 크루아상, 와플, 빙수, 음료
- 기타 : 위 분류에 해당하지 않는 경우. 예) 건강기능식품, 단백질바, 분류 불가

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 금지):
{"results": [{"id": <id>, "cuisine_type": "<분류>"}, ...]}"""

# ──────────────────────────────────────────────────────────────
# Gemini 클라이언트
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# 모델 우선순위: 3.1이 503이면 2.5, 그래도 안되면 2.0으로 폴백
_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
]


# ──────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
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
# 배치 분류
# ──────────────────────────────────────────────────────────────

def classify_batch(batch: list[dict]) -> dict[int, str]:
    """배치(최대 100개)를 Gemini로 분류. {id: cuisine_type} 반환.

    모델 폴백: gemini-3.1-flash-lite → 2.5-flash-lite → 2.0-flash-lite
    """
    items_text = "\n".join(
        f"- id={row['id']}, 이름=\"{row['product_name']}\", 카테고리={row.get('category_type', 'UNKNOWN')}"
        for row in batch
    )
    user_msg = f"다음 {len(batch)}개 메뉴를 식문화별로 분류해주세요:\n\n{items_text}"

    for model_name in _MODELS:
        for attempt in range(2):
            try:
                response = _gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        genai_types.Content(role="user", parts=[genai_types.Part(text=SYSTEM_PROMPT)]),
                        genai_types.Content(role="user", parts=[genai_types.Part(text=user_msg)]),
                    ],
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                raw = response.text.strip()
                parsed = json.loads(raw)
                results = parsed.get("results", [])

                out: dict[int, str] = {}
                for item in results:
                    item_id = int(item.get("id", -1))
                    cuisine = str(item.get("cuisine_type", "기타")).strip()
                    if cuisine not in VALID_CUISINES:
                        cuisine = "기타"
                    out[item_id] = cuisine
                return out

            except Exception as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    # 모델 과부하 → 다음 모델로 폴백
                    print(f"  [FALLBACK] {model_name} 과부하 → 다음 모델 시도")
                    break
                if attempt == 0:
                    print(f"  [RETRY] {model_name} attempt {attempt+1}: {err_str[:80]}")
                    time.sleep(2)
                else:
                    print(f"  [ERROR] {model_name} 실패: {err_str[:80]}")

    print(f"  [ERROR] 모든 모델 실패 — 기타로 처리")
    return {row["id"]: "기타" for row in batch}


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cuisine type classification via Gemini")
    parser.add_argument("--test", type=int, default=0, help="테스트 모드: N개만 처리")
    parser.add_argument("--resume", action="store_true", help="체크포인트에서 재개")
    args = parser.parse_args()

    supabase = get_client()

    # 처리 대상 조회 (price IS NOT NULL, cuisine_type IS NULL)
    print("Supabase에서 데이터 조회 중...")
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            supabase.table(TABLE)
            .select("id,product_name,category_type")
            .not_.is_("price", "null")
            .is_("cuisine_type", "null")
            .range(offset, offset + 999)
            .execute()
        )
        chunk = resp.data or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000

    print(f"분류 대상: {len(rows)}개 (유가격 + cuisine_type NULL)")

    # 체크포인트 적용
    done_ids: set[str] = set()
    if args.resume:
        done_ids = load_checkpoint()
        rows = [r for r in rows if str(r["id"]) not in done_ids]
        print(f"  체크포인트: {len(done_ids)}개 완료, 잔여 {len(rows)}개")

    # 테스트 모드
    if args.test > 0:
        rows = rows[:args.test]
        print(f"  테스트 모드: {len(rows)}개만 처리")

    if not rows:
        print("처리할 데이터 없음.")
        return

    # 배치 처리
    total = len(rows)
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    print(f"\n총 {total}개 → {len(batches)}개 배치 (배치당 {BATCH_SIZE}개)")

    success_count = 0
    with tqdm(total=total, desc="Cuisine 분류") as pbar:
        for batch_idx, batch in enumerate(batches):
            results = classify_batch(batch)

            # Supabase UPDATE
            for row in batch:
                row_id = row["id"]
                cuisine = results.get(row_id, "기타")
                try:
                    supabase.table(TABLE).update({"cuisine_type": cuisine}).eq("id", row_id).execute()
                    done_ids.add(str(row_id))
                    success_count += 1
                except Exception as e:
                    print(f"  [UPDATE ERROR] id={row_id}: {e}")

            # 체크포인트 저장
            save_checkpoint(done_ids)
            pbar.update(len(batch))

            # 배치 간 짧은 대기 (Rate Limit 방지)
            if batch_idx < len(batches) - 1:
                time.sleep(0.5)

    print(f"\n완료: {success_count}/{total}개 분류")

    # 결과 확인
    print("\n분류 결과 집계:")
    verify = supabase.table(TABLE).select("cuisine_type").not_.is_("price", "null").execute()
    from collections import Counter
    counts = Counter(r["cuisine_type"] for r in (verify.data or []))
    for cuisine, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cuisine or 'NULL':8s}: {cnt:4d}개")


if __name__ == "__main__":
    main()
