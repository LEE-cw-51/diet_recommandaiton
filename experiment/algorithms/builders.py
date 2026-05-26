"""알고리즘 빌더 — pymoo NSGA-II / R-NSGA-II 인스턴스 생성.

시뮬레이션 코드 전반에서 동일한 연산자 설정(교차/변이/샘플링)을 쓰도록
한 곳에 모았다. YAML 기반 생성은 algorithms.factory를 사용.
"""

from __future__ import annotations

import numpy as np


def make_nsga2(pop_size: int):
    """NSGA-II (vanilla) — 고정 연산자 설정."""
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


def make_rnsga2(pop_size: int, ref_points: np.ndarray):
    """R-NSGA-II — 참조점 기반. ref_points는 2D ndarray (n_ref × n_obj)."""
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
