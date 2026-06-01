"""논문용 그림 일괄 생성 스크립트.

원칙:
  - 모든 레이블·제목·범례: 영어
  - 범례는 그래프 밖에 위치 (bbox_to_anchor)
  - 수식은 matplotlib 렌더링 후 PNG 저장
  - 300 DPI, colorblind-safe palette
  - 기존 visualization/*.py 미수정

출력 위치: experiment/results/paper_figures/

사용법:
  python -X utf8 -m experiment.visualization.paper_figures --sample   # fig1만 생성
  python -X utf8 -m experiment.visualization.paper_figures --sec1     # Sec 1 그림만 생성
  python -X utf8 -m experiment.visualization.paper_figures --sec2     # Sec 2 그림만 생성
  python -X utf8 -m experiment.visualization.paper_figures --sec3     # Sec 3 그림만 생성
  python -X utf8 -m experiment.visualization.paper_figures --all      # 전체 생성
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from experiment import _PROJECT_ROOT

_RESULTS = _PROJECT_ROOT / "experiment" / "results"
_OUT = _RESULTS / "paper_figures"

# ── 공통 스타일 ────────────────────────────────────────────────────────────────
# matplotlib tab10 기본 팔레트 — 최적화 논문에서 가장 널리 쓰이는 표준 배색

COLORS = {
    "G1":     "#1f77b4",  # tab:blue
    "G2":     "#ff7f0e",  # tab:orange
    "G3":     "#2ca02c",  # tab:green
    "before": "#d62728",  # tab:red
    "after":  "#1f77b4",  # tab:blue
}

CUISINE_COLORS = {
    "Korean":   "#1f77b4",  # tab:blue
    "Western":  "#ff7f0e",  # tab:orange
    "Bunsik":   "#2ca02c",  # tab:green
    "Chinese":  "#d62728",  # tab:red
    "Japanese": "#9467bd",  # tab:purple
}

CUISINE_MAP = {"한식": "Korean", "양식": "Western", "분식": "Bunsik", "중식": "Chinese", "일식": "Japanese"}

DPI = 300
SINGLE_W = 3.5   # single-column inches
DOUBLE_W = 7.0   # double-column inches


def apply_style() -> None:
    plt.rcParams.update({
        "font.family":      "DejaVu Sans",
        "font.size":        9,
        "axes.titlesize":   10,
        "axes.labelsize":   9,
        "xtick.labelsize":  8,
        "ytick.labelsize":  8,
        "legend.fontsize":  8,
        "figure.dpi":       DPI,
        "axes.spines.top":  False,
        "axes.spines.right": False,
    })


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _p_label(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _load_step1_per_run() -> pd.DataFrame | None:
    """step1/per_run_metrics.csv 로드. 없으면 None."""
    p = _RESULTS / "step1" / "per_run_metrics.csv"
    return pd.read_csv(p) if p.exists() else None


def _load_cuisine_per_run_pooled() -> pd.DataFrame | None:
    """식문화 5종 per_run_metrics.csv 를 합산해 반환 (폴백 전용)."""
    frames = []
    for cuisine_kr, cuisine_en in CUISINE_MAP.items():
        p = _RESULTS / "step2_cuisine" / cuisine_kr / "per_run_metrics.csv"
        if p.exists():
            df = pd.read_csv(p)
            df["cuisine"] = cuisine_en
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else None


def _get_g1g2_per_run() -> tuple[pd.DataFrame, str]:
    """(df, source_label) — step1 우선, 없으면 cuisine 풀링."""
    df = _load_step1_per_run()
    if df is not None:
        return df[df.group.isin(["G1", "G2"])].copy(), "step1 (30 runs)"
    df = _load_cuisine_per_run_pooled()
    if df is not None:
        return df[df.group.isin(["G1", "G2"])].copy(), "cuisine pooled (3 runs × 5, test-mode)"
    return None, "no data"


# ── Fig 1: G1 vs G2 박스플롯 ───────────────────────────────────────────────────

def fig1_g1_g2_boxplot(out_dir: Path) -> None:
    apply_style()
    df, source = _get_g1g2_per_run()

    metrics = ["HV", "GD+", "IGD+"]
    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_W, 3.0))
    fig.subplots_adjust(right=0.82, wspace=0.42)

    for ax, metric in zip(axes, metrics):
        g1 = df[df.group == "G1"][metric].dropna().values if df is not None else np.array([])
        g2 = df[df.group == "G2"][metric].dropna().values if df is not None else np.array([])

        if len(g1) == 0 or len(g2) == 0:
            ax.text(0.5, 0.5, "No data\n(re-run simulation)", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8, color="gray")
            ax.set_title(metric)
            continue

        bp = ax.boxplot(
            [g1, g2],
            patch_artist=True,
            widths=0.45,
            medianprops=dict(color="black", linewidth=1.5),
            whiskerprops=dict(linewidth=0.8),
            capprops=dict(linewidth=0.8),
            flierprops=dict(marker="o", markersize=3, alpha=0.5),
        )
        for patch, color in zip(bp["boxes"], [COLORS["G1"], COLORS["G2"]]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_title(metric)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["G1\n(NSGA-II)", "G2\n(R-NSGA-II)"])
        ax.set_ylabel("Value")

    # 범례: 그래프 밖 오른쪽
    legend_handles = [
        mpatches.Patch(facecolor=COLORS["G1"], alpha=0.7, label="G1 (NSGA-II)"),
        mpatches.Patch(facecolor=COLORS["G2"], alpha=0.7, label="G2 (R-NSGA-II)"),
    ]
    fig.legend(handles=legend_handles, loc="center right",
               bbox_to_anchor=(1.0, 0.5), frameon=True, title="Algorithm")

    fig.suptitle("Algorithm Comparison: G1 vs G2 (3-Objective Space)", y=1.02, fontsize=10)

    out_path = out_dir / "fig1_g1_g2_boxplot.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 2: HV 수렴 곡선 ────────────────────────────────────────────────────────

def fig2_convergence(out_dir: Path) -> None:
    """step1/artifacts.npz 에서 세대별 HV 수렴 곡선 생성.

    snapshots_all: list[list[(gen, F_array)]] — 각 run × 각 snapshot에
    파레토 해 집합(F_array)이 저장됨. 세대별 HV를 직접 계산해 평균±표준편차 곡선.
    """
    from experiment.simulation.artifacts import has_artifacts, load_artifacts
    from experiment.core.metrics import compute_indicators, compute_reference_pf

    step1_dir = _RESULTS / "step1"
    apply_style()

    if not has_artifacts(step1_dir):
        _placeholder(out_dir / "fig2_g1_g2_convergence.png",
                     "fig2: run simulation first\n(python -m experiment.simulation.run_step1)")
        return

    payload = load_artifacts(step1_dir)
    groups  = payload["groups"]
    nadir_map = payload["nadir_map"]   # {"G1": ndarray, "G2": ndarray, "G3": ndarray}

    fig, ax = plt.subplots(figsize=(SINGLE_W * 1.4, 3.0))
    fig.subplots_adjust(right=0.75)

    for gname in ("G1", "G2"):
        snaps  = groups[gname]["snapshots_all"]   # list[list[(gen, F_array)]]
        nadir  = nadir_map[gname]

        # 이미 저장된 merged pareto front 를 ref_pf 로 사용 (메모리 절약)
        ref_pf = payload["pareto"].get(gname, None)
        if ref_pf is None or len(ref_pf) == 0:
            continue

        gen_hv: dict[int, list] = {}
        for run_snaps in snaps:
            for gen, F in run_snaps:
                if len(F) == 0:
                    continue
                hv = compute_indicators(F, ref_pf, nadir)["HV"]
                gen_hv.setdefault(int(gen), []).append(hv)

        if not gen_hv:
            continue

        gens  = sorted(gen_hv)
        means = np.array([np.nanmean(gen_hv[g]) for g in gens])
        stds  = np.array([np.nanstd(gen_hv[g])  for g in gens])

        ax.plot(gens, means, color=COLORS[gname], label=gname, linewidth=1.2)
        ax.fill_between(gens, means - stds, means + stds,
                        color=COLORS[gname], alpha=0.15)

    ax.set_xlabel("Generation")
    ax.set_ylabel("Hypervolume (HV)")
    ax.set_title("HV Convergence Curve (G1 vs G2)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=True, title="Algorithm")

    out_path = out_dir / "fig2_g1_g2_convergence.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 3: Pareto 산점도 (f1-f2, f1-f3, f2-f3) ─────────────────────────────

def fig3_pareto_scatter(out_dir: Path) -> None:
    from experiment.simulation.artifacts import has_artifacts, load_artifacts

    step1_dir = _RESULTS / "step1"
    apply_style()

    if not has_artifacts(step1_dir):
        _placeholder(out_dir / "fig3_pareto_scatter.png",
                     "fig3: run simulation first\n(python -m experiment.simulation.run_step1)")
        return

    payload = load_artifacts(step1_dir)
    pareto = payload["pareto"]   # {"G1": ndarray(n,3), "G2": ndarray(n,3), "G3": ndarray(n,4)}

    pairs = [(0, 1, "f1 (Calorie error)", "f2 (Macro error)"),
             (0, 2, "f1 (Calorie error)", "f3 (Price error)"),
             (1, 2, "f2 (Macro error)",   "f3 (Price error)")]

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_W, 2.8))
    fig.subplots_adjust(right=0.82, wspace=0.38)

    for ax, (i, j, xlabel, ylabel) in zip(axes, pairs):
        for gname, marker, zorder in [("G1", "x", 1), ("G2", "^", 2)]:
            pf = pareto.get(gname, np.empty((0, 3)))
            if len(pf) == 0:
                continue
            xi, yj = pf[:, i], pf[:, j]
            # 95th percentile clip — 이상치로 인한 축척 왜곡 방지
            xclip = np.percentile(xi, 95)
            yclip = np.percentile(yj, 95)
            mask = (xi <= xclip) & (yj <= yclip)
            ax.scatter(xi[mask], yj[mask],
                       c=COLORS[gname], marker=marker,
                       s=15, alpha=0.6, zorder=zorder, label=gname)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)

    axes[0].set_title("Pareto Front Projections (3-Objective)")
    legend_handles = [
        plt.Line2D([0], [0], marker="x", color="w", markerfacecolor=COLORS["G1"],
                   markeredgecolor=COLORS["G1"], markersize=6, label="G1 (NSGA-II)"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor=COLORS["G2"],
                   markeredgecolor=COLORS["G2"], markersize=6, label="G2 (R-NSGA-II)"),
    ]
    fig.legend(handles=legend_handles, loc="center right",
               bbox_to_anchor=(1.0, 0.5), frameon=True, title="Algorithm")

    out_path = out_dir / "fig3_pareto_scatter.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 4: Cold Start f4 before/after ─────────────────────────────────────────

def fig4_coldstart(out_dir: Path) -> None:
    csv_path = _RESULTS / "step1_coldstart" / "daily_f4_trend_coldstart.csv"
    apply_style()

    if not csv_path.exists():
        _placeholder(out_dir / "fig4_g3_f4_coldstart.png", "fig4: coldstart CSV not found")
        return

    df = pd.read_csv(csv_path)
    fig, ax = plt.subplots(figsize=(SINGLE_W * 1.3, 3.0))
    fig.subplots_adjust(right=0.72)

    ax.plot(df.day, df.f4_before, color=COLORS["before"],
            linewidth=1.5, linestyle="--", marker="s", markersize=5, label="Without Init")
    ax.plot(df.day, df.f4_after,  color=COLORS["after"],
            linewidth=1.5, linestyle="-",  marker="o", markersize=5, label="Cuisine-based Init")

    ax.set_xlabel("Day")
    ax.set_ylabel("f4 (KG Error Rate)")
    ax.set_title("Cold Start: f4 Before vs After Initialization")
    ax.set_xticks(df.day)

    # 89% reduction 주석 (Day 7 기준)
    f4_end = df.f4_after.iloc[-1]
    f4_start = df.f4_before.iloc[0]
    reduction = (f4_start - f4_end) / f4_start * 100
    ax.annotate(f"−{reduction:.0f}%", xy=(df.day.iloc[-1], f4_end),
                xytext=(df.day.iloc[-1] - 1.5, f4_end + 0.05),
                fontsize=7.5, color=COLORS["after"],
                arrowprops=dict(arrowstyle="->", color=COLORS["after"], lw=0.8))

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True)

    out_path = out_dir / "fig4_g3_f4_coldstart.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 5: 7일 KG 업데이트 f4 추이 (Loop B) — 한식·양식 각각 ────────────────────

def _fig5_single(out_dir: Path, cuisine_kr: str, cuisine_en: str, color: str) -> None:
    """cuisine 1개에 대한 Loop B 7일 f4 + 중복률 그림."""
    apply_style()

    p_f4  = _RESULTS / "step2_cuisine" / cuisine_kr / "daily_f4_trend.csv"
    p_dup = _RESULTS / "step2_cuisine" / cuisine_kr / "daily_duplication.csv"
    if not p_f4.exists():
        _placeholder(out_dir / f"fig5_{cuisine_en.lower()}_7days.png",
                     f"fig5 {cuisine_en}: no data")
        return

    df_f4  = pd.read_csv(p_f4)
    df_dup = pd.read_csv(p_dup) if p_dup.exists() else None

    fig, ax1 = plt.subplots(figsize=(SINGLE_W * 1.4, 2.8))

    ax1.plot(df_f4.day, df_f4.f4, color=color,
             linewidth=1.5, marker="o", markersize=5, label="f4 (KG error)")
    ax1.set_xlabel("Day")
    ax1.set_ylabel("f4 (KG Error Rate)", color=color)
    ax1.tick_params(axis="y", labelcolor=color)
    ax1.set_xticks(range(1, 8))
    ax1.set_ylim(bottom=0)

    if df_dup is not None:
        ax2 = ax1.twinx()
        ax2.bar(df_dup.day, df_dup.duplication_rate * 100,
                alpha=0.25, color="#888888", width=0.5, label="Dup. rate (%)")
        ax2.set_ylabel("Duplication Rate (%)", color="#666666")
        ax2.tick_params(axis="y", labelcolor="#666666")
        max_dup = df_dup.duplication_rate.max() * 100
        ax2.set_ylim(0, max(max_dup * 1.5, 4))
        lines2, labels2 = ax2.get_legend_handles_labels()
    else:
        lines2, labels2 = [], []

    lines1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               loc="upper right", fontsize=7, frameon=True)

    ax1.set_title(f"7-Day KG Update: {cuisine_en} (G3, Loop B)")

    fname = f"fig5_{cuisine_en.lower()}_7days.png"
    fig.savefig(out_dir / fname, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {fname}")


def fig5_7days_f4(out_dir: Path) -> None:
    """한식·양식 각각 별도 그림으로 생성."""
    targets = [("한식", "Korean", CUISINE_COLORS["Korean"]),
               ("양식", "Western", CUISINE_COLORS["Western"])]
    for cuisine_kr, cuisine_en, color in targets:
        _fig5_single(out_dir, cuisine_kr, cuisine_en, color)


# ── Fig 6: G2 vs G3 — f1/f2/f3 3D 투영 비교 ──────────────────────────────────

def fig6_g2_vs_g3_3d(out_dir: Path) -> None:
    from experiment.simulation.artifacts import has_artifacts, load_artifacts

    step1_dir = _RESULTS / "step1"
    apply_style()

    if not has_artifacts(step1_dir):
        _placeholder(out_dir / "fig6_g2_vs_g3_3d.png",
                     "fig6: run simulation first")
        return

    payload = load_artifacts(step1_dir)
    pareto = payload["pareto"]

    pairs = [(0, 1, "f1 (Calorie error)", "f2 (Macro error)"),
             (0, 2, "f1 (Calorie error)", "f3 (Price error)"),
             (1, 2, "f2 (Macro error)",   "f3 (Price error)")]

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_W, 2.8))
    fig.subplots_adjust(right=0.82, wspace=0.38)

    for ax, (i, j, xlabel, ylabel) in zip(axes, pairs):
        g2 = pareto.get("G2", np.empty((0, 3)))
        g3 = pareto.get("G3", np.empty((0, 4)))
        if len(g2) > 0:
            ax.scatter(g2[:, i], g2[:, j], c=COLORS["G2"],
                       marker="^", s=15, alpha=0.6, zorder=1, label="G2")
        if len(g3) > 0:
            ax.scatter(g3[:, i], g3[:, j], c=COLORS["G3"],
                       marker="o", s=15, alpha=0.6, zorder=2, label="G3")
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)

    axes[0].set_title("G2 vs G3: 3D Projection (f1/f2/f3)")
    legend_handles = [
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor=COLORS["G2"],
                   markeredgecolor=COLORS["G2"], markersize=6, label="G2 (R-NSGA-II, 3-obj)"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["G3"],
                   markeredgecolor=COLORS["G3"], markersize=6, label="G3 (R-NSGA-II+KG, 4-obj)"),
    ]
    fig.legend(handles=legend_handles, loc="center right",
               bbox_to_anchor=(1.0, 0.5), frameon=True, title="Algorithm")

    out_path = out_dir / "fig6_g2_vs_g3_3d.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 7: 식문화별 KG 메뉴 수 vs f4 산점도 ──────────────────────────────────

def fig7_cuisine_coverage(out_dir: Path) -> None:
    csv_path = _RESULTS / "step2_cuisine" / "cuisine_summary.csv"
    apply_style()

    if not csv_path.exists():
        _placeholder(out_dir / "fig7_cuisine_coverage.png", "fig7: cuisine_summary.csv not found")
        return

    df = pd.read_csv(csv_path)
    df["cuisine_en"] = df.cuisine.map(CUISINE_MAP)

    fig, ax = plt.subplots(figsize=(SINGLE_W * 1.4, 3.0))
    fig.subplots_adjust(right=0.72)

    for _, row in df.iterrows():
        cuisine_en = row["cuisine_en"]
        ax.scatter(row["kg_menu_count"], row["loop_b_f4_mean"],
                   color=CUISINE_COLORS.get(cuisine_en, "gray"),
                   s=70, zorder=3, label=cuisine_en)
        ax.annotate(cuisine_en, (row["kg_menu_count"], row["loop_b_f4_mean"]),
                    fontsize=7, xytext=(6, 3), textcoords="offset points")

    # 추세선
    if len(df) > 2:
        xs = df["kg_menu_count"].values
        ys = df["loop_b_f4_mean"].values
        z = np.polyfit(xs, ys, 1)
        p_poly = np.poly1d(z)
        x_line = np.linspace(xs.min(), xs.max(), 100)
        ax.plot(x_line, p_poly(x_line), "k--", linewidth=0.8, alpha=0.5, label="Trend")

    ax.set_xlabel("KG Menu Count")
    ax.set_ylabel("Mean f4 (Loop B)")
    ax.set_title("Cuisine Coverage vs KG Personalization Quality")

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=True, title="Cuisine")

    out_path = out_dir / "fig7_cuisine_coverage.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Fig 8: 식문화 5종 G3 IGD+ 비교 ───────────────────────────────────────────

def fig8_cuisine_metrics(out_dir: Path) -> None:
    apply_style()
    data = {}
    for cuisine_kr, cuisine_en in CUISINE_MAP.items():
        p = _RESULTS / "step2_cuisine" / cuisine_kr / "per_run_metrics.csv"
        if p.exists():
            df = pd.read_csv(p)
            g3 = df[df.group == "G3"]["IGD+"].dropna().values
            if len(g3) > 0:
                data[cuisine_en] = g3

    if not data:
        _placeholder(out_dir / "fig8_cuisine_metrics.png", "fig8: no per_run data")
        return

    fig, ax = plt.subplots(figsize=(SINGLE_W * 1.6, 3.0))
    fig.subplots_adjust(right=0.72)

    cuisines = list(data.keys())
    positions = range(1, len(cuisines) + 1)
    bp = ax.boxplot(
        [data[c] for c in cuisines],
        positions=list(positions),
        patch_artist=True,
        widths=0.5,
        medianprops=dict(color="black", linewidth=1.5),
        whiskerprops=dict(linewidth=0.8),
        capprops=dict(linewidth=0.8),
        flierprops=dict(marker="o", markersize=3, alpha=0.5),
    )
    for patch, cuisine in zip(bp["boxes"], cuisines):
        patch.set_facecolor(CUISINE_COLORS[cuisine])
        patch.set_alpha(0.7)

    ax.set_xticks(list(positions))
    ax.set_xticklabels(cuisines, rotation=15, ha="right")
    ax.set_ylabel("IGD+ (G3)")
    ax.set_title("G3 IGD+ by Cuisine Type")

    legend_handles = [
        mpatches.Patch(facecolor=CUISINE_COLORS[c], alpha=0.7, label=c) for c in cuisines
    ]
    ax.legend(handles=legend_handles, loc="upper left",
              bbox_to_anchor=(1.02, 1.0), frameon=True, title="Cuisine")

    out_path = out_dir / "fig8_cuisine_metrics.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Sec 4: 수식·파라미터 표 ───────────────────────────────────────────────────

def sec4_formula_objectives(out_dir: Path) -> None:
    """4목적함수 수식 PNG — 전체 합본 + 개별 f1~f4 파일."""
    apply_style()

    # ── 개별 f1~f4 파일 ─────────────────────────────────────────────────────
    individual = [
        (
            "formula_f1.png",
            r"$f_1 = \left|\dfrac{C_{rec} - C^*}{C^*}\right|$",
            r"Calorie error    ($C^* = 2000$ kcal)",
        ),
        (
            "formula_f2.png",
            r"$f_2 = \dfrac{1}{3}\sum_{m}\left|r_m^{rec} - r_m^*\right|,"
            r"\quad m \in \{carb,\ prot,\ fat\}$",
            r"Macronutrient ratio error",
        ),
        (
            "formula_f3.png",
            r"$f_3 = \left|\dfrac{P_{rec} - P^*}{P^*}\right|$",
            r"Price error    ($P^* = 8{,}000$ KRW)",
        ),
        (
            "formula_f4.png",
            r"$f_4 = 1 - \dfrac{1}{|M|}\sum_{i \in M} S_i$",
            r"KG preference error    ($S_i = p_i \cdot e^{-\lambda \Delta t_i}$)",
        ),
    ]

    for fname, formula, caption in individual:
        fig, ax = plt.subplots(figsize=(DOUBLE_W * 0.85, 1.4))
        ax.axis("off")
        ax.text(0.5, 0.62, formula, transform=ax.transAxes,
                fontsize=13, va="center", ha="center")
        ax.text(0.5, 0.18, caption, transform=ax.transAxes,
                fontsize=9, va="center", ha="center", color="#444444")
        out_path = out_dir / fname
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  saved → {out_path.name}")

    # ── 전체 합본 (formula_objectives.png) ────────────────────────────────
    fig, ax = plt.subplots(figsize=(DOUBLE_W, 2.2))
    ax.axis("off")

    lines = [
        r"$f_1 = \left|\frac{C_{rec} - C^*}{C^*}\right|$"
        r"     (Calorie error, $C^*=2000$ kcal)",
        r"$f_2 = \frac{1}{3}\sum_{m \in \{carb,prot,fat\}} \left|r_m^{rec} - r_m^*\right|$"
        r"     (Macronutrient ratio error)",
        r"$f_3 = \left|\frac{P_{rec} - P^*}{P^*}\right|$"
        r"     (Price error, $P^*=8000$ KRW)",
        r"$f_4 = 1 - \frac{1}{|M|}\sum_{i \in M} S_i$"
        r"     (KG preference error,  $S_i = p_i \cdot e^{-\lambda \Delta t_i}$)",
    ]
    for k, line in enumerate(lines):
        ax.text(0.02, 0.88 - k * 0.22, line, transform=ax.transAxes,
                fontsize=10, va="top", ha="left")

    ax.set_title("Objective Functions ($f_1$–$f_4$)", fontsize=11, pad=8)
    out_path = out_dir / "formula_objectives.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec4_formula_kg_decay(out_dir: Path) -> None:
    """KG 시간감쇠 수식 PNG."""
    apply_style()
    fig, ax = plt.subplots(figsize=(SINGLE_W * 1.8, 1.6))
    ax.axis("off")

    lines = [
        r"$D_{time} = e^{-\lambda \cdot \Delta t}$"
        r"     (time decay,  $\lambda=0.5$,  $\Delta t$ in days)",
        r"$S_i = p_i \cdot (1 - D_i)$"
        r"     (KG score,  $p_i$: preference weight)",
    ]
    for k, line in enumerate(lines):
        ax.text(0.02, 0.78 - k * 0.38, line, transform=ax.transAxes,
                fontsize=10, va="top", ha="left")

    ax.set_title("KG Time-Decay Personalization", fontsize=11, pad=8)
    out_path = out_dir / "formula_kg_decay.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec4_table_model_params(out_dir: Path) -> None:
    """G1/G2/G3 파라미터 비교 표 PNG."""
    apply_style()

    rows = [
        ["Population",       "200",           "200",                    "200"],
        ["Generations",      "200",           "200",                    "200"],
        ["Objectives",       "3 (f1,f2,f3)",  "3 (f1,f2,f3)",           "4 (f1,f2,f3,f4)"],
        ["Reference points", "—",             "[[0,0,0]]",              "[[0,0,0,0]]"],
        ["Crossover",        "2-pt (p=0.9)",  "2-pt (p=0.9)",           "2-pt (p=0.9)"],
        ["Mutation",         "PM (p=1/n)",    "PM (p=1/n)",             "PM (p=1/n)"],
        ["KG integration",   "✗",             "✗ (fixed KG score)",     "✓ (dynamic f4)"],
    ]
    col_labels = ["Parameter", "G1 (NSGA-II)", "G2 (R-NSGA-II)", "G3 (R-NSGA-II+KG)"]

    fig, ax = plt.subplots(figsize=(DOUBLE_W, 2.6))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 1.45)

    # 헤더 색상
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    # 짝수행 음영
    for i in range(1, len(rows) + 1):
        if i % 2 == 0:
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor("#f2f2f2")

    ax.set_title("Algorithm Parameter Comparison", fontsize=11, pad=6)
    out_path = out_dir / "table_model_params.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Sec 5: 실험 설계 표 ───────────────────────────────────────────────────────

def sec5_table_experiment_design(out_dir: Path) -> None:
    """실험 시나리오 요약 표 PNG."""
    apply_style()

    rows = [
        ["Loop A",  "G1/G2/G3 Algorithm\nComparison",
         "All cuisines\n(3,358 items)",   "30 runs\n(seed 42–71)",   "HV, GD+,\nIGD+"],
        ["Loop B",  "G3 7-Day KG\nDynamic Update",
         "All cuisines",                  "1 run/day\n× 7 days",     "f4 trend,\ndup. rate"],
        ["Loop A′", "Cuisine-specific\nG3 Evaluation",
         "Per cuisine pool\n(5 types)",   "30 runs\n(seed 42–71)",   "HV, GD+,\nIGD+, f4"],
        ["Cold\nStart", "KG Init\nComparison",
         "All cuisines",                  "1 run/day\n× 7 days",     "f4 before\nvs after"],
    ]
    col_labels = ["Scenario", "Purpose", "Data Pool", "Runs", "Metrics"]

    # col widths as fractions of total axes width
    col_widths = [0.10, 0.24, 0.24, 0.20, 0.18]

    fig, ax = plt.subplots(figsize=(DOUBLE_W, 3.0))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 2.1)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    for i in range(1, len(rows) + 1):
        if i % 2 == 0:
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor("#f2f2f2")

    ax.set_title("Experimental Scenarios", fontsize=11, pad=6)
    out_path = out_dir / "table_experiment_design.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Sec 1: 시스템 개요도 ──────────────────────────────────────────────────────

def sec1_system_overview(out_dir: Path) -> None:
    """시스템 전체 아키텍처 블록 다이어그램 PNG (fig0_system_overview.png)."""
    apply_style()

    fig, ax = plt.subplots(figsize=(DOUBLE_W * 1.1, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    # 블록 정의: (x_center, y_center, width, height, label_main, label_sub, facecolor)
    blocks = [
        (1.0, 2.0, 1.6, 1.2,
         "User Input",
         "Preferences\nAllergies / Budget",
         "#d4e6f1"),
        (3.1, 2.0, 1.6, 1.2,
         "food_master DB",
         "3,358 items\n(MFDS + Franchise)",
         "#d5f5e3"),
        (5.2, 2.0, 1.6, 1.2,
         "Knowledge Graph",
         "Preference weights\nTime decay (λ=0.5)",
         "#fdebd0"),
        (7.3, 2.0, 1.6, 1.2,
         "R-NSGA-II",
         "4 objectives\nf1  f2  f3  f4",
         "#fadbd8"),
        (9.2, 2.0, 1.4, 1.2,
         "Daily Meal",
         "Pareto-optimal\nrecommendation",
         "#e8daef"),
    ]

    # 목적함수 라벨 (최적화 블록 아래)
    obj_labels = ["f1: Calorie", "f2: Macros", "f3: Price", "f4: KG pref."]

    for xc, yc, w, h, label_main, label_sub, fc in blocks:
        rect = mpatches.FancyBboxPatch(
            (xc - w / 2, yc - h / 2), w, h,
            boxstyle="round,pad=0.05",
            facecolor=fc, edgecolor="#555555", linewidth=1.0,
        )
        ax.add_patch(rect)
        ax.text(xc, yc + 0.18, label_main, ha="center", va="center",
                fontsize=8.5, fontweight="bold")
        ax.text(xc, yc - 0.20, label_sub, ha="center", va="center",
                fontsize=7.2, color="#333333", linespacing=1.4)

    # 화살표 연결
    arrow_props = dict(arrowstyle="-|>", color="#444444", lw=1.2)
    xs = [b[0] for b in blocks]
    widths = [b[2] for b in blocks]
    for i in range(len(blocks) - 1):
        x_start = xs[i] + widths[i] / 2
        x_end   = xs[i + 1] - widths[i + 1] / 2
        ax.annotate("", xy=(x_end, 2.0), xytext=(x_start, 2.0),
                    arrowprops=arrow_props)

    # KG ↔ R-NSGA-II 양방향 피드백 (KG 동적 갱신 표현)
    ax.annotate("", xy=(5.2 + 0.8, 2.0 - 0.5), xytext=(7.3 - 0.8, 2.0 - 0.5),
                arrowprops=dict(arrowstyle="-|>", color="#888888", lw=0.8,
                                connectionstyle="arc3,rad=-0.35"))
    ax.text(6.25, 1.05, "daily update", ha="center", fontsize=6.5, color="#666666",
            style="italic")

    # 목적함수 라벨 (R-NSGA-II 블록 아래)
    for k, lbl in enumerate(obj_labels):
        ax.text(7.3 - 0.6 + k * 0.41, 1.25, lbl, ha="center", fontsize=5.8,
                color="#555555")

    ax.set_title("Proposed System Overview: KG + 4-Objective R-NSGA-II Daily Meal Recommendation",
                 fontsize=10, pad=10)

    out_path = out_dir / "fig0_system_overview.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Sec 2: KG 개념도 ──────────────────────────────────────────────────────────

def sec2_kg_concept(out_dir: Path) -> None:
    """KG 삼중항 예시 — 소규모 노드·엣지 그래프 PNG (fig_kg_concept.png)."""
    try:
        import networkx as nx
    except ImportError:
        _placeholder(out_dir / "fig_kg_concept.png",
                     "fig_kg_concept: install networkx\n(pip install networkx)")
        return

    apply_style()

    G = nx.DiGraph()

    # 노드 정의 — 카테고리·식문화는 노드로 표현하지 않고 본문에서 기술
    nodes = {
        "User A": {"type": "user"},
        "Menu 1": {"type": "food"},
        "Menu 2": {"type": "food"},
    }
    for n in nodes:
        G.add_node(n)

    # 엣지 정의: (head, tail, label)
    edges = [
        ("User A", "Menu 1", "ate (w=0.8)"),
        ("User A", "Menu 2", "ate (w=0.6)"),
    ]
    for h, t, lbl in edges:
        G.add_edge(h, t, label=lbl)

    # 레이아웃 — 수동 위치 지정
    pos = {
        "User A": (0.5, 0.85),
        "Menu 1": (0.15, 0.15),
        "Menu 2": (0.85, 0.15),
    }

    node_colors_map = {"user": "#aed6f1", "food": "#a9dfbf"}
    node_color = [node_colors_map[nodes[n]["type"]] for n in G.nodes()]
    node_size  = [1400 if nodes[n]["type"] == "user" else 1000 for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(DOUBLE_W * 0.55, 3.0))
    ax.axis("off")
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.05, 1.05)

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_color,
                           node_size=node_size, edgecolors="#555555", linewidths=0.8)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=8.5, font_weight="bold")
    nx.draw_networkx_edges(G, pos, ax=ax,
                           edge_color="#666666", arrows=True,
                           arrowstyle="-|>", arrowsize=16,
                           connectionstyle="arc3,rad=0.08",
                           min_source_margin=20, min_target_margin=20,
                           width=1.1)
    edge_labels = {(h, t): lbl for h, t, lbl in edges}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax,
                                 font_size=7.5, label_pos=0.5,
                                 bbox=dict(boxstyle="round,pad=0.15",
                                           fc="white", ec="none", alpha=0.85))

    # 범례
    legend_patches = [
        mpatches.Patch(facecolor="#aed6f1", edgecolor="#555", label="User"),
        mpatches.Patch(facecolor="#a9dfbf", edgecolor="#555", label="Food (Menu)"),
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=7.5,
              frameon=True, title="Node Type", title_fontsize=7.5)

    ax.set_title("Knowledge Graph Structure Example\n"
                 "(User–Menu interaction with preference weights)",
                 fontsize=9, pad=8)

    out_path = out_dir / "fig_kg_concept.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── Sec 3: 데이터 수집 및 정제 ───────────────────────────────────────────────


def sec3_pipeline_table(out_dir: Path) -> None:
    """데이터 수집·정제 파이프라인 전체 개요 표 PNG."""
    apply_style()

    rows = [
        ["Step 0",    "food_research_sample\n→ food_master BULK COPY",
         "Supabase",          "2,524",  "2,522",  "Dedup by\nproduct+brand"],
        ["Step 0b",   "Franchise CSV\n→ food_master INSERT",
         "Gemini 2.5F",       "871",    "850",    "Allergen 22-type\nJSONB parse"],
        ["Step 1/1b", "Naver Shopping API\n+ HACCP API → price/allergen",
         "Naver API\nGemini 2.5F", "2,522", "2,520", "price + allergens\nUPDATE"],
        ["Step 1c",   "Franchise price re-query\n(Naver webkr → Gemini)",
         "Naver API\nGemini 2.5F", "846",   "564",   "price UPDATE\n(re-verified)"],
        ["Step 2",    "LLM meal category\nclassification (5-class)",
         "Gemini 2.5F",       "3,372",  "3,372",  "category_type\n(MAIN/SOUP/SIDE\n/DRINK/SNACK)"],
        ["Step 2b",   "Remove low-quality\nnutrition rows",
         "SQL",               "3,372",  "3,358",  "calories<5 etc.\n14 rows deleted"],
        ["Step 2c",   "Price outlier treatment\n(Tukey IQR×1.5)",
         "SQL",               "3,358",  "3,358",  "142 rows → NULL\n(LOW 16 + HIGH 126)"],
        ["Step 6",    "Cuisine classification\n(7-class)",
         "Gemini 3.1F",       "2,183",  "2,183",  "cuisine_type\n(Korean/Western/…)"],
    ]
    col_labels = ["Step", "Process", "Tool", "Input\n(rows)", "Output\n(rows)", "Transform"]

    col_widths = [0.09, 0.26, 0.16, 0.09, 0.09, 0.24]

    fig, ax = plt.subplots(figsize=(DOUBLE_W * 1.1, 4.2))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    tbl.scale(1, 2.3)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    for i in range(1, len(rows) + 1):
        if i % 2 == 0:
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor("#f2f2f2")

    ax.set_title("Data Collection & Preprocessing Pipeline", fontsize=11, pad=6)
    out_path = out_dir / "table_data_pipeline.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec3_franchise_table(out_dir: Path) -> None:
    """프랜차이즈 6개사 데이터 수집 개요 표 PNG."""
    apply_style()

    rows = [
        ["McDonald's",  "HTML crawl",    "~90",   "Naver Shopping API",  "HACCP API"],
        ["Lotteria",    "HTML crawl",    "~70",   "Naver Shopping API",  "HACCP API"],
        ["Burger King", "CSV (manual)",  "~100",  "Naver Shopping API",  "HACCP API"],
        ["MomsTouсh",  "Excel crawl",   "~80",   "Naver Shopping API",  "HACCP API"],
        ["Subway",      "Excel crawl",   "~60",   "Naver Shopping API",  "HACCP API"],
        ["Salady",      "Excel crawl",   "~50",   "Naver Shopping API",  "HACCP API"],
        ["Preps",       "Excel crawl",   "~50",   "Naver Shopping API",  "HACCP API"],
    ]
    col_labels = ["Brand", "Collect Method", "Items", "Price Source", "Allergen Source"]
    col_widths = [0.16, 0.20, 0.10, 0.28, 0.22]

    fig, ax = plt.subplots(figsize=(DOUBLE_W, 2.8))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.8)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    for i in range(1, len(rows) + 1):
        if i % 2 == 0:
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor("#f2f2f2")

    ax.set_title("Franchise Data Collection Overview (7 Brands, ~500 items)", fontsize=11, pad=6)
    out_path = out_dir / "table_franchise_sources.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec3_category_criteria(out_dir: Path) -> None:
    """5-카테고리 분류 기준 표 PNG."""
    apply_style()

    rows = [
        ["MAIN",  "Primary carbohydrate\nsource (staple food)",
         "High carbs\nLow~mid sodium",
         "Rice, Gimbap, Sandwich,\nPasta, Lunch box"],
        ["SOUP",  "Broth-based dishes\n(soup / stew / porridge)",
         "Very high sodium\nBroth + solid mixed",
         "Doenjang-jjigae, Miyeok-guk,\nRamen, Seolleongtang"],
        ["SIDE",  "Side dishes\n(banchan, no broth)",
         "Mid sodium\nLow carbs",
         "Namul, Grilled items,\nSalad, Kimchi, Jeon"],
        ["DRINK", "Liquid beverages\n(no solid content)",
         "Low calorie\nWater-based",
         "Water, Juice, Coffee,\nMilk, Tea"],
        ["SNACK", "Snacks & desserts",
         "Mid calorie\nMay be high sugar",
         "Chips, Cake,\nNuts, Protein bar"],
    ]
    col_labels = ["Category", "Definition", "Nutritional Profile", "Examples"]
    col_widths = [0.12, 0.23, 0.27, 0.34]

    fig, ax = plt.subplots(figsize=(DOUBLE_W * 1.05, 3.2))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 2.1)

    cat_colors = {
        "MAIN":  "#d4e6f1",
        "SOUP":  "#fadbd8",
        "SIDE":  "#d5f5e3",
        "DRINK": "#fef9e7",
        "SNACK": "#f5eef8",
    }
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    for i, row in enumerate(rows, start=1):
        cat = row[0]
        color = cat_colors.get(cat, "#f2f2f2")
        tbl[i, 0].set_facecolor(color)
        tbl[i, 0].set_text_props(fontweight="bold")

    ax.set_title(
        "5-Class Meal Category Criteria\n(Based on NFIS, MFDS & HACCP Standards)",
        fontsize=10, pad=6,
    )
    out_path = out_dir / "table_category_criteria.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec3_distribution_chart(out_dir: Path) -> None:
    """food_master 카테고리·식문화 분포 서브피겨 PNG."""
    apply_style()

    cat_data = {
        "SNACK": 1101,
        "MAIN":   957,
        "SIDE":   688,
        "DRINK":  441,
        "SOUP":   171,
    }
    cuisine_data = {
        "Korean":   663,
        "Western":  448,
        "Bunsik":    90,
        "Chinese":   33,
        "Japanese":  31,
    }

    cat_colors_list = ["#9467bd", "#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
    cuisine_colors_list = [
        "#1f77b4",  # Korean
        "#ff7f0e",  # Western
        "#2ca02c",  # Bunsik
        "#d62728",  # Chinese
        "#9467bd",  # Japanese
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_W, 3.2))
    fig.subplots_adjust(wspace=0.38)

    # (a) 카테고리 분포
    cats = list(cat_data.keys())
    cat_vals = list(cat_data.values())
    bars1 = ax1.barh(cats, cat_vals, color=cat_colors_list, edgecolor="white", height=0.6)
    for bar, val in zip(bars1, cat_vals):
        ax1.text(bar.get_width() + 15, bar.get_y() + bar.get_height() / 2,
                 str(val), va="center", fontsize=8)
    ax1.set_xlabel("Item Count")
    ax1.set_title("(a) Category Distribution\n", pad=10)
    ax1.set_xlim(0, max(cat_vals) * 1.18)
    ax1.invert_yaxis()

    # (b) 식문화 분포
    cuisines = list(cuisine_data.keys())
    cuisine_vals = list(cuisine_data.values())
    bars2 = ax2.barh(cuisines, cuisine_vals, color=cuisine_colors_list, edgecolor="white", height=0.6)
    for bar, val in zip(bars2, cuisine_vals):
        ax2.text(bar.get_width() + 10, bar.get_y() + bar.get_height() / 2,
                 str(val), va="center", fontsize=8)
    ax2.set_xlabel("Item Count")
    ax2.set_title("(b) Cuisine Distribution\n(experiment cuisines, n=1,265)", pad=10)
    ax2.set_xlim(0, max(cuisine_vals) * 1.22)
    ax2.invert_yaxis()

    fig.suptitle("food_master Dataset Distribution (total 3,358 items)", fontsize=11, y=1.06)
    fig.subplots_adjust(top=0.82)
    out_path = out_dir / "fig_dataset_distribution.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


def sec3_price_outlier_table(out_dir: Path) -> None:
    """Tukey IQR 가격 이상치 처리 결과 표 PNG."""
    apply_style()

    rows = [
        ["MAIN",   "500",  "24,625",  "23",  "23"],
        ["SOUP",   "500",  "43,830",  "13",  "13"],
        ["SIDE",   "500",  "35,250",  "24",  "24"],
        ["DRINK",  "500",  "53,500",  "27",  "27"],
        ["SNACK",  "500",  "39,965",  "39",  "39"],
        ["ALL",    "500",  "—",       "126", "16 (LOW) + 126 (HIGH)"],
    ]
    col_labels = ["Category", "Lower Fence\n(KRW)", "Upper Fence\n(KRW)",
                  "HIGH outliers", "Treated as NULL"]
    col_widths = [0.14, 0.18, 0.18, 0.16, 0.32]

    fig, ax = plt.subplots(figsize=(DOUBLE_W, 2.6))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 1.8)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2c3e50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    # 마지막 행(ALL) 강조
    for j in range(len(col_labels)):
        tbl[len(rows), j].set_facecolor("#eaf2ff")
        tbl[len(rows), j].set_text_props(fontweight="bold")
    for i in range(1, len(rows)):
        if i % 2 == 0:
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor("#f2f2f2")

    ax.set_title(
        "Price Outlier Treatment: Tukey's Fence (IQR × 1.5) per Category\n"
        "(Lower fence fixed at 500 KRW; 142 items → NULL)",
        fontsize=10, pad=6,
    )
    out_path = out_dir / "table_price_outlier.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved → {out_path.name}")


# ── 플레이스홀더 (데이터 없을 때) ──────────────────────────────────────────────

def _placeholder(path: Path, msg: str) -> None:
    fig, ax = plt.subplots(figsize=(4, 2))
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            transform=ax.transAxes, fontsize=9, color="gray",
            bbox=dict(boxstyle="round", fc="lightyellow", ec="gray"))
    ax.axis("off")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  placeholder → {path.name}")


# ── KG 시각화 복사 ────────────────────────────────────────────────────────────

def copy_kg_viz(out_dir: Path) -> None:
    src = _RESULTS / "step2_cuisine" / "plot_kg_visualization.png"
    if src.exists():
        dst = out_dir / "plot_kg_visualization.png"
        shutil.copy2(src, dst)
        print(f"  copied → {dst.name}")
    else:
        print("  WARNING: plot_kg_visualization.png not found")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true",
                        help="fig1만 생성 (스타일 확인용)")
    parser.add_argument("--sec1", action="store_true",
                        help="Sec 1 시스템 개요도만 생성")
    parser.add_argument("--sec2", action="store_true",
                        help="Sec 2 KG 개념도만 생성")
    parser.add_argument("--sec3", action="store_true",
                        help="Sec 3 데이터 그림만 생성")
    parser.add_argument("--all", action="store_true",
                        help="전체 그림 생성")
    args = parser.parse_args()

    if not args.sample and not args.sec1 and not args.sec2 and not args.sec3 and not args.all:
        parser.print_help()
        return

    sec1 = _OUT / "sec1_intro"
    sec2 = _OUT / "sec2_theory"
    sec3 = _OUT / "sec3_data"
    sec4 = _OUT / "sec4_formulas"
    sec5 = _OUT / "sec5_experiment"
    sec6 = _OUT / "sec6_results"
    for d in (sec1, sec2, sec3, sec4, sec5, sec6):
        d.mkdir(parents=True, exist_ok=True)

    print("\n=== paper_figures 생성 ===")

    if args.sec1 or args.all:
        print("\n[Sec1] 시스템 개요도")
        sec1_system_overview(sec1)

    if args.sec2 or args.all:
        print("\n[Sec2] KG 개념도")
        sec2_kg_concept(sec2)

    if args.sec3 or args.all:
        print("\n[Sec3] 데이터 파이프라인 표")
        sec3_pipeline_table(sec3)
        print("\n[Sec3] 프랜차이즈 출처 표")
        sec3_franchise_table(sec3)
        print("\n[Sec3] 카테고리 분류 기준 표")
        sec3_category_criteria(sec3)
        print("\n[Sec3] 카테고리·식문화 분포 차트")
        sec3_distribution_chart(sec3)
        print("\n[Sec3] 가격 이상치 처리 표")
        sec3_price_outlier_table(sec3)

    if args.sample or args.all:
        print("\n[Fig 1] G1 vs G2 boxplot (sample)")
        fig1_g1_g2_boxplot(sec6)

    if args.all:
        print("\n[Sec4] 목적함수 수식")
        sec4_formula_objectives(sec4)
        print("\n[Sec4] KG 시간감쇠 수식")
        sec4_formula_kg_decay(sec4)
        print("\n[Sec4] 모델 파라미터 표")
        sec4_table_model_params(sec4)
        print("\n[Sec5] 실험 설계 표")
        sec5_table_experiment_design(sec5)
        print("\n[Fig 2] HV convergence curve")
        fig2_convergence(sec6)
        print("\n[Fig 3] Pareto scatter (3D)")
        fig3_pareto_scatter(sec6)
        print("\n[Fig 4] Cold start f4")
        fig4_coldstart(sec6)
        print("\n[Fig 5] 7-day f4 trend")
        fig5_7days_f4(sec6)
        print("\n[Fig 6] G2 vs G3 3D projection")
        fig6_g2_vs_g3_3d(sec6)
        print("\n[Fig 7] Cuisine coverage scatter")
        fig7_cuisine_coverage(sec6)
        print("\n[Fig 8] Cuisine G3 IGD+")
        fig8_cuisine_metrics(sec6)
        print("\n[KG viz] Copy existing")
        copy_kg_viz(sec6)

    print(f"\n완료: {_OUT}")


if __name__ == "__main__":
    main()
