"""품질 지표 계산 모듈.

pymoo 제공 지표: GD, IGD, IGD+, GD+, HV, Epsilon
수동 구현: Spread (Deb 2002 Delta metric)

모든 함수는 numpy ndarray를 입력으로 받음.
pareto_F: shape (n_solutions, n_obj) — 해당 run의 Pareto front
ref_pf:   shape (m, n_obj)           — 기준 Pareto front (30회 합집합 비지배 해)
"""

from __future__ import annotations

import numpy as np


def compute_indicators(
    pareto_F: np.ndarray,
    ref_pf: np.ndarray,
    ref_point: np.ndarray | None = None,
) -> dict[str, float]:
    """모든 품질 지표 계산.

    Args:
        pareto_F:   한 run의 Pareto front (n_sol × n_obj)
        ref_pf:     기준 Pareto front (30회 합집합 비지배 해)
        ref_point:  HV 계산용 reference point (None이면 ref_pf 기준 자동 설정)

    Returns:
        dict: GD, IGD, IGD+, GD+, HV, Spread, Epsilon
    """
    from pymoo.indicators.gd import GD
    from pymoo.indicators.igd import IGD
    from pymoo.indicators.igd_plus import IGDPlus
    from pymoo.indicators.gd_plus import GDPlus
    from pymoo.indicators.hv import HV

    if ref_point is None:
        ref_point = np.max(ref_pf, axis=0) * 1.1

    results: dict[str, float] = {}

    try:
        results["GD"] = float(GD(ref_pf)(pareto_F))
    except Exception:
        results["GD"] = float("nan")

    try:
        results["IGD"] = float(IGD(ref_pf)(pareto_F))
    except Exception:
        results["IGD"] = float("nan")

    try:
        results["IGD+"] = float(IGDPlus(ref_pf)(pareto_F))
    except Exception:
        results["IGD+"] = float("nan")

    try:
        results["GD+"] = float(GDPlus(ref_pf)(pareto_F))
    except Exception:
        results["GD+"] = float("nan")

    try:
        results["HV"] = float(HV(ref_point=ref_point)(pareto_F))
    except Exception:
        results["HV"] = float("nan")

    try:
        results["Spread"] = float(_spread(pareto_F))
    except Exception:
        results["Spread"] = float("nan")

    try:
        results["Epsilon"] = float(_epsilon(pareto_F, ref_pf))
    except Exception:
        results["Epsilon"] = float("nan")

    return results


def compute_reference_pf(all_F: np.ndarray) -> np.ndarray:
    """30회 실행의 Pareto front 합집합에서 비지배 해집합 추출.

    실제 PF를 알 수 없을 때의 표준 근사 방법 (CEC/BBOB 방식).
    """
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    nds = NonDominatedSorting()
    fronts = nds.do(all_F, only_non_dominated_front=True)
    return all_F[fronts]


def _spread(F: np.ndarray) -> float:
    """Spread (Delta) 지표 — Deb et al. (2002).

    해집단의 분포 균일성 측정. 0에 가까울수록 좋음.

    Δ = (d_f + d_l + Σ|d_i - d̄|) / (d_f + d_l + (n-1)·d̄)
      d_i: 연속 해 간 유클리드 거리
      d_f: 첫 해 ↔ 이상 extreme 해 거리
      d_l: 마지막 해 ↔ 이상 extreme 해 거리
    """
    if len(F) < 2:
        return 0.0

    # 첫 번째 목적함수 기준으로 정렬
    sorted_F = F[np.argsort(F[:, 0])]

    # 연속 해 간 거리
    dists = np.linalg.norm(np.diff(sorted_F, axis=0), axis=1)
    d_mean = np.mean(dists)

    if d_mean == 0:
        return 0.0

    # extreme 해: 각 목적함수 최솟값 지점
    extreme_min = np.min(F, axis=0)
    extreme_max = np.max(F, axis=0)

    d_f = float(np.linalg.norm(sorted_F[0] - extreme_min))
    d_l = float(np.linalg.norm(sorted_F[-1] - extreme_max))

    numerator = d_f + d_l + np.sum(np.abs(dists - d_mean))
    denominator = d_f + d_l + (len(dists)) * d_mean

    return float(numerator / denominator) if denominator > 0 else 0.0


def _epsilon(F: np.ndarray, ref_pf: np.ndarray) -> float:
    """Epsilon (ε) 지표 — 최소 ε: F가 ref_pf를 ε만큼 이동하면 지배 가능.

    ε = max_{z* ∈ ref_pf} min_{z ∈ F} max_i(z_i / z*_i)
    낮을수록 좋음 (1에 가까울수록 F ≈ ref_pf).
    """
    epsilon_vals = []
    for ref_point in ref_pf:
        min_ratio = np.inf
        for sol in F:
            # 0 나누기 방지
            ref_safe = np.where(np.abs(ref_point) < 1e-10, 1e-10, ref_point)
            ratio = np.max(sol / ref_safe)
            if ratio < min_ratio:
                min_ratio = ratio
        epsilon_vals.append(min_ratio)
    return float(np.max(epsilon_vals)) if epsilon_vals else float("nan")
