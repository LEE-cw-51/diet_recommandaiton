"""실험 러너 — 30회 반복, 시드 관리, 기준 PF 계산, 결과 저장.

사용법:
    from experiment.core.runner import run_experiment
    run_experiment(
        config_path="experiment/config/exp1_nsga2.yaml",
        cal_star=2000,
        price_star=8000,
        allergens=["난류"],
    )
"""

from __future__ import annotations

import csv
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

# 프로젝트 루트 기준 경로 설정
_ROOT = Path(__file__).resolve().parents[2]
_RESULTS_DIR = _ROOT / "experiment" / "results" / "output"

PROBLEM_REGISTRY = {
    "Exp1Problem":      "experiment.core.exp1_problem.Exp1Problem",
    "Exp2Problem":      "experiment.core.exp2_problem.Exp2Problem",
    "DailyExp1Problem": "experiment.core.daily_exp1_problem.DailyExp1Problem",
    "DailyExp2Problem": "experiment.core.daily_exp2_problem.DailyExp2Problem",
}


@dataclass
class RunResult:
    run_id: int
    seed: int
    experiment_id: str
    algorithm: str
    nutrition_label: str
    pareto_F: np.ndarray          # shape (n_sol, n_obj)
    pareto_X: np.ndarray          # shape (n_sol, 4)
    n_evals: int
    n_gen: int
    elapsed_sec: float
    best: dict = field(default_factory=dict)   # 칼로리 오차 최소 해


def _load_problem_class(class_name: str):
    module_path, cls_name = PROBLEM_REGISTRY[class_name].rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


def _run_once(problem, algorithm, n_gen: int, seed: int, run_id: int,
              experiment_id: str, algo_name: str, nutrition_label: str) -> RunResult:
    """단일 NSGA-II 실행."""
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination

    termination = get_termination("n_gen", n_gen)

    t0 = time.perf_counter()
    res = minimize(problem, algorithm, termination, seed=seed, verbose=False)
    elapsed = time.perf_counter() - t0

    # 실행 가능한 해만 추출 (g1 <= 0)
    n_var = problem.n_var
    if res is None or res.F is None or len(res.F) == 0:
        pareto_F = np.empty((0, problem.n_obj))
        pareto_X = np.empty((0, n_var))
    else:
        if res.G is not None:
            feasible_mask = np.all(res.G <= 0, axis=1)
            pareto_F = res.F[feasible_mask]
            pareto_X = res.X[feasible_mask]
        else:
            pareto_F = res.F
            pareto_X = res.X

    n_evals = res.algorithm.evaluator.n_eval if res and res.algorithm else 0
    n_gen_actual = res.algorithm.n_gen if res and res.algorithm else n_gen

    # 최적 해: f1(칼로리 오차) 최소 → 동률 시 마지막 목적함수(가격) 최소
    best = {}
    if len(pareto_F) > 0:
        best_idx = int(np.argmin(pareto_F[:, 0]))
        best_x = pareto_X[best_idx].astype(int)
        best_combo = problem.decode(best_x)
        best_t = problem.totals(best_combo)

        best = {
            "f_values": pareto_F[best_idx].tolist(),
            "x": best_x.tolist(),
            "calories": best_t["calories"],
            "protein": best_t["protein"],
            "carbs": best_t["carbs"],
            "fat": best_t["fat"],
            "price": best_t["price"],
        }

        # 일일 문제: 끼니별 첫 주메뉴 표시
        if hasattr(problem, "decode_meals"):
            meals = problem.decode_meals(best_x)
            best["main"] = " | ".join(
                meal[0].get("product_name", meal[0].get("menu_name", ""))
                for meal in meals
            )
            best["n_meals"] = problem.n_meals
            best["avg_price"] = best_t["price"] / problem.n_meals
        else:
            best["main"] = best_combo[0].get("product_name", best_combo[0].get("menu_name", ""))

    return RunResult(
        run_id=run_id,
        seed=seed,
        experiment_id=experiment_id,
        algorithm=algo_name,
        nutrition_label=nutrition_label,
        pareto_F=pareto_F,
        pareto_X=pareto_X,
        n_evals=n_evals,
        n_gen=n_gen_actual,
        elapsed_sec=elapsed,
        best=best,
    )


