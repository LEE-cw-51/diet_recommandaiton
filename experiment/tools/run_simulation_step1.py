"""1단계 기술적 검증 시뮬레이션 — G1/G2/G3 알고리즘 비교.

루프 A: NSGA-II(G1) vs R-NSGA-II 고정 KG(G2) vs R-NSGA-II 동적 ref_points(G3)
        30회 독립 실행 → HV, GD+, IGD+, 실행시간(avg_time_sec), Wilcoxon p-value

루프 B: G3 7일 시뮬레이션 (매일 KG record_eating 업데이트)
        f4 추이, 메뉴 중복률 추이

팩트 체크 반영 사항:
  [오류수정1] Nadir Point — 고정값 금지, all_F.max(axis=0)*1.1 동적 계산
  [오류수정2] RNSGA2 ref_points — 반드시 2D array (shape: n_ref × n_obj)
  [오류수정3] Loop A/B 역할 분리 — 루프 A는 30회 단일날, 루프 B는 7일 KG 업데이트
  [보완1] GD 대신 GD+/IGD+ 사용 (weakly Pareto compliant, 논문 표준)
  [보완2] Callback으로 10세대마다 F 스냅샷 수집 후 HV 후처리 (4D HV 계산 비용 회피)
  [보완3] simulate_kg.py의 _run_one_day() 재사용
  [추가A] Random Seed 고정: seed=SEED_START+i, np.random.seed() 동시 적용
  [추가B] time.perf_counter()로 실행시간 측정 → avg_time_sec CSV 기록
  [추가C] Wilcoxon rank-sum test (G1 vs G3, G2 vs G3) — scipy.stats.ranksums
  [추가D] 초기 KG 상태 고정 (TEST_USER, KG_PREFERENCES, KG_HISTORY) — 재현 가능 조건

산출물: experiment/results/step1/
  metrics_comparison.csv  daily_f4_trend.csv  daily_duplication.csv
  plot_convergence.png    plot_7days_f4.png

사용법:
  python -X utf8 -m experiment.tools.run_simulation_step1 --cal_star 2000 --price_star 8000
  python -X utf8 -m experiment.tools.run_simulation_step1 --test
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── matplotlib 설정 (헤드리스 환경 대응) ─────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("⚠ matplotlib 미설치 — PNG 그래프 생략 (pip install matplotlib)")

# ── 결과 저장 디렉토리 ──────────────────────────────────────────────────────
_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1"

# ──────────────────────────────────────────────────────────────────────────────
# 재현성 & 실험 상수
# ──────────────────────────────────────────────────────────────────────────────

SEED_START = 42        # 30회 run의 seed = SEED_START + run_idx
N_MEALS    = 3         # 하루 3끼 (간식 미포함)
HV_SAMPLE_EVERY = 10  # Callback: 매 10세대마다 F 스냅샷 수집

# ── 초기 KG 상태 — 고정 테스트 유저 (재현 가능 조건) ─────────────────────────
# 비어있는 KG에서는 G2/G3 모두 f4가 동일하게 나와 비교 의미 없음.
# MAIN 선호(1.2)·DRINK 비선호(0.8)와 섭취 이력 2건을 사전 세팅.
TEST_USER      = "test_user_1"
KG_PREFERENCES = {
    "비빔밥":   4,   # 4★ → P_i = 4/3 ≈ 1.33
    "된장찌개": 3,   # 3★ → P_i = 1.0 (중립)
}  # 메뉴 직접 별점 (카테고리 선호도 제거)
KG_HISTORY     = [
    {"menu_id": "비빔밥",   "timestamp": "2026-05-06T12:00:00"},
    {"menu_id": "된장찌개", "timestamp": "2026-05-06T19:00:00"},
]

# ── R-NSGA-II 참조점 — 반드시 2D numpy array (shape: n_ref × n_obj) ─────────
# 1D 배열을 넘기면 pymoo 내부 shape 오류 발생.
# G2는 3목적(f1, f2, f3) — KG 미포함, R-NSGA-II 알고리즘 순효과 검증용
# G3는 4목적(f1, f2, f3, f4) — KG 통합, 본 제안 모델
_REF_G2 = np.array([[0.0, 0.0, 0.0]])                               # G2: 3D 단일점
_REF_G3 = np.array([[0.0, 0.0, 0.0, 0.0], [0.1, 0.1, 0.1, 0.0]])    # G3: 4D 두 참조점


# ──────────────────────────────────────────────────────────────────────────────
# Callback — 세대별 F 스냅샷 수집
# ──────────────────────────────────────────────────────────────────────────────

from pymoo.core.callback import Callback  # noqa: E402


class _FSnapshotCallback(Callback):
    """4D HV는 O(n^3) — 매 세대 계산 시 매우 느리므로 F만 수집하고 후처리."""

    def __init__(self, sample_every: int = HV_SAMPLE_EVERY):
        super().__init__()
        self.data["snapshots"] = []   # [(gen: int, F: ndarray), ...]
        self._sample_every = sample_every

    def notify(self, algorithm) -> None:
        if algorithm.n_gen % self._sample_every == 0:
            F = algorithm.pop.get("F")
            if F is not None and len(F) > 0:
                self.data["snapshots"].append((int(algorithm.n_gen), F.copy()))


# ──────────────────────────────────────────────────────────────────────────────
# 알고리즘 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

def _make_nsga2(pop_size: int):
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.operators.crossover.pntx import PointCrossover
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import IntegerRandomSampling

    return NSGA2(
        pop_size=pop_size,
        sampling=IntegerRandomSampling(),
        crossover=PointCrossover(n_points=2, prob=0.9),
        mutation=PM(prob=0.083, eta=20),
        eliminate_duplicates=True,
    )


def _make_rnsga2(pop_size: int, ref_points: np.ndarray):
    from pymoo.algorithms.moo.rnsga2 import RNSGA2
    from pymoo.operators.crossover.pntx import PointCrossover
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import IntegerRandomSampling

    return RNSGA2(
        ref_points=ref_points,
        pop_size=pop_size,
        epsilon=0.001,
        normalization="front",
        sampling=IntegerRandomSampling(),
        crossover=PointCrossover(n_points=2, prob=0.9),
        mutation=PM(prob=0.083, eta=20),
        eliminate_duplicates=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 단일 실행
# ──────────────────────────────────────────────────────────────────────────────

def _run_once(
    problem,
    algorithm,
    n_gen: int,
    seed: int,
) -> tuple[np.ndarray, float, list[tuple[int, np.ndarray]]]:
    """단일 최적화 실행.

    Args:
        seed: np.random.seed()와 minimize(seed=)에 동시 적용하여 재현성 보장.

    Returns:
        (feasible_F, elapsed_sec, snapshots)
    """
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination

    np.random.seed(seed)   # numpy 전역 시드 고정 (재현성)
    cb = _FSnapshotCallback()

    t0 = time.perf_counter()
    res = minimize(
        problem, algorithm,
        get_termination("n_gen", n_gen),
        seed=seed,           # pymoo 내부 시드 고정
        callback=cb,
        verbose=False,
    )
    elapsed = time.perf_counter() - t0

    if res is None or res.F is None or len(res.F) == 0:
        return np.empty((0, problem.n_obj)), elapsed, []

    mask = (
        np.all(res.G <= 0, axis=1)
        if res.G is not None
        else np.ones(len(res.F), dtype=bool)
    )
    F = res.F[mask]
    snapshots: list[tuple[int, np.ndarray]] = res.algorithm.callback.data["snapshots"]
    return F, elapsed, snapshots


# ──────────────────────────────────────────────────────────────────────────────
# KGManager 초기화 (고정 조건)
# ──────────────────────────────────────────────────────────────────────────────

def _build_kg(all_foods: list[dict]):
    from experiment.core.kg_manager import KGManager

    kg_cfg = {
        "user_id":      TEST_USER,
        "preferences":  KG_PREFERENCES,
        "user_history": KG_HISTORY,
    }
    return KGManager.from_config(all_foods, kg_cfg, user_id=TEST_USER)


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
    """G1/G2/G3 각 n_runs회 실행. KG는 업데이트하지 않음 (단일 날 고정 상태).

    Returns:
        {
            "G1": {"F_list": [...], "times": [...], "snapshots_all": [...]},
            "G2": {...},
            "G3": {...},
        }
    """
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
        ("G1", problem_3obj, lambda: _make_nsga2(pop_size)),
        ("G2", problem_3obj, lambda: _make_rnsga2(pop_size, _REF_G2)),
        ("G3", problem_4obj, lambda: _make_rnsga2(pop_size, _REF_G3)),
    ]

    for run_idx in range(n_runs):
        seed = SEED_START + run_idx
        print(f"  [Loop A] Run {run_idx + 1:2d}/{n_runs}  seed={seed}")
        for gname, prob, algo_fn in algo_defs:
            F, elapsed, snaps = _run_once(prob, algo_fn(), n_gen, seed)
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

    simulate_kg.py의 _run_one_day()를 재사용하여 코드 중복 방지.
    Loop B 전용 KG를 별도 생성 (Loop A의 kg_base와 완전 분리).
    """
    from experiment.tools.simulate_kg import _run_one_day
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.core.nutrition import NutritionProfile

    kg = _build_kg(all_foods)           # Loop B 전용 KG (독립 인스턴스)
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

        best_F, best_X = _run_one_day(problem, pop_size, n_gen, seed, _REF_G3)

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
# 시각화 — PNG
# ──────────────────────────────────────────────────────────────────────────────

