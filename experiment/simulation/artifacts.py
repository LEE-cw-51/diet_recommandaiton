"""아티팩트 계약 — 계산 결과를 디스크에 저장하고 시각화가 로드한다.

목적: 시각화가 최적화를 **재실행하지 않도록**, 그래프 생성에 필요한 raw 데이터를
      한 번의 시뮬레이션에서 모두 저장한다.

저장 형식:
  results/<scenario>/artifacts.npz   — 단일 키 'payload' 에 중첩 dict (pickle).
    payload = {
        "groups":      {G: {"F_list":[ndarray...], "times":[...], "snapshots_all":[[(gen,F)...]...]}},
        "nadir_map":   {G: ndarray},
        "pareto":      {"G1":pf, "G2":pf, "G3":pf, "ref": ref_front},  # Loop A 30회에서 머지
        "daily_logs":  [...],   # Loop B 일별 로그(raw). 상세 구조는 run_step1 생성 스키마를 따른다.
        "meta":        {"n_gen":..., "pop_size":..., "n_runs":..., "n_days":...},
    }

  참고:
    - `kg_eaten`는 artifacts payload의 계약 키가 아니다.
    - KG 상태 재구성용 섭취 시퀀스가 필요하면 step2에서 별도 `kg_eaten_sequence.json`을 사용한다.

  CSV(metrics_comparison / per_run_metrics / daily_*)는 별도로 저장된다(사람이 읽고 논문 표에 사용).
  npz는 시각화 재현 전용.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

_ARTIFACT_NAME = "artifacts.npz"

# 신뢰 경로: 이 디렉토리 아래의 artifacts.npz 만 기본적으로 로드 허용.
# (save_artifacts 가 결과를 저장하는 유일한 위치)
_TRUSTED_RESULTS_ROOT = (_PROJECT_ROOT / "experiment" / "results").resolve()


def save_artifacts(out_dir: Path, payload: dict) -> Path:
    """payload(중첩 dict)를 out_dir/artifacts.npz 에 저장."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / _ARTIFACT_NAME
    np.savez(path, payload=np.array(payload, dtype=object))
    print(f"  💾 {path.name}")
    return path


def _is_trusted_path(path: Path) -> bool:
    """path 가 신뢰 결과 디렉토리(_TRUSTED_RESULTS_ROOT) 하위인지 검사."""
    try:
        path.resolve().relative_to(_TRUSTED_RESULTS_ROOT)
        return True
    except ValueError:
        return False


def load_artifacts(out_dir: Path, *, trust: bool = False) -> dict:
    """out_dir/artifacts.npz → payload dict 복원.

    보안 주의: 이 함수는 `allow_pickle=True`로 npz를 역직렬화하므로, 신뢰할 수 없는
    파일을 읽으면 임의 코드 실행 위험이 있다. 따라서 기본적으로 **프로젝트 결과
    디렉토리(`experiment/results/`) 하위 파일만** 로드를 허용한다. 그 밖의 경로는
    명시적으로 신뢰를 표시해야 한다:
      - `load_artifacts(path, trust=True)` 인자, 또는
      - 환경변수 `DIET_TRUST_ARTIFACTS=1`
    외부에서 내려받은/공유된 artifacts.npz 는 신뢰하지 말 것.
    """
    path = Path(out_dir) / _ARTIFACT_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"아티팩트 없음: {path}\n"
            f"  먼저 시뮬레이션을 실행하세요 (예: python -X utf8 -m experiment.simulation.run_step1)."
        )

    trusted = trust or os.environ.get("DIET_TRUST_ARTIFACTS") == "1" or _is_trusted_path(path)
    if not trusted:
        raise PermissionError(
            f"신뢰되지 않은 경로의 artifacts 로드 차단: {path}\n"
            f"  이 파일은 pickle 기반(allow_pickle=True)이라 임의 코드 실행 위험이 있습니다.\n"
            f"  신뢰 위치는 {_TRUSTED_RESULTS_ROOT} 하위입니다.\n"
            f"  직접 생성/검증한 파일이라면 load_artifacts(..., trust=True) 또는 "
            f"환경변수 DIET_TRUST_ARTIFACTS=1 로 허용하세요."
        )

    # allow_pickle=True: 위 가드를 통과한 신뢰 파일만 대상으로 한다.
    data = np.load(path, allow_pickle=True)
    return data["payload"].item()


def has_artifacts(out_dir: Path) -> bool:
    return (Path(out_dir) / _ARTIFACT_NAME).exists()


def build_pareto_payload(groups: dict) -> dict:
    """Loop A의 그룹별 per-run F를 머지해 그룹별 Pareto front를 산출.

    plot_pareto 가 최적화를 재실행하지 않도록, 이미 수행한 30회 실행 결과를 재사용한다.
    G1/G2는 3목적, G3는 4목적이므로 차원이 다름 — 그룹별로 분리 저장.
    """
    from experiment.core.metrics import compute_reference_pf

    pareto: dict = {}
    for g in ("G1", "G2", "G3"):
        f_list = [F for F in groups.get(g, {}).get("F_list", []) if len(F) > 0]
        if f_list:
            merged = np.vstack(f_list)
            pareto[g] = compute_reference_pf(merged)
        else:
            n_obj = 4 if g == "G3" else 3
            pareto[g] = np.empty((0, n_obj))

    # Reference front: G3 4D 단독 (차원이 다른 G1/G2와 머지 불가)
    pareto["ref"] = (
        compute_reference_pf(pareto["G3"]) if len(pareto["G3"]) > 0
        else np.empty((0, 4))
    )
    return pareto
