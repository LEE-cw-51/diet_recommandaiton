"""
Step 0b: final_nutrition_db.csv → food_master INSERT

흐름:
  data/processed/final_nutrition_db.csv (프랜차이즈 메뉴)
    → [Gemini 2.5 Flash] allergens_scraped 원문 → 22종 allergens JSONB
    → food_master UPSERT (영양성분 + allergens, price=NULL)

price 는 CSV 값 신뢰도 낮음(크롤링+랜덤 혼재) → NULL 저장.
Step 1b 재실행 시 Naver Shopping API 로 자동 조회.

실행:
  python pipeline/05_augment/step0b_csv_import.py --test 5   # 5개 테스트
  python pipeline/05_augment/step0b_csv_import.py             # 전체 실행
  python pipeline/05_augment/step0b_csv_import.py --resume    # 중단 재개
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

from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path 에 추가 (CLAUDE.md §10)
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from google import genai
from google.genai import types as genai_types
from tqdm import tqdm

from db.client import get_client

# ──────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────

# 워크트리 환경에서는 data/ 가 없으므로 메인 레포 경로로 폴백
# 워크트리: .../diet_recommendation/.claude/worktrees/<name>
# 메인 레포: .../diet_recommendation
_csv_candidates = [
    _ROOT / "data" / "processed" / "final_nutrition_db.csv",
    _ROOT.parent.parent.parent / "data" / "processed" / "final_nutrition_db.csv",
]
CSV_PATH = next((p for p in _csv_candidates if p.exists()), _csv_candidates[0])

CHECKPOINT_FILE = Path(".checkpoint/step0b_done.json")
TABLE = "food_master"

ALLERGEN_22 = [
    "난류", "우유", "메밀", "땅콩", "대두", "밀", "고등어", "게",
    "새우", "돼지고기", "복숭아", "토마토", "아황산류", "호두",
    "닭고기", "쇠고기", "오징어", "조개류", "잣", "아몬드", "캐슈넛", "키위",
]

# ──────────────────────────────────────────────────────────────
# Gemini 설정 (google-genai SDK, step1 과 동일 패턴)
# ──────────────────────────────────────────────────────────────

_gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


# ──────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """처리 완료된 키 집합 반환. 키 형식: "menu_name|store_name"."""
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
# Gemini 알레르기 파싱
# ──────────────────────────────────────────────────────────────

def _allergen_fields_str() -> str:
    return "\n".join(f'    "{a}": true 또는 false' for a in ALLERGEN_22)


def parse_allergens_with_gemini(product_name: str, raw_text: str) -> dict:
    """원문 텍스트 → 22종 알레르기 JSONB. 실패 시 모두 False 반환."""
    prompt = f"""[제품명]
{product_name}

[원재료/알레르기 원문 텍스트]
{raw_text[:2000]}

위 텍스트를 분석하여 아래 22종 알레르기 해당 여부를 JSON 으로만 출력하세요.
원문에서 해당 성분이 확인되면 true, 불확실하거나 언급 없으면 false.

{{
  "allergens": {{
{_allergen_fields_str()}
  }}
}}"""

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
    allergens = parsed.get("allergens", {})
    for a in ALLERGEN_22:
        allergens.setdefault(a, False)   # 누락 키 → False 보장
    return allergens


def _empty_allergens() -> dict:
    return {a: False for a in ALLERGEN_22}


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

def run_step0b(test_n: int | None = None, resume: bool = False) -> None:
    sb = get_client()
    done_keys = load_checkpoint() if resume else set()
    if done_keys:
        print(f"체크포인트 로드: {len(done_keys)}개 이미 처리됨")

    # CSV 로드 + 중복 제거 (product_name + brand_name 기준)
    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    df = df.drop_duplicates(subset=["menu_name", "store_name"])
    rows = df.to_dict("records")

    if test_n:
        rows = rows[:test_n]

    print(f"처리 대상: {len(rows)}개  →  {TABLE}")
    success = fail = skip = 0

    for row in tqdm(rows, desc="Step 0b: CSV import"):
        key = f"{row['menu_name']}|{row['store_name']}"
        if key in done_keys:
            skip += 1
            continue

        try:
            raw_text = str(row.get("allergens_scraped", "") or "").strip()
            if raw_text:
                allergens = parse_allergens_with_gemini(str(row["menu_name"]), raw_text)
            else:
                allergens = _empty_allergens()

            record = {
                "product_name":   str(row["menu_name"]),
                "brand_name":     str(row["store_name"]) if row.get("store_name") else None,
                "food_group":     None,
                "price":          None,          # CSV 가격 신뢰 불가 → Step 1b 에서 Naver 로 채움
                "calories":       _safe_float(row.get("calories")),
                "protein":        _safe_float(row.get("protein")),
                "fat":            _safe_float(row.get("fat")),
                "carbs":          _safe_float(row.get("carbs")),
                "sugar":          _safe_float(row.get("sugars")),
                "sodium":         _safe_float(row.get("sodium")),
                "allergens":      allergens,
                "raw_label_text": raw_text,
                "data_source":    "final_nutrition_db",
                "is_verified":    False,
                "augmented_at":   "now()",
            }

            sb.table(TABLE).upsert(record, on_conflict="product_name,brand_name").execute()
            done_keys.add(key)
            save_checkpoint(done_keys)
            success += 1

        except Exception as e:
            print(f"\n  FAIL [{row['menu_name']}]: {e}")
            fail += 1

        time.sleep(3)   # Gemini Flash-Lite RPM 대응

    print(f"\n완료 — 성공: {success}, 실패: {fail}, 스킵: {skip}")
    print(f"체크포인트: {CHECKPOINT_FILE} ({len(done_keys)}개)")


def _safe_float(v) -> float | None:
    """pandas NaN / None → None, 그 외 float 변환."""
    if v is None:
        return None
    try:
        f = float(v)
        import math
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 0b: final_nutrition_db.csv → food_master INSERT"
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
    run_step0b(test_n=args.test, resume=args.resume)