_GROUP_COLORS = {"G1": "#e74c3c", "G2": "#2980b9", "G3": "#27ae60"}
_GROUP_LABELS = {
    "G1": "G1: NSGA-II (3-obj, no KG)",
    "G2": "G2: R-NSGA-II (3-obj, no KG)",
    "G3": "G3: R-NSGA-II + KG (4-obj, Proposed)",
}


def plot_convergence(
    out_dir: Path,
    groups: dict[str, dict],
    nadir_map: dict[str, np.ndarray],
    n_gen: int,
) -> None:
    """세대별 HV 수렴 곡선 (HV_SAMPLE_EVERY 간격, 30회 평균 ± 표준편차).

    F 스냅샷에 Nadir을 적용해 후처리 계산 → 4D HV 반복 호출 최소화.
    그룹별 nadir이 달라(3D vs 4D), HV 값의 절대치는 그룹 간 비교 불가 — 각자 수렴 형태만 비교.
    """
    if not HAS_MPL:
        return

    from pymoo.indicators.hv import HV

    hv_inds   = {g: HV(ref_point=nadir_map[g]) for g in groups.keys()}
    gen_ticks = list(range(HV_SAMPLE_EVERY, n_gen + 1, HV_SAMPLE_EVERY))

    fig, ax = plt.subplots(figsize=(9, 5))

    for gname, gdata in groups.items():
        hv_ind = hv_inds[gname]
        gen_hv: dict[int, list[float]] = {g: [] for g in gen_ticks}
        for snaps in gdata["snapshots_all"]:
            snap_dict = dict(snaps)
            for gt in gen_ticks:
                F = snap_dict.get(gt)
                if F is not None and len(F) > 0:
                    try:
                        gen_hv[gt].append(float(hv_ind(F)))
                    except Exception:
                        pass

        x_vals = [g for g in gen_ticks if gen_hv[g]]
        y_mean = [float(np.mean(gen_hv[g])) for g in x_vals]
        y_std  = [float(np.std(gen_hv[g]))  for g in x_vals]

        ax.plot(x_vals, y_mean,
                color=_GROUP_COLORS[gname], label=_GROUP_LABELS[gname], linewidth=2)
        ax.fill_between(
            x_vals,
            np.array(y_mean) - np.array(y_std),
            np.array(y_mean) + np.array(y_std),
            alpha=0.15, color=_GROUP_COLORS[gname],
        )

    ax.set_xlabel("Generation", fontsize=12)
    ax.set_ylabel("Hypervolume (HV)", fontsize=12)
    ax.set_title("Convergence: HV per Generation (mean ± std)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = out_dir / "plot_convergence.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"  🖼  {path.name}")