def run_experiment(
    config_path: str,
    cal_star: float,
    price_star: float,
    allergens: list[str] | None = None,
    test_mode: bool = False,
) -> list[RunResult]:
    """30회 반복 실험 실행.

    Args:
        config_path:  YAML 설정 파일 경로
        cal_star:     목표 칼로리 (kcal)
        price_star:   목표 가격 (원)
        allergens:    회피할 알레르겐 목록 (None이면 필터링 없음)
        test_mode:    True이면 pop=10, gen=5, n_runs=2로 빠른 검증
    """
    from experiment.core.loader import FoodDataLoader
    from experiment.core.metrics import compute_indicators, compute_reference_pf
    from experiment.algorithms.factory import get_algorithm
    from experiment.core.nutrition import NutritionProfile

    # ── 설정 로딩 ──────────────────────────────────────────────
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    experiment_id = cfg["experiment_id"]
    algo_name = cfg["algorithm"]["name"]
    algo_cfg = cfg["algorithm"].copy()
    n_gen = algo_cfg.pop("n_gen", 200)
    n_runs = cfg["runner"]["n_runs"]
    seed_start = cfg["runner"]["seed_start"]

    profile = NutritionProfile.from_dict(cfg["problem"]["nutrition_profile"])
    problem_class_name = cfg["problem"]["class"]

    if test_mode:
        algo_cfg["pop_size"] = 10
        n_gen = 5
        n_runs = 2
        print("⚡ [TEST MODE] pop=10, gen=5, n_runs=2")

    # ── 데이터 로딩 ────────────────────────────────────────────
    loader = FoodDataLoader.from_supabase()
    cats = loader.get_category_lists(allergens_to_avoid=allergens)
    mains = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks = cats["DRINK"]
    snacks = cats.get("SNACK", [])

    print(f"  MAIN: {len(mains)}, SIDE_SOUP: {len(sides_soup)}, "
          f"DRINK: {len(drinks)}, SNACK: {len(snacks)}")

    if not mains:
        raise ValueError("MAIN 카테고리가 비어 있습니다.")

    # ── Problem 인스턴스화 ──────────────────────────────────────
    ProblemCls = _load_problem_class(problem_class_name)
    is_daily = problem_class_name.startswith("Daily")

    if is_daily:
        n_meals = cfg["problem"].get("n_meals", 3)
        include_snack = cfg["problem"].get("include_snack", False)
        problem = ProblemCls(
            mains=mains,
            sides_soup=sides_soup,
            drinks=drinks,
            snacks=snacks,
            n_meals=n_meals,
            include_snack=include_snack,
            cal_star=cal_star,
            price_per_meal_star=price_star,
            profile=profile,
        )
    else:
        problem = ProblemCls(
            mains=mains,
            sides_soup=sides_soup,
            drinks=drinks,
            cal_star=cal_star,
            price_star=price_star,
            profile=profile,
        )

    # ── 30회 반복 실행 ─────────────────────────────────────────
    results: list[RunResult] = []
    price_label = f"{price_star:,}원/끼니" if is_daily else f"{price_star:,}원"
    print(f"\n🚀 [{experiment_id}] {algo_name} × {n_runs}회 실험 시작")
    print(f"   NutritionProfile: {profile.label} | Cal*: {cal_star} | Price*: {price_label}")
    if is_daily:
        snack_label = f" + 간식" if include_snack else ""
        print(f"   식사 구성: {n_meals}끼{snack_label} (자유 배분) | n_var={problem.n_var}")
    print("-" * 60)

    for run_id in range(n_runs):
        seed = seed_start + run_id
        algo = get_algorithm(algo_name, algo_cfg)
        result = _run_once(
            problem, algo, n_gen, seed, run_id,
            experiment_id, algo_name, profile.label
        )
        results.append(result)
        n_sol = len(result.pareto_F)
        print(f"  Run {run_id + 1:2d}/{n_runs} | seed={seed} | "
              f"Pareto={n_sol}해 | {result.elapsed_sec:.1f}s")

    # ── 기준 PF 계산 ───────────────────────────────────────────
    all_F_list = [r.pareto_F for r in results if len(r.pareto_F) > 0]
    if not all_F_list:
        print("⚠️ 모든 실행에서 실행 가능한 해 없음. 지표 계산 불가.")
        return results

    all_F = np.vstack(all_F_list)
    ref_pf = compute_reference_pf(all_F)
    # ref_point = 전체 해(all_F)의 nadir × 1.1
    # ref_pf(최고 성능 해만)의 max를 쓰면 개별 run 해들이 ref_point를 초과해 HV=0이 됨
    ref_point = np.max(all_F, axis=0) * 1.1
    print(f"\n📐 기준 PF 크기: {len(ref_pf)}해")

    # ── 지표 계산 ──────────────────────────────────────────────
    indicators_list: list[dict] = []
    for r in results:
        if len(r.pareto_F) == 0:
            inds = {k: float("nan") for k in
                    ["GD", "IGD", "IGD+", "GD+", "HV", "Spread", "Epsilon"]}
        else:
            inds = compute_indicators(r.pareto_F, ref_pf, ref_point)
        indicators_list.append(inds)

    # ── 결과 저장 ──────────────────────────────────────────────
    _save_results(results, indicators_list, ref_pf, cfg, config_path)

    # ── 요약 출력 ──────────────────────────────────────────────
    _print_summary(results, indicators_list)

    return results


