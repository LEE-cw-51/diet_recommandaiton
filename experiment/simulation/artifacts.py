"""아티팩트 계약 — 계산 결과를 디스크에 저장하고 시각화가 로드한다.

목적: 시각화가 최적화를 **재실행하지 않도록**, 그래프 생성에 필요한 raw 데이터를
      한 번의 시뮬레이션에서 모두 저장한다.

저장 형식:
  results/<scenario>/artifacts.npz   — 단일 키 'payload' 에 중첩 dict (pickle).
    payload = {
        "groups":     {G: {"F_list":[ndarray...], "times":[...], "snapshots_all":[[(gen,F)...]...]}},
        "nadir_map":  {G: ndarray},
        "pareto":     {"G1":pf, "G2":pf, "G3":pf, "ref": ref_front},  # Loop A 30회에서 머지
        "kg_eaten":   {day: [menu_id, ...]},   # Loop B 일별 섭취 (KG 상태 재구성용, optional)
        "meta":       {"n_gen":..., "pop_size":..., "n_runs":..., "n_days":...},
    }

  CSV(metrics_comparison / per_run_metrics / daily_*)는 별도로 저장된다(사람이 읽고 논문 표에 사용).
  npz는 시각화 재현 전용.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_ARTIFACT_NAME = "artifacts.npz"


def save_artifacts(out_dir: Path, payload: dict) -> Path:
    """payload(중첩 dict)를 out_dir/artifacts.npz 에 저장."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / _ARTIFACT_NAME
    np.savez(path, payload=np.array(payload, dtype=object))
    print(f"  💾 {path.name}")
    return path


def load_artifacts(out_dir: Path) -> dict:
    """out_dir/artifacts.npz → payload dict 복원."""
    path = Path(out_dir) / _ARTIFACT_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"아티팩트 없음: {path}\n"
            f"  먼저 시뮬레이션을 실행하세요 (예: python -X utf8 -m experiment.simulation.run_step1)."
        )
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
