"""
G2 (R-NSGA-II, KG 없음) 7일 Loop B 시뮬레이션 → G3와 비교 표 출력
전체 food pool 사용 (실제 실험과 동일)
"""
import json, sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiment.core.loader import FoodDataLoader
from experiment.core.daily_exp3_problem import DailyExp3Problem
from experiment.core.nutrition import NutritionProfile
from experiment.core.kg_manager import KGManager, make_menu_id
from experiment.algorithms.builders import make_rnsga2
from experiment.models.variants import REF_G2, N_MEALS, SEED_START, TEST_USER
from experiment.simulation.simulate_kg import _run_one_day
from pymoo.optimize import minimize
from pymoo.termination import get_termination
from db.client import get_client

CUISINE   = "한식"
BASE_DATE = datetime(2026, 5, 7, 12, 0, 0)
N_DAYS    = 7
POP_SIZE  = 200
N_GEN     = 200
CAL_STAR  = 2000.0
PRICE_STAR = 8000.0

# ── 1. food pool 로드 ─────────────────────────────────────────────────────────
print("\n[STEP 1] food pool 로드")
loader = FoodDataLoader.from_supabase()
cats   = loader.get_category_lists()
mains      = cats["MAIN"]
sides_soup = cats["SIDE_SOUP"]
drinks     = cats["DRINK"]
snacks     = cats["SNACK"]
all_foods  = loader.menu_items
print(f"  MAIN:{len(mains)} SIDE_SOUP:{len(sides_soup)} DRINK:{len(drinks)} SNACK:{len(snacks)}")

# ── 2. G2 7일 시뮬레이션 ──────────────────────────────────────────────────────
print("\n[STEP 2] G2 R-NSGA-II 7일 Loop B (KG 없음, 전체 pool)")
profile  = NutritionProfile.who2025()
kg_dummy = KGManager()
for item in all_foods:
    mid = make_menu_id(item)
    if mid:
        kg_dummy.add_menu(mid,
                          category=item.get("category_type", item.get("category", "UNKNOWN")),
                          cuisine=item.get("cuisine_type"))

def main_of(combo):
    for item in combo:
        if item.get("category") == "MAIN":
            name    = str(item.get("product_name") or "")
            cuisine = item.get("cuisine_type") or "—"
            return f"{name} [{cuisine}]"
    item = combo[0]
    return f"{item.get('product_name','')} [{item.get('cuisine_type') or '—'}]"

g2_days = []
for day in range(1, N_DAYS + 1):
    today = BASE_DATE + timedelta(days=day - 1)
    seed  = SEED_START + day

    problem = DailyExp3Problem(
        mains=mains, sides_soup=sides_soup,
        drinks=drinks, snacks=snacks,
        n_meals=N_MEALS, include_snack=False,
        cal_star=CAL_STAR, price_per_meal_star=PRICE_STAR,
        profile=profile,
        kg_manager=kg_dummy,
        user_id=TEST_USER,
        lambda_decay=0.5,
        sim_now=today,
        use_f4=False,  # G2: 3목적 (f1/f2/f3)
    )

    algo = make_rnsga2(pop_size=POP_SIZE, ref_points=REF_G2)
    np.random.seed(seed)
    res  = minimize(problem, algo, get_termination("n_gen", N_GEN),
                    seed=seed, verbose=False)

    if res is None or res.F is None or len(res.F) == 0:
        print(f"  Day {day}: 해 없음")
        g2_days.append({"day": day, "date": today.strftime("%Y-%m-%d"),
                        "meals": {"아침": "—", "점심": "—", "저녁": "—"}})
        continue

    best_idx = np.argmin(res.F[:, 0])
    combo    = problem.decode(res.X[best_idx])
    f1, f2, f3 = res.F[best_idx, :3]

    meals = {
        "아침": main_of(combo[0:4]),
        "점심": main_of(combo[4:8]),
        "저녁": main_of(combo[8:12]),
    }
    print(f"  Day {day} ({today.strftime('%m-%d')}): f1={f1:.4f} f2={f2:.4f} f3={f3:.4f} | "
          f"아침={meals['아침'][:20]}")
    g2_days.append({"day": day, "date": today.strftime("%Y-%m-%d"), "meals": meals})

# ── 3. G3 데이터 로드 (기존 JSON + Supabase) ──────────────────────────────────
print("\n[STEP 3] G3 데이터 로드")
seq    = json.loads((ROOT / "experiment/results/step2_cuisine/한식/kg_eaten_sequence.json")
                    .read_text(encoding="utf-8"))
all_ids = list({mid for day in seq["days"] for mid in day["menu_ids"]})
res_db  = get_client().table("food_master") \
    .select("id,product_name,category_type,cuisine_type") \
    .in_("id", [int(i) for i in all_ids]).execute()
id2row  = {str(r["id"]): r for r in res_db.data}

def main_of_ids(id_chunk):
    for mid in id_chunk:
        r = id2row.get(str(mid))
        if r and r.get("category_type") == "MAIN":
            return f"{r['product_name']} [{r.get('cuisine_type') or '—'}]"
    r = id2row.get(str(id_chunk[0]))
    return f"{r['product_name']} [{r.get('cuisine_type') or '—'}]" if r else f"ID:{id_chunk[0]}"

g3_days = []
for day_info in seq["days"][:N_DAYS]:
    ids = day_info["menu_ids"]
    g3_days.append({
        "day":   day_info["day"],
        "date":  day_info["date"],
        "meals": {
            "아침": main_of_ids(ids[0:4]),
            "점심": main_of_ids(ids[4:8]),
            "저녁": main_of_ids(ids[8:12]),
        }
    })

# ── 4. 표 출력 ────────────────────────────────────────────────────────────────
f4df  = pd.read_csv(ROOT / "experiment/results/step2_cuisine/한식/daily_f4_trend.csv")
dupdf = pd.read_csv(ROOT / "experiment/results/step2_cuisine/한식/daily_duplication.csv")
f4    = dict(zip(f4df["day"],  f4df["f4"]))
dup   = dict(zip(dupdf["day"], dupdf["duplication_rate"]))

print("\n\n| 날짜 | 끼니 | G2 (R-NSGA-II, KG 없음) | G3 (R-NSGA-II+KG, 한식 선호) |")
print("|------|------|------------------------|-------------------------------|")
for i, (d2, d3) in enumerate(zip(g2_days, g3_days)):
    day = i + 1
    dup_str = f" ⚠️ 중복 {dup[day]*100:.1f}%" if dup.get(day, 0) > 0 else ""
    for li, label in enumerate(["아침", "점심", "저녁"]):
        day_cell = f"**Day {day}** f4={f4[day]:.4f}{dup_str}" if li == 0 else ""
        g2m = d2["meals"].get(label, "—")
        g3m = d3["meals"].get(label, "—")
        print(f"| {day_cell} | {label} | {g2m} | {g3m} |")

# ── 5. JSON 저장 ──────────────────────────────────────────────────────────────
out = ROOT / "paper_outputs/table_6_2_g2_g3.json"
out.parent.mkdir(exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump({"G2": g2_days, "G3": g3_days}, f, ensure_ascii=False, indent=2)
print(f"\n💾 저장 → {out}")
