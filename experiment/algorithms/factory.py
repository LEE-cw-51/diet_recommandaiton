"""알고리즘 팩토리 — register 데코레이터 패턴.

알고리즘 추가 방법:
  1. @register("MOEAD") 데코레이터로 빌더 함수 등록
  2. YAML config의 algorithm.name을 "MOEAD"로 변경
  3. Problem, metrics, runner 변경 없음

현재 등록된 알고리즘: NSGA2
"""

from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(name: str):
    """알고리즘 빌더 함수를 레지스트리에 등록하는 데코레이터."""
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name.upper()] = fn
        return fn
    return decorator


def get_algorithm(name: str, cfg: dict):
    """등록된 알고리즘 인스턴스를 반환."""
    key = name.upper()
    if key not in _REGISTRY:
        raise ValueError(
            f"알 수 없는 알고리즘: '{name}'. "
            f"등록된 알고리즘: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[key](cfg)


def list_algorithms() -> list[str]:
    return list(_REGISTRY.keys())


# ------------------------------------------------------------------
# NSGA-II
# ------------------------------------------------------------------

@register("NSGA2")
def _build_nsga2(cfg: dict):
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.operators.crossover.pntx import PointCrossover
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import IntegerRandomSampling

    crossover_cfg = cfg.get("crossover", {})
    mutation_cfg = cfg.get("mutation", {})

    return NSGA2(
        pop_size=cfg["pop_size"],
        sampling=IntegerRandomSampling(),
        crossover=PointCrossover(
            n_points=crossover_cfg.get("n_points", 2),
            prob=crossover_cfg.get("prob", 0.9),
        ),
        mutation=PM(
            prob=mutation_cfg.get("prob", 0.1),
            eta=mutation_cfg.get("eta", 20),
        ),
        eliminate_duplicates=cfg.get("eliminate_duplicates", True),
    )


# ------------------------------------------------------------------
# 미래 확장 예시 (주석 해제 후 사용)
# ------------------------------------------------------------------

# @register("MOEAD")
# def _build_moeaD(cfg: dict):
#     from pymoo.algorithms.moo.moead import MOEAD
#     from pymoo.operators.sampling.rnd import IntegerRandomSampling
#     from pymoo.util.ref_dirs import get_reference_directions
#     ref_dirs = get_reference_directions("das-dennis", cfg.get("n_obj", 2),
#                                         n_partitions=cfg.get("n_partitions", 12))
#     return MOEAD(ref_dirs, n_neighbors=cfg.get("n_neighbors", 15),
#                  sampling=IntegerRandomSampling())


# @register("SPEA2")
# def _build_spea2(cfg: dict):
#     from pymoo.algorithms.moo.spea2 import SPEA2
#     from pymoo.operators.crossover.pntx import PointCrossover
#     from pymoo.operators.mutation.pm import PM
#     from pymoo.operators.sampling.rnd import IntegerRandomSampling
#     return SPEA2(
#         pop_size=cfg["pop_size"],
#         sampling=IntegerRandomSampling(),
#         crossover=PointCrossover(prob=cfg.get("crossover", {}).get("prob", 0.9)),
#         mutation=PM(prob=cfg.get("mutation", {}).get("prob", 0.1)),
#     )
