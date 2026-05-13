"""plot_step2_results.py — 논문용 3종 시각화

Figure 1  plot_interp1_g1_vs_g2.png
  해석1: G1(NSGA-II) vs G2(R-NSGA-II) 알고리즘 순효과
  5 cuisines × 30 runs pooled — per-cuisine 평균을 data point로 grouped bar chart

Figure 2  plot_interp2_g2_vs_g3.png
  해석2: G2 vs G3 KG 통합 효과
  (a) 식문화별 Loop B f4 일별 추이 (7일)
  (b) KG 메뉴 수 vs f4 평균 scatter (로그 스케일 + 회귀선)

Figure 3  plot_kg_visualization.png
  KG 구조 시각화 — 한식 Day 0 vs Day 7 (NetworkX radial layout)

Usage:
    python -X utf8 -m experiment.tools.plot_step2_results
    python -X utf8 -m experiment.tools.plot_step2_results --no_kg
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from datetime import datetime, timedelta
from math import cos, pi, sin
from pathlib import Path

import numpy as np

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    # 한글 폰트 설정 (Windows: Malgun Gothic, fallback to NanumGothic)
    import platform
    _KOREAN_FONT = "Malgun Gothic" if platform.system() == "Windows" else "NanumGothic"
    plt.rcParams["font.family"] = [_KOREAN_FONT, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ──────────────────────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────────────────────

CUISINES = ["한식", "양식", "분식", "중식", "일식"]
_OUT_DIR  = _PROJECT_ROOT / "experiment" / "results" / "step2_cuisine"

_CUISINE_COLORS = {
    "한식": "#e74c3c",
    "양식": "#2980b9",
    "분식": "#27ae60",
    "중식": "#f39c12",
    "일식": "#8e44ad",
}

TEST_USER  = "test_user_1"
BASE_DATE  = datetime(2026, 5, 7, 12, 0, 0)
_REF_G3    = np.array([[0.0, 0.0, 0.0, 0.0], [0.1, 0.1, 0.1, 0.0]])

# ──────────────────────────────────────────────────────────────────────────────
# 데이터 로딩 유틸
# ──────────────────────────────────────────────────────────────────────────────

def _load_metrics(cuisine: str) -> dict:
    """metrics_comparison.csv → {group: {metric: {mean, std, min, max}}}"""
    path = _OUT_DIR / cuisine / "metrics_comparison.csv"
    result: dict = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g, m = row["group"], row["metric"]
            if g not in result:
                result[g] = {}
            result[g][m] = {
                "mean": float(row["mean"]),
                "std":  float(row["std"]),
                "min":  float(row["min"]),
                "max":  float(row["max"]),
            }
    return result


def _load_daily_f4(cuisine: str) -> list[dict]:
    path = _OUT_DIR / cuisine / "daily_f4_trend.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({"day": int(row["day"]), "f4": float(row["f4"])})
    return rows


def _load_cuisine_summary() -> list[dict]:
    path = _OUT_DIR / "cuisine_summary.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "cuisine":       row["cuisine"],
                "kg_menu_count": int(row["kg_menu_count"]),
                "f4_mean":       float(row["loop_b_f4_mean"]),
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Figure 1: 해석1 — G1 vs G2 알고리즘 비교
# ──────────────────────────────────────────────────────────────────────────────

def _sig_label(p: float) -> str:
    if math.isnan(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _add_sig_bracket(ax, x0: float, x1: float, y: float, label: str) -> None:
    ax.plot([x0, x0, x1, x1], [y * 0.99, y, y, y * 0.99],
            color="black", linewidth=1.0)
    ax.text((x0 + x1) / 2, y * 1.005, label,
            ha="center", va="bottom", fontsize=11, fontweight="bold")


def plot_interp1(out_dir: Path) -> None:
    """G1 vs G2 per-cuisine 평균 비교 bar chart (3 metrics)."""
    try:
        from scipy.stats import wilcoxon as scipy_wilcoxon
        def _wilcoxon_p(a, b):
            _, p = scipy_wilcoxon(a, b)
            return float(p)
    except ImportError:
        def _wilcoxon_p(a, b):
            return float("nan")

    metrics_cfg = [
        ("HV",   "Hypervolume ↑"),
        ("GD+",  "GD+ ↓"),
        ("IGD+", "IGD+ ↓"),
    ]

    # 5 cuisine × per-group mean 수집
    g1_vals: dict[str, list] = {m: [] for m, _ in metrics_cfg}
    g2_vals: dict[str, list] = {m: [] for m, _ in metrics_cfg}
    for c in CUISINES:
        data = _load_metrics(c)
        for mname, _ in metrics_cfg:
            g1_vals[mname].append(data["G1"][mname]["mean"])
            g2_vals[mname].append(data["G2"][mname]["mean"])

    random.seed(0)
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    fig.suptitle(
        "Algorithm Effect: NSGA-II (G1) vs R-NSGA-II (G2)\n"
        "3-objective | 5 cuisines × 30 runs = 150 runs each",
        fontsize=12, fontweight="bold", y=1.03,
    )

    for idx, (ax, (mname, mlabel)) in enumerate(zip(axes, metrics_cfg)):
        v1 = np.array(g1_vals[mname])
        v2 = np.array(g2_vals[mname])

        # 유의성 검정
        p = _wilcoxon_p(v1, v2)

        # bar: pooled mean across 5 cuisines
        means  = [v1.mean(), v2.mean()]
        stds   = [v1.std(ddof=1), v2.std(ddof=1)]
        colors = ["#e74c3c", "#2980b9"]
        x      = np.array([0.0, 1.0])

        ax.bar(x, means, yerr=stds, color=colors, width=0.45,
               capsize=6, alpha=0.75, edgecolor="white", linewidth=0.5,
               error_kw={"elinewidth": 1.5, "capthick": 1.5})

        # 식문화별 data point + 연결선 (jitter)
        rng_state = random.getstate()
        for ci, (cuisine, c_color) in enumerate(_CUISINE_COLORS.items()):
            jx1 = x[0] + (random.random() - 0.5) * 0.3
            jx2 = x[1] + (random.random() - 0.5) * 0.3
            ax.scatter([jx1, jx2], [v1[ci], v2[ci]],
                       color=c_color, s=45, zorder=6,
                       edgecolors="white", linewidths=0.8)
            ax.plot([jx1, jx2], [v1[ci], v2[ci]],
                    color=c_color, alpha=0.35, linewidth=0.9, zorder=5)

        # 유의성 브래킷
        y_top = max(means[0] + stds[0], means[1] + stds[1])
        y_br  = y_top * 1.18
        _add_sig_bracket(ax, x[0], x[1], y_br, _sig_label(p))

        ax.set_xlim(-0.5, 1.5)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["G1\n(NSGA-II)", "G2\n(R-NSGA-II)"], fontsize=10)
        ax.set_ylabel(mlabel, fontsize=10)
        ax.set_title(f"({chr(97 + idx)}) {mlabel}", fontsize=11)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylim(bottom=0, top=y_br * 1.12)

        p_txt = f"Wilcoxon p = {p:.4f}" if not math.isnan(p) else ""
        ax.text(0.97, 0.03, p_txt,
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7.5, color="dimgray")

    # 범례
    cuisine_patches = [
        Patch(color=col, label=c)
        for c, col in _CUISINE_COLORS.items()
    ]
    fig.legend(handles=cuisine_patches, loc="upper right",
               bbox_to_anchor=(1.01, 1.0), title="Cuisine",
               fontsize=8, title_fontsize=8, ncol=1)

    plt.tight_layout()
    path = out_dir / "plot_interp1_g1_vs_g2.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 1] 저장: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Figure 2: 해석2 — G2 vs G3 KG 통합 효과
# ──────────────────────────────────────────────────────────────────────────────

def plot_interp2(out_dir: Path) -> None:
    """(a) 식문화별 f4 7일 추이  (b) KG 메뉴 수 vs f4 scatter."""
    summary = _load_cuisine_summary()
    daily   = {c: _load_daily_f4(c) for c in CUISINES}
    kg_cnt  = {row["cuisine"]: row["kg_menu_count"] for row in summary}

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "KG Integration Effect: G3 (R-NSGA-II + KG) — Loop B Simulation",
        fontsize=12, fontweight="bold", y=1.03,
    )

    # ── (a) 일별 f4 추이 ──────────────────────────────────────────────────────
    ax = axes[0]
    for c in CUISINES:
        color = _CUISINE_COLORS[c]
        days  = [r["day"] for r in daily[c]]
        f4s   = [r["f4"]  for r in daily[c]]
        n     = kg_cnt.get(c, "?")
        ax.plot(days, f4s, marker="o", color=color, linewidth=2,
                markersize=6, label=f"{c}  (n={n})", zorder=5)

    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("f4  (KG preference error rate, ↓ better)", fontsize=10)
    ax.set_title("(a) Daily f4 Trend by Cuisine Preference", fontsize=11)
    ax.set_xticks(range(1, 8))
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # ── (b) KG 메뉴 수 vs f4 scatter + 회귀선 ────────────────────────────────
    ax = axes[1]
    xs    = np.array([row["kg_menu_count"] for row in summary], dtype=float)
    ys    = np.array([row["f4_mean"]        for row in summary], dtype=float)
    names = [row["cuisine"] for row in summary]

    # 로그x 회귀
    lx    = np.log(xs)
    coeff = np.polyfit(lx, ys, 1)
    x_fit = np.linspace(xs.min() * 0.6, xs.max() * 1.3, 300)
    y_fit = np.polyval(coeff, np.log(x_fit))
    r2    = float(np.corrcoef(lx, ys)[0, 1] ** 2)

    ax.plot(x_fit, y_fit, "--", color="gray", linewidth=1.5, alpha=0.85,
            label=f"Trend (log-linear, R²={r2:.3f})", zorder=3)

    for x_val, y_val, c_name in zip(xs, ys, names):
        color = _CUISINE_COLORS[c_name]
        ax.scatter([x_val], [y_val], color=color, s=110, zorder=6,
                   edgecolors="white", linewidths=1.2)
        ax.annotate(c_name, (x_val, y_val), xytext=(7, 5),
                    textcoords="offset points",
                    fontsize=9, color=color, fontweight="bold")

    ax.set_xscale("log")
    ax.set_xlabel("KG Preference Menus (log scale)", fontsize=11)
    ax.set_ylabel("f4 Mean  (7-day Loop B avg)", fontsize=10)
    ax.set_title("(b) KG Coverage vs f4 Performance", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.text(0.97, 0.96,
            "More KG menus → lower f4\n(better preference coverage)",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="dimgray",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

    plt.tight_layout()
    path = out_dir / "plot_interp2_g2_vs_g3.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 2] 저장: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Figure 3: KG 구조 시각화
# ──────────────────────────────────────────────────────────────────────────────

def _build_kg_cuisine_local(
    all_foods: list[dict],
    cuisine: str,
    weight: float,
) -> object:
    """_build_kg_cuisine 로컬 복사본 (import 의존 제거)."""
    from experiment.core.kg_manager import KGManager, make_menu_id
    kg = KGManager()
    for item in all_foods:
        mid = make_menu_id(item)
        if not mid:
            continue
        cat         = item.get("category_type", item.get("category", "UNKNOWN"))
        cuisine_val = item.get("cuisine_type")
        kg.add_menu(mid, category=cat, cuisine=cuisine_val)
    kg.set_cuisine_preference(TEST_USER, cuisine, weight)
    return kg


def _draw_kg_panel(
    ax,
    kg,
    user_id: str,
    sample_mids: list[str],
    sim_now: datetime,
    lambda_decay: float,
    title: str,
) -> None:
    """NetworkX radial layout으로 KG 상태 한 패널 그리기."""
    try:
        import networkx as nx
    except ImportError:
        ax.text(0.5, 0.5, "networkx not installed",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title)
        return

    n = len(sample_mids)
    center = (0.0, 0.0)
    pos    = {user_id: center}
    for i, mid in enumerate(sample_mids):
        angle = 2 * pi * i / n + pi / 2
        pos[mid] = (2.8 * cos(angle), 2.8 * sin(angle))

    node_colors: list = []
    node_sizes:  list = []
    for node in [user_id] + sample_mids:
        if node == user_id:
            node_colors.append("#2c3e50")
            node_sizes.append(700)
        else:
            edata    = kg.G.get_edge_data(user_id, node, default={})
            last_ate = edata.get("last_ate")
            pref     = float(edata.get("pref", 0.0))
            if last_ate is not None:
                delta     = max(0.0, (sim_now - last_ate).total_seconds() / 86400.0)
                intensity = math.exp(-lambda_decay * delta)
                r_v = 0.90
                g_v = 0.28 + (1.0 - intensity) * 0.30
                b_v = 0.18
                node_colors.append((r_v, g_v, b_v))
                node_sizes.append(int(100 + intensity * 200))
            elif pref > 1.0:
                node_colors.append("#27ae60")
                node_sizes.append(90)
            else:
                node_colors.append("#bdc3c7")
                node_sizes.append(60)

    edge_list:   list = []
    edge_colors: list = []
    edge_widths: list = []
    for mid in sample_mids:
        if not kg.G.has_edge(user_id, mid):
            continue
        edata    = kg.G[user_id][mid]
        pref     = float(edata.get("pref", 1.0))
        last_ate = edata.get("last_ate")
        if last_ate is not None:
            delta  = max(0.0, (sim_now - last_ate).total_seconds() / 86400.0)
            decay  = math.exp(-lambda_decay * delta)
            ec     = (0.85, 0.45 + (1 - decay) * 0.2, 0.12)
            ew     = 0.6 + pref * 1.2 * (1 - decay * 0.5)
        elif pref > 1.0:
            ec = (0.15, 0.68, 0.35)
            ew = 0.5 + pref * 1.2
        else:
            ec = (0.78, 0.78, 0.78)
            ew = 0.4
        edge_list.append((user_id, mid))
        edge_colors.append(ec)
        edge_widths.append(ew)

    all_nodes = [user_id] + sample_mids
    sub_g     = kg.G.subgraph(all_nodes)

    nx.draw_networkx_nodes(
        sub_g, pos, nodelist=[user_id],
        node_color=["#2c3e50"], node_size=[700], ax=ax,
    )
    nx.draw_networkx_nodes(
        sub_g, pos, nodelist=sample_mids,
        node_color=node_colors[1:], node_size=node_sizes[1:], ax=ax,
    )
    if edge_list:
        nx.draw_networkx_edges(
            sub_g, pos, edgelist=edge_list,
            edge_color=edge_colors, width=edge_widths,
            arrows=False, ax=ax, alpha=0.75,
        )

    ax.text(0, 0, "User", ha="center", va="center",
            fontsize=8, color="white", fontweight="bold", zorder=10)
    ax.set_title(title, fontsize=10.5, fontweight="bold")
    ax.axis("off")


def plot_kg_visualization(out_dir: Path) -> None:
    """한식 KG Day 0 vs Day 7 — NetworkX 방사형 레이아웃."""
    from experiment.core.loader import FoodDataLoader
    from experiment.core.nutrition import NutritionProfile
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.tools.simulate_kg import _run_one_day

    print("  [Figure 3] Supabase 데이터 로딩...")
    loader     = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks

    cuisine = "한식"
    weight  = 1.3

    # ── Day 0 KG 빌드 ─────────────────────────────────────────────────────────
    kg_day0 = _build_kg_cuisine_local(all_foods, cuisine, weight)

    korean_mids = [
        node for node, attrs in kg_day0.G.nodes(data=True)
        if attrs.get("type") == "menu" and attrs.get("cuisine") == cuisine
    ]
    random.seed(42)
    n_sample    = min(40, len(korean_mids))
    sample_mids = random.sample(korean_mids, n_sample)
    print(f"  [Figure 3] 한식 메뉴 {len(korean_mids)}개 중 {n_sample}개 샘플링")

    # ── Day 7 KG — 경량 재시뮬레이션 (pop=30, gen=30) ────────────────────────
    print("  [Figure 3] Day 7 KG 상태 재현 중 (pop=30, gen=30) ...")
    kg_day7  = _build_kg_cuisine_local(all_foods, cuisine, weight)
    profile  = NutritionProfile.who2025()

    for day in range(1, 8):
        today   = BASE_DATE + timedelta(days=day - 1)
        problem = DailyExp3Problem(
            mains=mains, sides_soup=sides_soup,
            drinks=drinks, snacks=snacks,
            n_meals=3, include_snack=False,
            cal_star=2000.0, price_per_meal_star=8000.0,
            profile=profile,
            kg_manager=kg_day7, user_id=TEST_USER,
            lambda_decay=0.5, sim_now=today,
        )
        best_F, best_X = _run_one_day(problem, 30, 30, 42 + day, _REF_G3)
        if best_X is not None:
            combo = problem.decode(best_X)
            for item in combo:
                mid = make_menu_id(item)
                if mid:
                    kg_day7.record_eating(TEST_USER, mid, today)

    sim_day7 = BASE_DATE + timedelta(days=6)

    # ── 시각화 ───────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"Knowledge Graph Structure — 한식 Cuisine (pref={weight})  "
        f"[{n_sample} menus sampled]",
        fontsize=12, fontweight="bold",
    )

    _draw_kg_panel(
        axes[0], kg_day0, TEST_USER, sample_mids,
        sim_now=BASE_DATE, lambda_decay=0.5,
        title=f"(a) Day 0 — Initial State\nAll {n_sample} sampled menus: pref={weight}",
    )
    _draw_kg_panel(
        axes[1], kg_day7, TEST_USER, sample_mids,
        sim_now=sim_day7, lambda_decay=0.5,
        title="(b) Day 7 — After 7-day Simulation\n"
              "Red-orange = recently eaten (decay applied)",
    )

    legend_items = [
        Patch(color="#27ae60",       label=f"pref={weight} (cuisine init, not yet eaten)"),
        Patch(color=(0.9, 0.28, 0.18), label="Eaten most recently (high decay)"),
        Patch(color=(0.9, 0.48, 0.24), label="Eaten earlier (partial decay)"),
        Patch(color="#bdc3c7",       label="Default pref (not in cuisine)"),
    ]
    fig.legend(handles=legend_items, loc="lower center",
               ncol=2, fontsize=9, bbox_to_anchor=(0.5, -0.04))

    plt.tight_layout()
    path = out_dir / "plot_kg_visualization.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 3] 저장: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Step2 실험 결과 3종 시각화")
    parser.add_argument("--no_kg", action="store_true",
                        help="KG 시각화 생략 (Supabase 연결 없이 Figure 1·2만)")
    args = parser.parse_args()

    if not HAS_MPL:
        print("ERROR: matplotlib 미설치 — pip install matplotlib")
        sys.exit(1)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[Figure 1] G1 vs G2 알고리즘 비교...")
    plot_interp1(_OUT_DIR)

    print("[Figure 2] G2 vs G3 KG 통합 효과...")
    plot_interp2(_OUT_DIR)

    if not args.no_kg:
        print("[Figure 3] KG 구조 시각화 (Supabase 연결 필요)...")
        plot_kg_visualization(_OUT_DIR)
    else:
        print("[Figure 3] --no_kg 플래그: KG 시각화 생략")

    print(f"\n완료. 저장 위치: {_OUT_DIR}")


if __name__ == "__main__":
    main()