def plot_7days_f4(out_dir: Path, daily_logs: list[dict]) -> None:
    """G3 7일 f4(KG 오차율) 추이 — f1(칼로리 오차) 보조축 병행."""
    if not HAS_MPL:
        return

    valid = [log for log in daily_logs if not np.isnan(log.get("f4", np.nan))]
    if not valid:
        print("  ⚠ Loop B 유효 결과 없음 — plot_7days_f4.png 생략")
        return

    days  = [log["day"]  for log in valid]
    f4    = [log["f4"]   for log in valid]
    f1    = [log["f1"]   for log in valid]
    dates = [log["date"] for log in valid]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    ax1.plot(days, f4, "o-", color="#27ae60", linewidth=2, label="f4 (KG Error Rate)")
    ax2.plot(days, f1, "s--", color="#e74c3c", linewidth=1.5, alpha=0.7, label="f1 (Calorie Error)")

    ax1.set_xlabel("Day", fontsize=12)
    ax1.set_ylabel("f4: KG Error Rate", color="#27ae60", fontsize=12)
    ax2.set_ylabel("f1: Calorie Error Rate", color="#e74c3c", fontsize=12)
    ax1.set_title("G3: 7-Day f4 Trend (KG Dynamic Update)", fontsize=13)
    ax1.set_xticks(days)
    ax1.set_xticklabels(dates, rotation=30, ha="right")

    lines1, lbl1 = ax1.get_legend_handles_labels()
    lines2, lbl2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lbl1 + lbl2, fontsize=10, loc="upper right")
    ax1.grid(True, alpha=0.3)
    plt.tight_layout()

    path = out_dir / "plot_7days_f4.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"  🖼  {path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# 시각화 — G1/G2/G3 지표 비교 (박스플롯 + 바 차트)
# ──────────────────────────────────────────────────────────────────────────────

def _sig_label(p: float) -> str:
    """p-value → 유의성 기호 (논문 표준 표기)."""
    if np.isnan(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _draw_significance_bracket(
    ax,
    x1: float, x2: float,
    y_top: float, label: str,
    color: str = "black",
) -> None:
    """두 그룹 사이에 유의성 브래킷 그리기."""
    if not label:
        return
    h = (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.04
    ax.plot([x1, x1, x2, x2], [y_top, y_top + h, y_top + h, y_top],
            lw=1.0, color=color)
    ax.text((x1 + x2) / 2, y_top + h * 1.1, label,
            ha="center", va="bottom", fontsize=9, color=color)


def plot_metrics_boxplot(
    out_dir: Path,
    metrics: dict[str, dict],
    p_vals: dict,
) -> None:
    """G1/G2/G3 × HV/GD+/IGD+ 박스플롯 (3 서브플롯, 유의성 브래킷 포함).

    논문 Fig. 표준 형식: 30회 분포를 박스로 표현.
    HV는 높을수록 좋음(↑), GD+/IGD+는 낮을수록 좋음(↓).
    """
    if not HAS_MPL:
        return

    metric_defs = [
        ("hv",   "HV",   "Hypervolume (HV) ↑",   True),
        ("gdp",  "GD+",  "GD+ (lower is better ↓)", False),
        ("igdp", "IGD+", "IGD+ (lower is better ↓)", False),
    ]

    gnames = ["G1", "G2", "G3"]
    short_labels = [_GROUP_LABELS[g].split(":")[0] for g in gnames]  # "G1", "G2", "G3"
    positions = [1, 2, 3]

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle(
        "Algorithm Comparison: G1 vs G2 vs G3 (30 Independent Runs)",
        fontsize=13, fontweight="bold", y=1.01,
    )

    for ax, (mkey, mlabel, mtitle, higher_better) in zip(axes, metric_defs):
        data = [
            [x for x in metrics[g][mkey] if not np.isnan(x)]
            for g in gnames
        ]
        colors = [_GROUP_COLORS[g] for g in gnames]

        bp = ax.boxplot(
            data,
            positions=positions,
            patch_artist=True,
            widths=0.5,
            medianprops=dict(color="white", linewidth=2),
            flierprops=dict(marker="o", markersize=3, alpha=0.5),
            notch=False,
        )
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
        for whisker in bp["whiskers"]:
            whisker.set(linewidth=1.2, linestyle="--", color="gray")
        for cap in bp["caps"]:
            cap.set(linewidth=1.2, color="gray")

        ax.set_title(mtitle, fontsize=11, pad=8)
        ax.set_xticks(positions)
        ax.set_xticklabels(short_labels, fontsize=10)
        ax.set_ylabel(mlabel, fontsize=10)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
        ax.set_xlim(0.4, 3.6)

        # 유의성 브래킷: G1 vs G3 (위), G2 vs G3 (아래)
        y_max = max((max(d) if d else 0) for d in data)
        y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
        ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] + y_range * 0.25)

        for (base, target, offset_ratio) in [("G1", "G3", 0.12), ("G2", "G3", 0.22)]:
            p = p_vals.get((base, target, mlabel), np.nan)
            sig = _sig_label(p)
            if sig:
                xi = positions[gnames.index(base)]
                xj = positions[gnames.index(target)]
                y_br = y_max + y_range * offset_ratio
                _draw_significance_bracket(ax, xi, xj, y_br, sig, color="black")

        # 범례 패치 (첫 번째 서브플롯에만)
        if ax is axes[0]:
            import matplotlib.patches as mpatches
            legend_patches = [
                mpatches.Patch(facecolor=_GROUP_COLORS[g], alpha=0.75,
                               label=_GROUP_LABELS[g])
                for g in gnames
            ]
            ax.legend(handles=legend_patches, fontsize=8,
                      loc="upper right", framealpha=0.8)

    plt.tight_layout()
    path = out_dir / "plot_metrics_boxplot.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  🖼  {path.name}")


