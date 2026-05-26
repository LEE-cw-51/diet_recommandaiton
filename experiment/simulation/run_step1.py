"""1단계 기술적 검증 시뮬레이션 — G1/G2/G3 알고리즘 비교 (계산 전담).

루프 A: NSGA-II(G1) vs R-NSGA-II 고정 KG(G2) vs R-NSGA-II 동적 ref_points(G3)
        30회 독립 실행 → HV, GD+, IGD+, 실행시간(avg_time_sec), Wilcoxon p-value
루프 B: G3 7일 시뮬레이션 (매일 KG record_eating 업데이트) → f4 추이, 메뉴 중복률

이 스크립트는 **그래프를 그리지 않는다.** 계산 후 CSV + artifacts.npz 만 저장한다.
시각화는 `python -X utf8 -m experiment.visualization.plot_step1` 로 별도 실행
(저장된 아티팩트만 읽으며 최적화를 재실행하지 않음).

공통 로직 출처:
  알고리즘 빌더   → experiment.algorithms.builders (make_nsga2 / make_rnsga2)
  모델 변형·상수  → experiment.models.variants (REF_G2 / REF_G3 / SEED_START / ...)
  실행 엔진       → experiment.simulation.engine (run_once / build_kg)
  아티팩트 저장   → experiment.simulation.artifacts

산출물: experiment/results/step1/
  metrics_comparison.csv  per_run_metrics.csv  daily_f4_trend.csv  daily_duplication.csv
  artifacts.npz           (시각화 재현용 raw 데이터)

사용법:
  python -X utf8 -m experiment.simulation.run_step1 --cal_star 2000 --price_star 8000
  python -X utf8 -m experiment.simulation.run_step1 --test
  python -X utf8 -m experiment.simulation.run_step1 --plot   # 계산 후 시각화까지
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiment.algorithms.builders import make_nsga2, make_rnsga2  # noqa: E402
from experiment.models.variants import (  # noqa: E402
    N_MEALS,
    REF_G2,
    REF_G3,
    SEED_START,
    TEST_USER,
)
from experiment.simulation.artifacts import build_pareto_payload, save_artifacts  # noqa: E402
from experiment.simulation.engine import build_kg, run_once  # noqa: E402

# ── 결과 저장 디렉토리 ──────────────────────────────────────────────────────
_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1"


# ──────────────────────────────────────────────────────────────────────────────
# Loop A — 30회 독립 실행 (단일 날, 고정 KG)
# ──────────────────────────────────────────────────────────────────────────────

def run_loop_a(
    mains: list[dict],
    sides_soup: list[dict],
    drinks: list[dict],
    snacks: list[dict],
    kg_base,
    cal_star: float,
    price_star: float,
    n_runs: int,
    pop_size: int,
    n_gen: int,
) -> dict[str, dict]:
    """G1/G2/G3 각 n_runs회 실행. KG는 업데이트하지 않음 (단일 날 고정 상태)."""
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.nutrition import NutritionProfile

    profile = NutritionProfile.who2025()

    groups: dict[str, dict] = {
        g: {"F_list": [], "times": [], "snapshots_all": []}
        for g in ("G1", "G2", "G3")
    }

    # G1/G2: 3목적 (f1, f2, f3) — KG 미포함
    # G3:    4목적 (f1, f2, f3, f4) — KG 통합
    # 두 problem 모두 KG는 record_eating 미호출이므로 stateless.
    problem_3obj = DailyExp3Problem(
        mains=mains, sides_soup=sides_soup,
        drinks=drinks, snacks=snacks,
        n_meals=N_MEALS, include_snack=False,
        cal_star=cal_star, price_per_meal_star=price_star,
        profile=profile,
        kg_manager=kg_base,
        user_id=TEST_USER,
        lambda_decay=0.5,
        use_f4=False,
    )
    problem_4obj = DailyExp3Problem(
        mains=mains, sides_soup=sides_soup,
        drinks=drinks, snacks=snacks,
        n_meals=N_MEALS, include_snack=False,
        cal_star=cal_star, price_per_meal_star=price_star,
        profile=profile,
        kg_manager=kg_base,
        user_id=TEST_USER,
        lambda_decay=0.5,
        use_f4=True,
    )

    algo_defs = [
        ("G1", problem_3obj, lambda: make_nsga2(pop_size)),
        ("G2", problem_3obj, lambda: make_rnsga2(pop_size, REF_G2)),
        ("G3", problem_4obj, lambda: make_rnsga2(pop_size, REF_G3)),
    ]

    for run_idx in range(n_runs):
        seed = SEED_START + run_idx
        print(f"  [Loop A] Run {run_idx + 1:2d}/{n_runs}  seed={seed}")
        for gname, prob, algo_fn in algo_defs:
            F, elapsed, snaps = run_once(prob, algo_fn(), n_gen, seed)
            groups[gname]["F_list"].append(F)
            groups[gname]["times"].append(elapsed)
            groups[gname]["snapshots_all"].append(snaps)
            print(f"    {gname}: {len(F):3d}해  {elapsed:.2f}s")

    return groups


# ──────────────────────────────────────────────────────────────────────────────
# 지표 계산
# ──────────────────────────────────────────────────────────────────────────────

def compute_loop_a_metrics(
    groups: dict[str, dict],
    ref_map: dict[str, np.ndarray],
    nadir_map: dict[str, np.ndarray],
) -> dict[str, dict]:
    """각 그룹의 n_runs회 HV, GD+, IGD+ 산출.

    ref_map / nadir_map: 그룹별 reference front / nadir
    (G1/G2는 3D, G3는 4D — 차원이 다르므로 그룹마다 분리).
    """
    from experiment.core.metrics import compute_indicators

    result: dict[str, dict] = {}
    for gname, gdata in groups.items():
        ref_front = ref_map[gname]
        nadir     = nadir_map[gname]
        hv_vals, gdp_vals, igdp_vals = [], [], []
        for F in gdata["F_list"]:
            if len(F) == 0:
                hv_vals.append(np.nan)
                gdp_vals.append(np.nan)
                igdp_vals.append(np.nan)
            else:
                inds = compute_indicators(F, ref_front, nadir)
                hv_vals.append(inds["HV"])
                gdp_vals.append(inds["GD+"])
                igdp_vals.append(inds["IGD+"])
        result[gname] = {
            "hv":    hv_vals,
            "gdp":   gdp_vals,
            "igdp":  igdp_vals,
            "times": gdata["times"],
        }
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Wilcoxon rank-sum test
# ──────────────────────────────────────────────────────────────────────────────

def compute_wilcoxon(metrics: dict[str, dict]) -> dict:
    """비모수 검정 (Wilcoxon rank-sum).

    - G1 vs G2 (둘 다 3D): R-NSGA-II 알고리즘 순효과 검증
    - G1 vs G3, G2 vs G3 (차원 다름): 직접 비교 의미 약하나 참고용 산출
      (HV는 4D vs 3D 부피 단위 다름 — 해석 시 주의 필요)

    Returns:
        {(base_group, target_group, metric_label): p_value}
    """
    from scipy.stats import ranksums

    p_vals: dict[tuple, float] = {}
    pairs = [("G1", "G2"), ("G1", "G3"), ("G2", "G3")]
    for base, target in pairs:
        for metric_key, label in [("hv", "HV"), ("gdp", "GD+"), ("igdp", "IGD+")]:
            a = [x for x in metrics[base][metric_key]   if not np.isnan(x)]
            b = [x for x in metrics[target][metric_key] if not np.isnan(x)]
            if len(a) >= 3 and len(b) >= 3:
                _, p = ranksums(a, b)
                p_vals[(base, target, label)] = float(p)
            else:
                p_vals[(base, target, label)] = np.nan
    return p_vals


# ──────────────────────────────────────────────────────────────────────────────
# Loop B — G3 7일 시뮬레이션 (매일 KG 업데이트)
# ──────────────────────────────────────────────────────────────────────────────

def run_loop_b(
    mains: list[dict],
    sides_soup: list[dict],
    drinks: list[dict],
    snacks: list[dict],
    all_foods: list[dict],
    cal_star: float,
    price_star: float,
    n_days: int,
    pop_size: int,
    n_gen: int,
) -> list[dict]:
    """G3 n_days일 시뮬레이션.

    simulate_kg._run_one_day()를 재사용하여 코드 중복 방지.
    Loop B 전용 KG를 별도 생성 (Loop A의 kg_base와 완전 분리).
    """
    from experiment.simulation.simulate_kg import _run_one_day
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.core.nutrition import NutritionProfile

    kg = build_kg(all_foods)            # Loop B 전용 KG (독립 인스턴스)
    profile = NutritionProfile.who2025()
    base_date = datetime(2026, 5, 7, 12, 0, 0)   # 고정 시작 날짜 (재현성)

    daily_logs: list[dict] = []
    menu_history: list[str] = []        # 누적 메뉴 목록 (중복률 계산용)
    prev_combo = None                   # 전날 선택 메뉴 (다음 day에 record_eating)

    for day in range(1, n_days + 1):
        today = base_date + timedelta(days=day - 1)
        seed  = SEED_START + day

        # ★ 전날 선택 메뉴를 오늘 기록 (1일 경과로 decay 효과 발생)
        if prev_combo is not None:
            for item in prev_combo:
                mid = make_menu_id(item)
                if mid:
                    kg.record_eating(TEST_USER, mid, today)

        problem = DailyExp3Problem(
            mains=mains, sides_soup=sides_soup,
            drinks=drinks, snacks=snacks,
            n_meals=N_MEALS, include_snack=False,
            cal_star=cal_star, price_per_meal_star=price_star,
            profile=profile,
            kg_manager=kg,
            user_id=TEST_USER,
            lambda_decay=0.5,
            sim_now=today,              # 가상 현재 시각 — ATE 타임스탬프와 동일 시계
        )

        best_F, best_X = _run_one_day(problem, pop_size, n_gen, seed, REF_G3)

        if best_F is None:
            daily_logs.append({
                "day": day, "date": today.strftime("%Y-%m-%d"),
                "f1": np.nan, "f2": np.nan, "f3": np.nan, "f4": np.nan,
                "menu_names": [], "categories": [], "duplication_rate": np.nan,
            })
            print(f"  [Loop B] Day {day}: ⚠ 실행 가능한 해 없음")
            prev_combo = None
            continue

        combo      = problem.decode(best_X)
        menu_names = [
            str(item.get("product_name") or item.get("menu_name") or "")
            for item in combo
        ]
        categories = [item.get("category", "UNKNOWN") for item in combo]
        f1, f2, f3, f4 = best_F

        # ★ 오늘 선택을 내일을 위해 저장 (내일 record_eating 호출)
        prev_combo = combo

        # 누적 중복률 계산
        menu_history.extend(menu_names)
        cnt = Counter(menu_history)
        repeated = sum(v - 1 for v in cnt.values() if v > 1)
        dup_rate = repeated / len(menu_history) if menu_history else 0.0

        # KG 점수 상세 정보
        from experiment.core.kg_manager import make_menu_id
        menu_ids_today = [make_menu_id(item) for item in combo if make_menu_id(item)]
        kg_scores = []
        for mid in menu_ids_today:
            edata = kg.G.get_edge_data(TEST_USER, mid, default={})
            pref = float(edata.get("pref", 1.0))
            last_ate = edata.get("last_ate")
            if last_ate is not None:
                import math
                delta_days = max(0.0, (today - last_ate).total_seconds() / 86400.0)
                decay = min(1.0, math.exp(-0.5 * delta_days))
            else:
                decay = 0.0
            score = pref * (1 - decay)
            kg_scores.append(score)

        avg_kg = float(np.mean(kg_scores)) if kg_scores else 0.0
        max_s = kg.max_possible_score(TEST_USER)

        daily_logs.append({
            "day": day, "date": today.strftime("%Y-%m-%d"),
            "f1": float(f1), "f2": float(f2),
            "f3": float(f3), "f4": float(f4),
            "menu_names": menu_names, "categories": categories,
            "duplication_rate": float(dup_rate),
        })

        print(f"  [Loop B] Day {day} ({today.strftime('%m-%d')}): "
              f"f4={f4:.4f}  f1={f1:.4f}  중복률={dup_rate:.1%}  "
              f"avg_kg={avg_kg:.3f}  max_s={max_s:.3f}  menus={len(menu_ids_today)}")

    return daily_logs


# ──────────────────────────────────────────────────────────────────────────────
# 저장 — CSV
# ──────────────────────────────────────────────────────────────────────────────

def save_metrics_csv(
    out_dir: Path,
    metrics: dict[str, dict],
    p_vals: dict,
    n_runs: int,
) -> None:
    """metrics_comparison.csv — G1/G2/G3 × HV/GD+/IGD+, 실행시간, p-value."""
    path = out_dir / "metrics_comparison.csv"
    fieldnames = [
        "group", "metric", "mean", "std", "min", "max",
        "avg_time_sec", "wilcoxon_p_vs_G3", "seed_start", "n_runs",
    ]
    rows = []
    for gname in ("G1", "G2", "G3"):
        g = metrics[gname]
        avg_t = float(np.nanmean(g["times"]))
        for metric_key, label in [("hv", "HV"), ("gdp", "GD+"), ("igdp", "IGD+")]:
            vals = [x for x in g[metric_key] if not np.isnan(x)]
            p = p_vals.get((gname, "G3", label), np.nan) if gname != "G3" else np.nan
            rows.append({
                "group":              gname,
                "metric":             label,
                "mean":               f"{np.mean(vals):.6f}"  if vals else "nan",
                "std":                f"{np.std(vals):.6f}"   if vals else "nan",
                "min":                f"{np.min(vals):.6f}"   if vals else "nan",
                "max":                f"{np.max(vals):.6f}"   if vals else "nan",
                "avg_time_sec":       f"{avg_t:.3f}",
                "wilcoxon_p_vs_G3":   f"{p:.4f}" if not np.isnan(p) else "nan",
                "seed_start":         SEED_START,
                "n_runs":             n_runs,
            })
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  💾 {path.name}")


def save_perrun_metrics_csv(out_dir: Path, metrics: dict[str, dict]) -> None:
    """per_run_metrics.csv — 각 run의 개별 HV/GD+/IGD+/time_sec 저장.

    columns: group, run_idx, HV, GD+, IGD+, time_sec
    G1/G2 (3D)와 G3 (4D) 모두 동일 포맷으로 저장.
    """
    path = out_dir / "per_run_metrics.csv"
    fieldnames = ["group", "run_idx", "HV", "GD+", "IGD+", "time_sec"]
    rows = []
    for gname in ("G1", "G2", "G3"):
        g = metrics[gname]
        for i, (hv, gdp, igdp, t) in enumerate(
            zip(g["hv"], g["gdp"], g["igdp"], g["times"])
        ):
            rows.append({
                "group":    gname,
                "run_idx":  i,
                "HV":       f"{hv:.6f}"   if not np.isnan(hv)   else "nan",
                "GD+":      f"{gdp:.6f}"  if not np.isnan(gdp)  else "nan",
                "IGD+":     f"{igdp:.6f}" if not np.isnan(igdp) else "nan",
                "time_sec": f"{t:.3f}",
            })
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  💾 {path.name}")


def save_daily_csvs(out_dir: Path, daily_logs: list[dict]) -> None:
    # daily_f4_trend.csv
    f4_path = out_dir / "daily_f4_trend.csv"
    with open(f4_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day", "date", "f1", "f2", "f3", "f4"])
        w.writeheader()
        for log in daily_logs:
            w.writerow({k: log.get(k, "") for k in ["day", "date", "f1", "f2", "f3", "f4"]})
    print(f"  💾 {f4_path.name}")

    # daily_duplication.csv
    dup_path = out_dir / "daily_duplication.csv"
    with open(dup_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day", "date", "duplication_rate"])
        w.writeheader()
        for log in daily_logs:
            dup = log.get("duplication_rate", np.nan)
            w.writerow({
                "day":              log["day"],
                "date":             log["date"],
                "duplication_rate": f"{dup:.4f}" if not np.isnan(dup) else "nan",
            })
    print(f"  💾 {dup_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# 요약 출력
# ──────────────────────────────────────────────────────────────────────────────

def print_summary(metrics: dict[str, dict], p_vals: dict) -> None:
    print("\n" + "=" * 65)
    print("  📊 Loop A 결과 요약 (평균 ± 표준편차)")
    print("=" * 65)
    for gname in ("G1", "G2", "G3"):
        g = metrics[gname]
        print(
            f"  {gname}: HV={np.nanmean(g['hv']):.4f}±{np.nanstd(g['hv']):.4f}"
            f"  GD+={np.nanmean(g['gdp']):.4f}"
            f"  IGD+={np.nanmean(g['igdp']):.4f}"
            f"  time={np.nanmean(g['times']):.2f}s"
        )
    print("\n  📈 Wilcoxon rank-sum test")
    print("    [G1 vs G2] R-NSGA-II 알고리즘 순효과 (둘 다 3D, 직접 비교 가능)")
    for label in ("HV", "GD+", "IGD+"):
        p = p_vals.get(("G1", "G2", label), np.nan)
        if np.isnan(p):
            print(f"      G1 vs G2 [{label}]: p=nan")
        else:
            sig = "✅ p<0.05" if p < 0.05 else "❌ n.s."
            print(f"      G1 vs G2 [{label}]: p={p:.4f}  {sig}")
    print("    [vs G3] 차원 다름(3D↔4D) — HV 절대값 비교는 단위 다름 caveat")
    for base in ("G1", "G2"):
        for label in ("HV", "GD+", "IGD+"):
            p = p_vals.get((base, "G3", label), np.nan)
            if np.isnan(p):
                print(f"      {base} vs G3 [{label}]: p=nan")
            else:
                sig = "✅ p<0.05" if p < 0.05 else "❌ n.s."
                print(f"      {base} vs G3 [{label}]: p={p:.4f}  {sig}")


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="1단계 기술적 검증 시뮬레이션 (계산 전담)")
    parser.add_argument("--cal_star",    type=float, default=2000.0)
    parser.add_argument("--price_star",  type=float, default=8000.0)
    parser.add_argument("--n_runs",      type=int,   default=30,
                        help="Loop A 독립 실행 횟수")
    parser.add_argument("--n_days",      type=int,   default=7,
                        help="Loop B 시뮬레이션 일수")
    parser.add_argument("--pop_size",    type=int,   default=200)
    parser.add_argument("--n_gen",       type=int,   default=200)
    parser.add_argument("--test",        action="store_true",
                        help="테스트 모드: pop=10, gen=20, runs=3, days=2")
    parser.add_argument("--skip_loop_b", action="store_true",
                        help="Loop B(7일 시뮬레이션) 건너뜀")
    parser.add_argument("--plot",        action="store_true",
                        help="계산 후 시각화까지 실행 (저장된 아티팩트를 로드해 그림 생성)")
    args = parser.parse_args()

    if args.test:
        args.pop_size = 10
        args.n_gen    = 20
        args.n_runs   = 3
        args.n_days   = 2
        print("⚡ [TEST MODE] pop=10, gen=20, runs=3, days=2")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 데이터 로딩 ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  📦 Supabase 데이터 로딩")
    from experiment.core.loader import FoodDataLoader

    loader     = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks
    print(f"  MAIN:{len(mains)} SIDE_SOUP:{len(sides_soup)} "
          f"DRINK:{len(drinks)} SNACK:{len(snacks)}")

    # ── KG 초기화 (Loop A 공용 — 업데이트 없음) ────────────────────────────
    print("\n  🔗 KG 초기화 (고정 상태: Loop A 전용)")
    kg_base = build_kg(all_foods)
    print(f"  nodes={kg_base.G.number_of_nodes()}  "
          f"edges={kg_base.G.number_of_edges()}  "
          f"max_score={kg_base.max_possible_score(TEST_USER):.3f}")

    # ── Loop A ─────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  🚀 Loop A: G1/G2/G3 × {args.n_runs}회 독립 실행")
    print(f"  Cal*={args.cal_star} | Price*={args.price_star} | "
          f"pop={args.pop_size} | gen={args.n_gen}")
    print("=" * 65)

    groups = run_loop_a(
        mains, sides_soup, drinks, snacks, kg_base,
        args.cal_star, args.price_star,
        args.n_runs, args.pop_size, args.n_gen,
    )

    # ── Reference Front & Nadir (그룹별 분리 — G1/G2는 3D, G3는 4D) ───────
    print("\n  📐 Reference Front 계산 (G1+G2 합병 3D / G3 단독 4D)")
    from experiment.core.metrics import compute_reference_pf

    # G1+G2: 3D ref_front (R-NSGA-II 순효과 비교용)
    F_3d_list = [F for g in ("G1", "G2") for F in groups[g]["F_list"] if len(F) > 0]
    # G3: 4D ref_front (KG 통합 모델 단독 평가)
    F_4d_list = [F for F in groups["G3"]["F_list"] if len(F) > 0]
    if not F_3d_list or not F_4d_list:
        print("⚠ 유효한 해 없음. 프로그램 종료.")
        return

    all_F_3d  = np.vstack(F_3d_list)
    ref_3d    = compute_reference_pf(all_F_3d)
    nadir_3d  = all_F_3d.max(axis=0) * 1.1

    all_F_4d  = np.vstack(F_4d_list)
    ref_4d    = compute_reference_pf(all_F_4d)
    nadir_4d  = all_F_4d.max(axis=0) * 1.1

    ref_map   = {"G1": ref_3d,   "G2": ref_3d,   "G3": ref_4d}
    nadir_map = {"G1": nadir_3d, "G2": nadir_3d, "G3": nadir_4d}

    print(f"  ref_3d (G1/G2) 크기: {len(ref_3d)}해 / nadir_3d: {np.round(nadir_3d, 3)}")
    print(f"  ref_4d (G3)    크기: {len(ref_4d)}해 / nadir_4d: {np.round(nadir_4d, 3)}")

    # ── 지표 계산 & Wilcoxon ───────────────────────────────────────────────
    print("\n  📊 GD+/IGD+/HV 계산 + Wilcoxon rank-sum test")
    metrics = compute_loop_a_metrics(groups, ref_map, nadir_map)
    p_vals  = compute_wilcoxon(metrics)
    print_summary(metrics, p_vals)

    # ── CSV 저장 ──────────────────────────────────────────────────────────
    print(f"\n  💾 CSV 저장 → {_OUT_DIR}")
    save_metrics_csv(_OUT_DIR, metrics, p_vals, args.n_runs)
    save_perrun_metrics_csv(_OUT_DIR, metrics)

    # ── Loop B ────────────────────────────────────────────────────────────
    daily_logs: list[dict] = []
    if not args.skip_loop_b:
        print(f"\n{'='*65}")
        print(f"  🌐 Loop B: G3 {args.n_days}일 시뮬레이션 (KG 동적 업데이트)")
        print("=" * 65)
        daily_logs = run_loop_b(
            mains, sides_soup, drinks, snacks, all_foods,
            args.cal_star, args.price_star,
            args.n_days, args.pop_size, args.n_gen,
        )
        save_daily_csvs(_OUT_DIR, daily_logs)
    else:
        print("\n  ⏭ Loop B 건너뜀 (--skip_loop_b)")

    # ── 아티팩트 저장 (시각화 재현용 — 알고리즘 재실행 방지) ──────────────
    print("\n  📦 아티팩트 저장 (시각화 재현용)")
    payload = {
        "groups":     groups,
        "nadir_map":  nadir_map,
        "metrics":    metrics,
        "p_vals":     p_vals,
        "pareto":     build_pareto_payload(groups),
        "daily_logs": daily_logs,
        "meta": {
            "n_gen":      args.n_gen,
            "pop_size":   args.pop_size,
            "n_runs":     args.n_runs,
            "n_days":     args.n_days,
            "cal_star":   args.cal_star,
            "price_star": args.price_star,
        },
    }
    save_artifacts(_OUT_DIR, payload)

    print(f"\n✅ 계산 완료! 산출물 → {_OUT_DIR}")

    # ── (옵션) 시각화 — 저장된 아티팩트를 로드해 그림 생성 ────────────────
    if args.plot:
        print("\n  🖼  시각화 (아티팩트 로드 — 최적화 재실행 없음)")
        from experiment.visualization.plot_step1 import render_from_dir
        render_from_dir(_OUT_DIR)
    else:
        print("  ▸ 시각화: python -X utf8 -m experiment.visualization.plot_step1")


if __name__ == "__main__":
    main()
