"""
Step 2: food_master category_type 분류 (Gemini 2.5 Flash-Lite)

흐름:
  food_master WHERE category_type IS NULL
    → [Gemini 2.5 Flash-Lite] product_name + 영양성분 → MAIN/SOUP/SIDE/DRINK/SNACK 분류
    → food_master category_type + classified_at UPDATE

분류 기준 (한국 식품공전 + 식약처 + HACCP):
  MAIN  : 탄수화물 주공급원 (밥, 빵, 면, 떡, 도시락)
  SOUP  : 국물류 (국, 찌개, 탕, 라면)
  SIDE  : 부식 (반찬, 샐러드, 김치, 나물, 구이)
  DRINK : 액상 음료 (물, 주스, 커피, 차)
  SNACK : 간식 (과자, 초콜릿, 견과류, 건강식품)

실행:
  python pipeline/05_augment/step2_food_classifier.py --test 5   # 5개 테스트
  python pipeline/05_augment/step2_food_classifier.py             # 전체 실행
  python pipeline/05_augment/step2_food_classifier.py --resume    # 중단 재개

전환 이력:
  v1: Groq LLaMA 3.1 8B (TPM 6K 한도 초과로 중단)
  v2: Gemini 2.5 Flash-Lite (유료 계정, 높은 TPM 한도)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Windows cp949 터미널에서 유니코드 출력 허용
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

CHECKPOINT_FILE = Path(".checkpoint/step2_done.json")
TABLE = "food_master"
VALID_CATEGORIES = {"MAIN", "SOUP", "SIDE", "DRINK", "SNACK"}

SYSTEM_PROMPT = """한국 식품공전(NFIS), 식품의약품안전처, HACCP 분류 기준에 따라 식품을 분류하는 전문가입니다.

다음 5가지 카테고리 중 하나로 분류하세요:

- MAIN  : 탄수화물 주공급원. 한 끼 식사의 주식이 되는 식품.
          예) 밥, 볶음밥, 김밥, 도시락, 빵, 샌드위치, 국수, 라면(건조), 떡, 파스타
- SOUP  : 국물이 있는 탕/국/찌개/죽류. 나트륨이 높고 고형물과 국물이 혼합된 식품.
          예) 된장찌개, 김치찌개, 부대찌개, 미역국, 설렁탕, 삼계탕, 즉석국, 컵라면(조리 후)
- SIDE  : 밥과 함께 먹는 부식. 국물이 없는 반찬류.
          예) 김치, 나물, 조림, 볶음, 구이, 샐러드, 두부, 계란프라이, 햄, 소시지
- DRINK : 액상 음료. 고형물이 거의 없는 마시는 식품.
          예) 생수, 탄산음료, 주스, 커피, 차, 두유, 우유, 스무디, 스포츠음료
- SNACK : 간식/디저트. 식사 대용이 아닌 간식류.
          예) 과자, 칩, 초콜릿, 사탕, 아이스크림, 케이크, 견과류, 단백질바, 건강기능식품

영양성분도 판단 기준으로 활용:
- MAIN: 탄수화물 높음, 단백질 적당
- SOUP: 나트륨 매우 높음, 단백질 적당, 탄수화물 낮음
- SIDE: 단백질 또는 채소 위주, 나트륨 중간
- DRINK: 칼로리 매우 낮음, 당류 다양, 나트륨 거의 없음
- SNACK: 당류 또는 지방 높음, 칼로리 중간~높음

반드시 JSON 형식으로만 응답 (다른 텍스트 금지):
{"category_type": "MAIN 또는 SOUP 또는 SIDE 또는 DRINK 또는 SNACK"}"""

# ──────────────────────────────────────────────────────────────
# Gemini 클라이언트
# ──────────────────────────────────────────────────────────────

import os

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


# ──────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """처리 완료된 id 집합 반환 (str 형식)."""
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
# Gemini 분류
# ──────────────────────────────────────────────────────────────

def _fmt(v, suffix: str = "") -> str:
    """None 또는 0을 '-'로, 그 외는 값+단위로."""
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    return f"{f:.1f}{suffix}"


def classify_one(row: dict) -> str:
    """Gemini 2.5 Flash-Lite로 1개 행 분류. 실패 시 'MAIN' fallback."""
    user_msg = (
        f"제품명: {row.get('product_name', '')}\n"
        f"브랜드: {row.get('brand_name') or '불명'}\n"
        f"식품군: {row.get('food_group') or '불명'}\n"
        f"칼로리: {_fmt(row.get('calories'), 'kcal')} | "
        f"탄수화물: {_fmt(row.get('carbs'), 'g')} | "
        f"당류: {_fmt(row.get('sugar'), 'g')} | "
        f"단백질: {_fmt(row.get('protein'), 'g')} | "
        f"지방: {_fmt(row.get('fat'), 'g')} | "
        f"나트륨: {_fmt(row.get('sodium'), 'mg')}"
    )
    prompt = SYSTEM_PROMPT + "\n\n" + user_msg

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
            result = json.loads(response.text)
            cat = result.get("category_type", "").upper()
            return cat if cat in VALID_CATEGORIES else "MAIN"

        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                m = re.search(r"retry[^\d]*(\d+)", str(e), re.IGNORECASE)
                delay = int(m.group(1)) + 5 if m else 35
                print(f"\n  [Gemini] Rate limit, {delay}s 대기 후 재시도 ({attempt + 1}/{MAX_RETRIES - 1})...")
                time.sleep(delay)
            else:
                print(f"\n  [Gemini] 오류: {e}")
                return "MAIN"

    return "MAIN"


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

def run_step2(test_n: int | None = None, resume: bool = False) -> None:
    sb = get_client()
    done_ids = load_checkpoint() if resume else set()
    if done_ids:
        print(f"체크포인트 로드: {len(done_ids)}개 이미 처리됨")

    # category_type IS NULL 전체 로드 (pagination)
    SELECT_COLS = "id,product_name,brand_name,food_group,calories,carbs,sugar,protein,fat,sodium"
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table(TABLE)
            .select(SELECT_COLS)
            .is_("category_type", "null")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        rows.extend(batch)
        offset += 1000

    print(f"분류 대상 (category_type=NULL): {len(rows)}개")

    if test_n:
        rows = rows[:test_n]

    success = 0
    fail = 0
    now_str = datetime.now(timezone.utc).isoformat()

    for row in tqdm(rows, desc="Step 2: category_type 분류"):
        row_id = str(row["id"])
        if row_id in done_ids:
            continue

        try:
            cat = classify_one(row)

            sb.table(TABLE).update({
                "category_type": cat,
                "classified_at": now_str,
            }).eq("id", row["id"]).execute()

            done_ids.add(row_id)
            save_checkpoint(done_ids)
            success += 1

        except Exception as e:
            print(f"\n  FAIL id={row['id']} [{row.get('product_name')}]: {e}")
            fail += 1

        time.sleep(1)  # Gemini 유료 계정 rate limit 안전 마진

    print(f"\n완료 — 성공: {success}, 실패: {fail}")
    print(f"체크포인트: {CHECKPOINT_FILE} ({len(done_ids)}개)")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 2: food_master category_type 분류 (Gemini 2.5 Flash-Lite)"
    )
    parser.add_argument("--test", type=int, metavar="N", help="N개만 처리 (테스트 모드)")
    parser.add_argument("--resume", action="store_true", help="체크포인트 기반 재개")
    args = parser.parse_args()
    run_step2(test_n=args.test, resume=args.resume)
