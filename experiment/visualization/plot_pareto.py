"""G1/G2/G3 Pareto Front 2D 투영 시각화 — 저장된 PF 로드 (재실행 없음).

run_step1 이 Loop A 30회 실행 결과에서 그룹별 머지 Pareto Front를 계산해
artifacts.npz(payload["pareto"])에 저장한다. 이 스크립트는 그 PF만 로드해 그린다.
(과거에는 시각화를 위해 NSGA-II/R-NSGA-II를 5회 재실행했으나, 결합을 제거함.)

목적함수 차원:
  G1, G2: 3목적 (f1, f2, f3)        → f4 관련 페어에는 마커 표시 안 됨
  G3:     4목적 (f1, f2, f3, f4)    → 6개 페어 모두 표시

2×3 subplot — C(4,2)=6쌍:
  (f1,f2) (f1,f3) (f1,f4) (f2,f3) (f2,f4) (f3,f4)

사용법:
  python -X utf8 -m experiment.visualization.plot_pareto
  python -X utf8 -m experiment.visualization.plot_pareto --dir experiment/results/step1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("⚠ matplotlib 미설치 — pip install matplotlib")

from experiment.simulation.artifacts import load_artifacts  # noqa: E402

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1"


def plot_pareto_scatter(
    g1_pf: np.ndarray,
    g2_pf: np.ndarray,
    g3_pf: np.ndarray,
    ref_front: np.ndarray,
    out_dir: Path,
) -> None:
    """G1/G2/G3 Pareto Front 2D 투영 — 2×3 subplot (C(4,2)=6쌍)."""
    if not HAS_MPL:
        print("⚠ matplotlib 없음 — 그래프 생략")
        return

    # 목적함수 인덱스 (0-based) — 4목적 전체 조합 C(4,2)=6
    PAIRS = [
        (0, 1, "f1 (Calorie Error)",  "f2 (Macro Ratio Error)"),
        (0, 2, "f1 (Calorie Error)",  "f3 (Price Error)"),
        (0, 3, "f1 (Calorie Error)",  "f4 (KG Error Rate)"),
        (1, 2, "f2 (Macro Ratio Error)", "f3 (Price Error)"),
        (1, 3, "f2 (Macro Ratio Error)", "f4 (KG Error Rate)"),
        (2, 3, "f3 (Price Error)",    "f4 (KG Error Rate)"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()
    fig.suptitle("Pareto Front Projection: G1 vs G2 vs G3 (All 6 Pairs)", fontsize=13)

    styles = {
        "G1 (NSGA-II, 3-obj)":      (g1_pf,    "gray",   "x",  60, 0.7),
        "G2 (R-NSGA-II, 3-obj)":    (g2_pf,    "#4477AA","^",  50, 0.75),
        "G3 (R-NSGA-II + KG, 4-obj)":(g3_pf,   "#EE6677","o",  55, 0.85),
        "Reference Front (4D from G3)":(ref_front, "black",  "*",  80, 1.0),
    }

    for ax, (xi, yi, xlabel, ylabel) in zip(axes, PAIRS):
        for label, (pf, color, marker, size, alpha) in styles.items():
            if len(pf) == 0:
                continue
            # 그룹의 PF 차원이 인덱스(xi, yi)를 커버하지 못하면 누락 (G1/G2의 f4 페어)
            if pf.shape[1] <= max(xi, yi):
                continue
            ax.scatter(
                pf[:, xi], pf[:, yi],
                label=label, color=color, marker=marker,
                s=size, alpha=alpha, linewidths=0.8,
            )
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.4)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="lower center", ncol=4,
        fontsize=9, bbox_to_anchor=(0.5, -0.08),
        frameon=True,
    )

    plt.tight_layout()
    out_path = out_dir / "plot_pareto_scatter.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  🖼  plot_pareto_scatter.png")


def render_from_dir(out_dir: Path) -> None:
    """artifacts.npz(payload['pareto'])를 로드해 Pareto scatter 생성."""
    out_dir = Path(out_dir)
    payload = load_artifacts(out_dir)
    pareto = payload.get("pareto")
    if not pareto:
        print("⚠ 아티팩트에 'pareto' 없음 — run_step1 을 최신 버전으로 재실행하세요.")
        return

    g1_pf = pareto.get("G1", np.empty((0, 3)))
    g2_pf = pareto.get("G2", np.empty((0, 3)))
    g3_pf = pareto.get("G3", np.empty((0, 4)))
    ref_front = pareto.get("ref", np.empty((0, 4)))
    print(f"  로드: G1={len(g1_pf)}해  G2={len(g2_pf)}해  "
          f"G3={len(g3_pf)}해  ref={len(ref_front)}해")

    plot_pareto_scatter(g1_pf, g2_pf, g3_pf, ref_front, out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="G1/G2/G3 Pareto Front 시각화 (저장된 PF 로드 — 재실행 없음)")
    parser.add_argument("--dir", default=str(_OUT_DIR),
                        help="아티팩트 디렉토리 (기본: experiment/results/step1). "
                             "experiment/results/ 밖 경로는 pickle 보안 가드로 차단됨 "
                             "— 외부 경로는 DIET_TRUST_ARTIFACTS=1 환경변수로 허용.")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    print(f"\n🖼  Pareto Front 시각화 — {out_dir}")
    render_from_dir(out_dir)
    print(f"\n✅ 완료! → {out_dir}")


if __name__ == "__main__":
    main()
