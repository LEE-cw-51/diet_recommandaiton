"""
G1 vs G2 Wilcoxon rank-sum test
— G1/G2 30회 독립 실행 후 공유 ref front 기준 HV/GD+/IGD+ 계산 및 검정
— 결과를 storyboard_sec4_5_6.md 표 6-1에 반영할 p-value 산출

실행: python -X utf8 run_g1g2_wilcoxon.py
소요: 약 7~8분
"""
import sys, time
from pathlib import Path

import numpy as np
from scipy.stats import ranksums

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiment.core.loader import FoodDataLoader
from experiment.core.metrics import compute_indicators, compute_reference_pf
from experiment.simulation.engine import build_kg, run_once
from experiment.algorithms.builders import make_nsga2, make_rnsga2
from experiment.models.variants import REF_G2, N_MEALS, SEED_START, TEST_USER
from experiment.core.daily_exp3_problem import DailyExp3Problem
from experiment.core.nutrition import NutritionProfile

N_RUNS   = 30
POP_SIZE = 200
N_GEN    = 200
CAL_STAR   = 2000.0
PRICE_STAR = 8000.0

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
print("📦 food_master 로딩...")
loader = FoodDataLoader.from_supabase()
cats   = loader.get_category_lists()
mains, sides_soup, drinks, snacks = (
    cats["MAIN"], cats["SIDE_SOUP"], cats["DRINK"], cats["SNACK"]
)
all_foods = loader.menu_items
print(f"  MAIN:{len(mains)} SIDE_SOUP:{len(sides_soup)} DRINK:{len(drinks)} SNACK:{len(snacks)}")

kg_base = build_kg(all_foods)
profile = NutritionProfile.who2025()

problem = DailyExp3Problem(
    mains=mains, sides_soup=sides_soup,
    drinks=drinks, snacks=snacks,
    n_meals=N_MEALS, include_snack=False,
    cal_star=CAL_STAR, price_per_meal_star=PRICE_STAR,
    profile=profile,
    kg_manager=kg_base,
    user_id=TEST_USER,
    lambda_decay=0.5,
    use_f4=False,  # G1/G2: 3목적
)

# ── G1·G2 30회 실행 ───────────────────────────────────────────────────────────
print(f"\n🚀 G1/G2 각 {N_RUNS}회 독립 실행 (pop={POP_SIZE}, gen={N_GEN})")
t_start = time.perf_counter()

g1_F_list, g2_F_list = [], []

for run_idx in range(N_RUNS):
    seed = SEED_START + run_idx
    print(f"  Run {run_idx+1:2d}/{N_RUNS}  seed={seed}", end="  ", flush=True)

    F1, t1, _ = run_once(problem, make_nsga2(POP_SIZE), N_GEN, seed)
    F2, t2, _ = run_once(problem, make_rnsga2(POP_SIZE, REF_G2), N_GEN, seed)

    g1_F_list.append(F1)
    g2_F_list.append(F2)
    print(f"G1:{len(F1)}해 {t1:.1f}s  G2:{len(F2)}해 {t2:.1f}s")

elapsed_total = time.perf_counter() - t_start
print(f"\n  총 소요: {elapsed_total:.0f}s ({elapsed_total/60:.1f}분)")

# ── 공유 ref front 계산 ───────────────────────────────────────────────────────
print("\n📐 공유 Reference Front 계산 (G1+G2 합병 비지배해)")
all_F = np.vstack([F for F in g1_F_list + g2_F_list if len(F) > 0])
ref_front = compute_reference_pf(all_F)
nadir     = all_F.max(axis=0) * 1.1
print(f"  ref_front 크기: {len(ref_front)}해  nadir: {np.round(nadir, 3)}")

# ── 지표 계산 ─────────────────────────────────────────────────────────────────
def calc_metrics(F_list, ref_front, nadir):
    hv, gdp, igdp = [], [], []
    for F in F_list:
        if len(F) == 0:
            continue
        inds = compute_indicators(F, ref_front, nadir)
        hv.append(inds["HV"])
        gdp.append(inds["GD+"])
        igdp.append(inds["IGD+"])
    return np.array(hv), np.array(gdp), np.array(igdp)

g1_hv, g1_gdp, g1_igdp = calc_metrics(g1_F_list, ref_front, nadir)
g2_hv, g2_gdp, g2_igdp = calc_metrics(g2_F_list, ref_front, nadir)

# ── Wilcoxon 검정 ─────────────────────────────────────────────────────────────
def p_star(p):
    if p < 0.001: return f"{p:.4f} ***"
    if p < 0.01:  return f"{p:.4f} **"
    if p < 0.05:  return f"{p:.4f} *"
    return f"{p:.4f} (n.s.)"

_, p_hv   = ranksums(g1_hv,   g2_hv)
_, p_gdp  = ranksums(g1_gdp,  g2_gdp)
_, p_igdp = ranksums(g1_igdp, g2_igdp)

# ── 결과 출력 ─────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("📊 G1 vs G2 결과 (공유 ref front, 30회)")
print("="*60)
print(f"{'지표':6} | {'G1 mean±std':20} | {'G2 mean±std':20} | p-value")
print("-"*60)
for metric, g1v, g2v, p in [
    ("HV",   g1_hv,   g2_hv,   p_hv),
    ("GD+",  g1_gdp,  g2_gdp,  p_gdp),
    ("IGD+", g1_igdp, g2_igdp, p_igdp),
]:
    g1s = f"{g1v.mean():.4f}±{g1v.std():.4f}"
    g2s = f"{g2v.mean():.4f}±{g2v.std():.4f}"
    print(f"{metric:6} | {g1s:20} | {g2s:20} | {p_star(p)}")

print("\n📋 스토리보드 표 6-1 반영용:")
print(f"  G1 vs G2 HV   p = {p_star(p_hv)}")
print(f"  G1 vs G2 GD+  p = {p_star(p_gdp)}")
print(f"  G1 vs G2 IGD+ p = {p_star(p_igdp)}")

# ── JSON 저장 ─────────────────────────────────────────────────────────────────
import json
out = ROOT / "paper_outputs/g1g2_wilcoxon.json"
result = {
    "n_runs": N_RUNS,
    "G1": {"HV": round(float(g1_hv.mean()),4), "HV_std": round(float(g1_hv.std()),4),
           "GDp": round(float(g1_gdp.mean()),4), "IGDp": round(float(g1_igdp.mean()),4)},
    "G2": {"HV": round(float(g2_hv.mean()),4), "HV_std": round(float(g2_hv.std()),4),
           "GDp": round(float(g2_gdp.mean()),4), "IGDp": round(float(g2_igdp.mean()),4)},
    "wilcoxon_G1_vs_G2": {
        "HV_p":   round(float(p_hv),   4),
        "GDp_p":  round(float(p_gdp),  4),
        "IGDp_p": round(float(p_igdp), 4),
    }
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\n💾 저장 → {out}")
