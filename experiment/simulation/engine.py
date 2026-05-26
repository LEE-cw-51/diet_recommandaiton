"""최적화 실행 엔진 — 단일 실행·KG 초기화·스냅샷 수집.

run_simulation_* 스크립트가 공통으로 쓰는 실행 로직을 한 곳에 모았다.
재현성 상수·참조점은 experiment.models.variants 에서 가져온다.
"""

from __future__ import annotations

import time

import numpy as np
from pymoo.core.callback import Callback

from experiment.models.variants import (
    HV_SAMPLE_EVERY,
    KG_HISTORY,
    KG_PREFERENCES,
    TEST_USER,
)


class FSnapshotCallback(Callback):
    """4D HV는 O(n^3) — 매 세대 계산은 매우 느리므로 F만 수집하고 후처리한다."""

    def __init__(self, sample_every: int = HV_SAMPLE_EVERY):
        super().__init__()
        self.data["snapshots"] = []   # [(gen: int, F: ndarray), ...]
        self._sample_every = sample_every

    def notify(self, algorithm) -> None:
        if algorithm.n_gen % self._sample_every == 0:
            F = algorithm.pop.get("F")
            if F is not None and len(F) > 0:
                self.data["snapshots"].append((int(algorithm.n_gen), F.copy()))


def run_once(
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
    cb = FSnapshotCallback()

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


def build_kg(all_foods: list[dict]):
    """고정 테스트 유저 KG 초기화 (재현 가능 조건).

    variants.KG_PREFERENCES / KG_HISTORY 를 사용해 사전 선호·섭취 이력을 세팅.
    """
    from experiment.core.kg_manager import KGManager

    kg_cfg = {
        "user_id":      TEST_USER,
        "preferences":  KG_PREFERENCES,
        "user_history": KG_HISTORY,
    }
    return KGManager.from_config(all_foods, kg_cfg, user_id=TEST_USER)