def _save_results(
    results: list[RunResult],
    indicators_list: list[dict],
    ref_pf: np.ndarray,
    cfg: dict,
    config_path: str,
) -> Path:
    """결과를 CSV + 설정 스냅샷으로 저장."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _RESULTS_DIR / f"{cfg['experiment_id']}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # runs_summary.csv
    summary_path = out_dir / "runs_summary.csv"
    indicator_keys = ["GD", "IGD", "IGD+", "GD+", "HV", "Spread", "Epsilon"]
    fieldnames = (
        ["run_id", "seed", "n_evals", "n_gen", "elapsed_sec", "n_pareto"]
        + indicator_keys
        + ["best_f1", "best_price", "best_main"]
    )
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r, inds in zip(results, indicators_list):
            row = {
                "run_id": r.run_id,
                "seed": r.seed,
                "n_evals": r.n_evals,
                "n_gen": r.n_gen,
                "elapsed_sec": f"{r.elapsed_sec:.3f}",
                "n_pareto": len(r.pareto_F),
            }
            for k in indicator_keys:
                row[k] = f"{inds.get(k, float('nan')):.6f}"
            row["best_f1"] = f"{r.best.get('f_values', [float('nan')])[0]:.6f}" if r.best else "nan"
            row["best_price"] = r.best.get("price", "") if r.best else ""
            row["best_main"] = r.best.get("main", "") if r.best else ""
            writer.writerow(row)

    # ref_pareto_front.csv
    ref_path = out_dir / "ref_pareto_front.csv"
    n_obj = ref_pf.shape[1]
    with open(ref_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([f"f{i+1}" for i in range(n_obj)])
        writer.writerows(ref_pf.tolist())

    # run_NN_pareto.csv
    for r in results:
        run_path = out_dir / f"run_{r.run_id:02d}_pareto.csv"
        with open(run_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            n_obj = r.pareto_F.shape[1] if len(r.pareto_F) > 0 else 0
            n_xvar = r.pareto_X.shape[1] if len(r.pareto_X) > 0 else 0
            header = [f"f{i+1}" for i in range(n_obj)] + [f"x{i}" for i in range(n_xvar)]
            writer.writerow(header)
            for fv, xv in zip(r.pareto_F, r.pareto_X):
                writer.writerow(list(fv) + list(xv))

    # config_snapshot.yaml
    shutil.copy(config_path, out_dir / "config_snapshot.yaml")

    print(f"\n💾 결과 저장 완료: {out_dir}")
    return out_dir


def _print_summary(results: list[RunResult], indicators_list: list[dict]) -> None:
    keys = ["GD", "IGD", "HV", "Spread"]
    print("\n📊 실험 결과 요약 (평균 ± 표준편차)")
    print("-" * 50)
    for k in keys:
        vals = [inds[k] for inds in indicators_list if not np.isnan(inds.get(k, float("nan")))]
        if vals:
            print(f"  {k:8s}: {np.mean(vals):.4f} ± {np.std(vals):.4f}")
    elapsed = [r.elapsed_sec for r in results]
    print(f"  {'Time':8s}: {np.mean(elapsed):.1f}s ± {np.std(elapsed):.1f}s")
    n_pareto = [len(r.pareto_F) for r in results]
    print(f"  {'|PF|':8s}: {np.mean(n_pareto):.1f} ± {np.std(n_pareto):.1f}")