def plot_metrics_bar(
    out_dir: Path,
    metrics: dict[str, dict],
    p_vals: dict,
) -> None:
    """G1/G2/G3 지표 그룹드 바 차트 (평균 ± std, 유의성 표기).

    논문 Table 수치를 시각적으로 한 눈에 파악하기 위한 요약 차트.
    """
    if not HAS_MPL:
        return

    gnames      = ["G1", "G2", "G3"]
    metric_keys = [("hv", "HV"), ("gdp", "GD+"), ("igdp", "IGD+")]
    n_metrics   = len(metric_keys)
    n_groups    = len(gnames)

    x = np.arange(n_metrics)
    bar_w = 0.22
    offsets = np.array([-bar_w, 0, bar_w])

    fig, ax = plt.subplots(figsize=(9, 5))

    for i, gname in enumerate(gnames):
        means = [
            float(np.nanmean(metrics[gname][mk])) for mk, _ in metric_keys
        ]
        stds = [
            float(np.nanstd(metrics[gname][mk])) for mk, _ in metric_keys
        ]
        bars = ax.bar(
            x + offsets[i], means, bar_w,
            yerr=stds, capsize=4,
            color=_GROUP_COLORS[gname], alpha=0.80,
            label=_GROUP_LABELS[gname],
            error_kw=dict(elinewidth=1.2, ecolor="gray"),
        )

        # 바 위 수치 표기
        for bar, mean in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(stds) * 0.05,
                f"{mean:.3f}",
                ha="center", va="bottom", fontsize=7, rotation=0,
            )

    # 유의성 표기 (각 지표 위)
    for j, (_, mlabel) in enumerate(metric_keys):
        y_vals = [
            float(np.nanmean(metrics[g][mk])) + float(np.nanstd(metrics[g][mk]))
            for g, (mk, _) in [(g, metric_keys[j]) for g in gnames]
        ]
        y_top = max(y_vals) * 1.12
        for base in ("G1", "G2"):
            p = p_vals.get((base, "G3", mlabel), np.nan)
            sig = _sig_label(p)
            if sig and sig != "n.s.":
                xi = x[j] + offsets[gnames.index(base)]
                xj = x[j] + offsets[gnames.index("G3")]
                ax.annotate(
                    "", xy=(xj, y_top), xytext=(xi, y_top),
                    arrowprops=dict(arrowstyle="-", lw=1.0),
                )
                ax.text((xi + xj) / 2, y_top * 1.01, sig,
                        ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(["HV (↑)", "GD+ (↓)", "IGD+ (↓)"], fontsize=11)
    ax.set_ylabel("Indicator Value (mean ± std)", fontsize=11)
    ax.set_title("Algorithm Comparison: Mean Indicator Values (30 Runs)", fontsize=12)
    ax.legend(fontsize=9, loc="upper right", framealpha=0.85)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    plt.tight_layout()

    path = out_dir / "plot_metrics_bar.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  🖼  {path.name}")


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
    parser = argparse.ArgumentParser(description="1단계 기술적 검증 시뮬레이션")
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
    kg_base = _build_kg(all_foods)
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

    # ── 시각화 ────────────────────────────────────────────────────────────
    if HAS_MPL:
        print("\n  🖼  그래프 생성")
        plot_convergence(_OUT_DIR, groups, nadir_map, args.n_gen)
        plot_metrics_boxplot(_OUT_DIR, metrics, p_vals)
        plot_metrics_bar(_OUT_DIR, metrics, p_vals)

    # ── Loop B ────────────────────────────────────────────────────────────
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
        if HAS_MPL:
            plot_7days_f4(_OUT_DIR, daily_logs)
    else:
        print("\n  ⏭ Loop B 건너뜀 (--skip_loop_b)")

    print(f"\n✅ 완료! 산출물 → {_OUT_DIR}")


if __name__ == "__main__":
    main()
