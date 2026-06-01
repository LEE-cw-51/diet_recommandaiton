"""
논문 표 6-2: G1 vs G3 한식 선호 유저 7일 추천 식단 비교
  - G3: kg_eaten_sequence.json의 menu_id → Supabase 조회 (name + cuisine_type)
  - G1: NSGA-II 7일 시뮬레이션 (KG 없음, 매일 독립 실행)
출력: paper_outputs/table_6_2_menus.json + 콘솔 마크다운 표
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# ── 프로젝트 루트 경로 설정 ───────────────────────────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.client import get_client
from experiment.simulation.engine import build_kg
from experiment.models.variants import N_MEALS, SEED_START, TEST_USER
from experiment.core.loader import FoodDataLoader  # FoodDataLoader.from_supabase()

# ── 상수 ──────────────────────────────────────────────────────────────────────
CUISINE     = "한식"
BASE_DATE   = datetime(2026, 5, 7, 12, 0, 0)
N_DAYS      = 7
POP_SIZE    = 200
N_GEN       = 200
CAL_STAR    = 2000.0
PRICE_STAR  = 8000.0
CUISINE_WEIGHT = 1.3

SEQ_PATH = ROOT / "experiment/results/step2_cuisine/한식/kg_eaten_sequence.json"
OUT_PATH = ROOT / "paper_outputs/table_6_2_menus.json"
OUT_PATH.parent.mkdir(exist_ok=True)

client = get_client()

# ══════════════════════════════════════════════════════════════════════════════
# 1. G3 — kg_eaten_sequence.json → Supabase 조회
# ══════════════════════════════════════════════════════════════════════════════
print("\n[G3] kg_eaten_sequence.json 로드 + Supabase 조회")

seq = json.loads(SEQ_PATH.read_text(encoding="utf-8"))
all_ids = list({mid for day in seq["days"] for mid in day["menu_ids"]})

res = client.table("food_master") \
    .select("id,product_name,category_type,cuisine_type") \
    .in_("id", [int(i) for i in all_ids]) \
    .execute()

id2row = {str(r["id"]): r for r in res.data}
print(f"  조회 완료: {len(id2row)}개")

def main_of_ids(id_chunk: list) -> str:
    """4개 ID 중 MAIN 카테고리 첫 번째를 '메뉴명 [cuisine]' 형태로 반환."""
    for mid in id_chunk:
        r = id2row.get(str(mid))
        if r and r.get("category_type") in ("MAIN",):
            return f"{r['product_name']} [{r.get('cuisine_type') or '—'}]"
    # MAIN 없으면 첫 번째
    r = id2row.get(str(id_chunk[0]))
    if r:
        return f"{r['product_name']} [{r.get('cuisine_type') or '—'}]"
    return f"ID:{id_chunk[0]}"

g3_days = []
for day_info in seq["days"][:N_DAYS]:
    ids = day_info["menu_ids"]   # 12개
    meals = {
        "아침": main_of_ids(ids[0:4]),
        "점심": main_of_ids(ids[4:8]),
        "저녁": main_of_ids(ids[8:12]),
    }
    g3_days.append({"day": day_info["day"], "date": day_info["date"], "meals": meals})

# ══════════════════════════════════════════════════════════════════════════════
# 2. G1 — NSGA-II 7일 시뮬레이션 (KG 없음, 매일 독립)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[G1] NSGA-II 7일 시뮬레이션 (KG 없음)")

from experiment.algorithms.builders import make_nsga2
from experiment.core.daily_exp3_problem import DailyExp3Problem
from experiment.core.nutrition import NutritionProfile
from experiment.core.kg_manager import KGManager, make_menu_id
from pymoo.optimize import minimize
from pymoo.termination import get_termination

loader    = FoodDataLoader.from_supabase()
cats      = loader.get_category_lists()
# G1은 식문화 필터 없음 — 전체 풀 사용 (실제 실험과 동일)
mains_kr      = cats["MAIN"]
sides_soup_kr = cats["SIDE_SOUP"]
drinks_kr     = cats["DRINK"]
snacks_kr     = cats["SNACK"]
all_foods     = loader.menu_items

print(f"  한식 풀: MAIN {len(mains_kr)}, SIDE_SOUP {len(sides_soup_kr)}, "
      f"DRINK {len(drinks_kr)}, SNACK {len(snacks_kr)}")

profile = NutritionProfile.who2025()
# G1용 더미 KG (f4 계산 안 함 — KGManager만 넘기고 pref 초기화 없음)
kg_dummy = KGManager()
for item in all_foods:
    mid = make_menu_id(item)
    if mid:
        cat = item.get("category_type", item.get("category", "UNKNOWN"))
        kg_dummy.add_menu(mid, category=cat, cuisine=item.get("cuisine_type"))

g1_days = []
for day in range(1, N_DAYS + 1):
    today = BASE_DATE + timedelta(days=day - 1)
    seed  = SEED_START + day

    # G1은 f1/f2/f3 3목적 — kg_manager 넘기되 f4는 0으로 고정 (pref 미설정)
    problem = DailyExp3Problem(
        mains=mains_kr, sides_soup=sides_soup_kr,
        drinks=drinks_kr, snacks=snacks_kr,
        n_meals=N_MEALS, include_snack=False,
        cal_star=CAL_STAR, price_per_meal_star=PRICE_STAR,
        profile=profile,
        kg_manager=kg_dummy,
        user_id=TEST_USER,
        lambda_decay=0.5,
        sim_now=today,
    )

    algo = make_nsga2(pop_size=POP_SIZE)
    np.random.seed(seed)
    res  = minimize(problem, algo, get_termination("n_gen", N_GEN),
                    seed=seed, verbose=False)

    if res is None or res.F is None or len(res.F) == 0:
        print(f"  Day {day}: 해 없음")
        g1_days.append({"day": day, "date": today.strftime("%Y-%m-%d"), "meals": {}})
        continue

    # 파레토 전선 중 f1 최소 해 선택
    best_idx = np.argmin(res.F[:, 0])
    best_X   = res.X[best_idx]
    combo    = problem.decode(best_X)

    def main_of(chunk):
        """4개 아이템 중 MAIN 카테고리 첫 번째 반환, 없으면 첫 번째."""
        for item in chunk:
            if item.get("category") == "MAIN":
                name    = str(item.get("product_name") or "")
                cuisine = item.get("cuisine_type") or "—"
                return f"{name} [{cuisine}]"
        item = chunk[0]
        return f"{item.get('product_name','')} [{item.get('cuisine_type') or '—'}]"

    meals = {
        "아침": main_of(combo[0:4]),
        "점심": main_of(combo[4:8]),
        "저녁": main_of(combo[8:12]),
    }
    f1, f2, f3 = res.F[best_idx, :3]
    print(f"  Day {day} ({today.strftime('%m-%d')}): f1={f1:.4f} f2={f2:.4f} f3={f3:.4f} | "
          f"아침={meals['아침'][:20]}")
    g1_days.append({"day": day, "date": today.strftime("%Y-%m-%d"), "meals": meals})

# ══════════════════════════════════════════════════════════════════════════════
# 3. 출력
# ══════════════════════════════════════════════════════════════════════════════
print("\n\n[논문용 마크다운 표 — G1 vs G3 한식 선호 유저 7일 추천 식단 (MAIN 메뉴)]\n")
print("| 날짜 | 끼니 | G1 (NSGA-II, 선호 없음) | G3 (R-NSGA-II + KG, 한식 선호) |")
print("|------|------|------------------------|--------------------------------|")

import pandas as _pd
_f4df = _pd.read_csv(ROOT / "experiment/results/step2_cuisine/한식/daily_f4_trend.csv")
f4_by_day = dict(zip(_f4df["day"], _f4df["f4"]))

for day_idx in range(N_DAYS):
    d1  = g1_days[day_idx]
    d3  = g3_days[day_idx] if day_idx < len(g3_days) else {}
    f4  = f4_by_day.get(day_idx + 1, "")
    date = d1["date"]
    for li, label in enumerate(["아침", "점심", "저녁"]):
        g1m = d1["meals"].get(label, "—")
        g3m = d3.get("meals", {}).get(label, "—")
        day_cell = f"**Day {day_idx+1}** ({date})<br>f4={f4:.4f}" if li == 0 else ""
        print(f"| {day_cell} | {label} | {g1m} | {g3m} |")

# JSON 저장
output = {"G1": g1_days, "G3": g3_days}
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n💾 저장 → {OUT_PATH}")
