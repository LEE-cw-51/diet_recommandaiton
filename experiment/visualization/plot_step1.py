"""Step1 시각화 — 저장된 아티팩트만 로드해 그래프 생성 (최적화 재실행 없음).

생성 그래프 (results/step1/):
  plot_convergence.png       세대별 HV 수렴 곡선 (30회 평균 ± std)
  plot_metrics_boxplot.png   G1/G2/G3 × HV/GD+/IGD+ 박스플롯 (유의성 브래킷)
  plot_metrics_bar.png       지표 평균 ± std 바 차트
  plot_7days_f4.png          G3 7일 f4 추이 (Loop B)

데이터 출처: experiment/results/step1/artifacts.npz (run_step1 이 저장).
plot 함수들은 데이터 인자를 직접 받으므로 run_step2_cuisine 등에서도 재사용된다.

사용법:
  python -X utf8 -m experiment.visualization.plot_step1
  python -X utf8 -m experiment.visualization.plot_step1 --dir experiment/results/step1
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
    print("⚠ matplotlib 미설치 — PNG 그래프 생략 (pip install matplotlib)")

from experiment.models.variants import (  # noqa: E402
    GROUP_COLORS as _GROUP_COLORS,
    GROUP_LABELS as _GROUP_LABELS,
    HV_SAMPLE_EVERY,
)
from experiment.simulation.artifacts import load_artifacts  # noqa: E402

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step1"


# ──────────────────────────────────────────────────────────────────────────────
# 수렴 곡선
# ──────────────────────────────────────────────────────────────────────────────

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
# 지표 비교 (박스플롯 + 바 차트)
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
# 아티팩트 로드 → 전체 렌더
# ──────────────────────────────────────────────────────────────────────────────

def render_from_dir(out_dir: Path) -> None:
    """results 디렉토리의 artifacts.npz 를 로드해 step1 그래프 전체 생성.

    최적화를 재실행하지 않는다 — 저장된 raw 데이터만 사용.
    """
    if not HAS_MPL:
        print("⚠ matplotlib 없음 — 그래프 생략")
        return

    out_dir = Path(out_dir)
    payload = load_artifacts(out_dir)

    groups    = payload["groups"]
    nadir_map = payload["nadir_map"]
    metrics   = payload["metrics"]
    p_vals    = payload["p_vals"]
    daily_logs = payload.get("daily_logs", [])
    n_gen     = payload["meta"]["n_gen"]

    plot_convergence(out_dir, groups, nadir_map, n_gen)
    plot_metrics_boxplot(out_dir, metrics, p_vals)
    plot_metrics_bar(out_dir, metrics, p_vals)
    if daily_logs:
        plot_7days_f4(out_dir, daily_logs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step1 시각화 (저장된 아티팩트 로드 — 최적화 재실행 없음)")
    parser.add_argument("--dir", default=str(_OUT_DIR),
                        help="아티팩트 디렉토리 (기본: experiment/results/step1). "
                             "experiment/results/ 밖 경로는 pickle 보안 가드로 차단됨 "
                             "— 외부 경로는 DIET_TRUST_ARTIFACTS=1 환경변수로 허용.")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    print(f"\n🖼  Step1 시각화 — {out_dir}")
    render_from_dir(out_dir)
    print(f"\n✅ 완료! → {out_dir}")


if __name__ == "__main__":
    main()
