"""plot_step2_results.py — Paper-quality 3-figure visualization

Figure 1  plot_interp1_g1_vs_g2.png
  Interpretation 1: G1 (NSGA-II) vs G2 (R-NSGA-II) algorithm effect
  Panels (a)(b)(c): G1 vs G2 boxplots — 5 cuisines × 30 runs = 150 observations each
  Panel (d): G3 standalone — per-cuisine GD+ convergence quality (n=30 each)

Figure 2  plot_interp2_g2_vs_g3.png
  Interpretation 2: KG integration effect (G3)
  (a) Daily f4 trend by cuisine (7-day Loop B)
  (b) KG coverage (# menus) vs f4 scatter (log-scale + regression)

Figure 3  plot_kg_visualization.png
  KG structure — Korean cuisine, Day 0 vs Day 7 (NetworkX radial layout)

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
    plt.rcParams["axes.unicode_minus"] = False
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

CUISINES = ["한식", "양식", "분식", "중식", "일식"]

_CUISINE_EN = {
    "한식": "Korean",
    "양식": "Western",
    "분식": "Snack",
    "중식": "Chinese",
    "일식": "Japanese",
}

_OUT_DIR = _PROJECT_ROOT / "experiment" / "results" / "step2_cuisine"

_CUISINE_COLORS = {
    "Korean":  "#e74c3c",
    "Western": "#2980b9",
    "Snack":   "#27ae60",
    "Chinese": "#f39c12",
    "Japanese":"#8e44ad",
}

TEST_USER  = "test_user_1"
BASE_DATE  = datetime(2026, 5, 7, 12, 0, 0)
_REF_G3    = np.array([[0.0, 0.0, 0.0, 0.0], [0.1, 0.1, 0.1, 0.0]])

# ──────────────────────────────────────────────────────────────────────────────
# Data loading utilities
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


def _load_perrun_metrics(cuisine: str) -> list[dict]:
    """per_run_metrics.csv → list of {group, run_idx, HV, GD+, IGD+}"""
    path = _OUT_DIR / cuisine / "per_run_metrics.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "group":   row["group"],
                "run_idx": int(row["run_idx"]),
                "HV":   float(row["HV"])   if row["HV"]   != "nan" else np.nan,
                "GD+":  float(row["GD+"])  if row["GD+"]  != "nan" else np.nan,
                "IGD+": float(row["IGD+"]) if row["IGD+"] != "nan" else np.nan,
            })
    return rows


def _load_daily_f4(cuisine: str) -> list[dict]:
    path = _OUT_DIR / cuisine / "daily_f4_trend.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({"day": int(row["day"]), "f4": float(row["f4"])})
    return rows


def _load_cuisine_summary() -> list[dict]:
    """cuisine_summary.csv — f4_mean computed directly from daily_f4_trend.csv
    (robust: cuisine_summary loop_b columns may be NaN after --skip_loop_b re-run)
    """
    path = _OUT_DIR / "cuisine_summary.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cuisine = row["cuisine"]
            # Always compute f4_mean from the actual 7-day data
            daily   = _load_daily_f4(cuisine)
            f4_mean = float(np.mean([r["f4"] for r in daily])) if daily else float("nan")
            rows.append({
                "cuisine":       cuisine,
                "kg_menu_count": int(row["kg_menu_count"]),
                "f4_mean":       f4_mean,
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Figure 1: Interpretation 1 — G1 vs G2 + G3 standalone
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
    """G1 vs G2 boxplot (n=150 pooled) + G3 standalone per-cuisine GD+."""
    try:
        from scipy.stats import ranksums
        def _ranksums_p(a, b):
            _, p = ranksums(a, b)
            return float(p)
    except ImportError:
        def _ranksums_p(a, b):
            return float("nan")

    metrics_cfg = [
        ("HV",   "Hypervolume (↑)"),
        ("GD+",  "GD+ (↓)"),
        ("IGD+", "IGD+ (↓)"),
    ]

    # ── Collect data ──────────────────────────────────────────────────────────
    # G1/G2: pool across all 5 cuisines (150 each) — cuisine-independent
    g1_pool: dict[str, list] = {m: [] for m, _ in metrics_cfg}
    g2_pool: dict[str, list] = {m: [] for m, _ in metrics_cfg}
    # G3: per-cuisine
    g3_by_cuisine: dict[str, dict] = {c: {"GD+": [], "IGD+": []} for c in CUISINES}
    # Per-cuisine means for overlay dots
    g1_means: dict[str, list] = {m: [] for m, _ in metrics_cfg}
    g2_means: dict[str, list] = {m: [] for m, _ in metrics_cfg}

    # Statistics: use Korean representative (G1/G2 cuisine-independent)
    _STAT_CUISINE = "한식"
    stat_data = _load_perrun_metrics(_STAT_CUISINE)
    stat_g1 = {m: [r[m] for r in stat_data if r["group"] == "G1"
                   and not np.isnan(r[m])] for m, _ in metrics_cfg}
    stat_g2 = {m: [r[m] for r in stat_data if r["group"] == "G2"
                   and not np.isnan(r[m])] for m, _ in metrics_cfg}
    p_vals = {m: _ranksums_p(stat_g1[m], stat_g2[m]) for m, _ in metrics_cfg}

    for c in CUISINES:
        rows   = _load_perrun_metrics(c)
        g1rows = [r for r in rows if r["group"] == "G1"]
        g2rows = [r for r in rows if r["group"] == "G2"]
        g3rows = [r for r in rows if r["group"] == "G3"]

        for mname, _ in metrics_cfg:
            v1 = [r[mname] for r in g1rows if not np.isnan(r[mname])]
            v2 = [r[mname] for r in g2rows if not np.isnan(r[mname])]
            g1_pool[mname].extend(v1)
            g2_pool[mname].extend(v2)
            g1_means[mname].append(float(np.mean(v1)) if v1 else np.nan)
            g2_means[mname].append(float(np.mean(v2)) if v2 else np.nan)

        g3_by_cuisine[c]["GD+"]  = [r["GD+"]  for r in g3rows if not np.isnan(r["GD+"])]
        g3_by_cuisine[c]["IGD+"] = [r["IGD+"] for r in g3rows if not np.isnan(r["IGD+"])]

    # ── Figure layout ─────────────────────────────────────────────────────────
    random.seed(0)
    fig, axes = plt.subplots(1, 4, figsize=(17, 5.5))
    fig.suptitle(
        "Algorithm Comparison: G1 (NSGA-II) vs G2 (R-NSGA-II)  |  "
        "3-objective, 5 cuisines x 30 runs = 150 obs each",
        fontsize=11, fontweight="bold", y=1.03,
    )

    # ── Panels (a)(b)(c): G1 vs G2 boxplots ──────────────────────────────────
    for idx, (ax, (mname, mlabel)) in enumerate(zip(axes[:3], metrics_cfg)):
        v1 = np.array(g1_pool[mname])
        v2 = np.array(g2_pool[mname])
        p  = p_vals[mname]

        # Boxplot
        bp = ax.boxplot(
            [v1, v2],
            positions=[0.0, 1.0],
            widths=0.45,
            patch_artist=True,
            showfliers=True,
            flierprops=dict(marker=".", markersize=3, alpha=0.4),
            medianprops=dict(color="black", linewidth=2),
            whiskerprops=dict(linewidth=1.2),
            capprops=dict(linewidth=1.2),
        )
        for patch, color in zip(bp["boxes"], ["#e74c3c", "#2980b9"]):
            patch.set_facecolor(color)
            patch.set_alpha(0.55)

        # Per-cuisine mean dots + connecting lines
        for ci, c in enumerate(CUISINES):
            cname = _CUISINE_EN[c]
            color = _CUISINE_COLORS[cname]
            m1    = g1_means[mname][ci]
            m2    = g2_means[mname][ci]
            jx1   = 0.0 + (random.random() - 0.5) * 0.28
            jx2   = 1.0 + (random.random() - 0.5) * 0.28
            ax.scatter([jx1, jx2], [m1, m2],
                       color=color, s=55, zorder=6,
                       edgecolors="white", linewidths=0.8)
            ax.plot([jx1, jx2], [m1, m2],
                    color=color, alpha=0.40, linewidth=1.0, zorder=5)

        # Significance bracket
        y_top = max(np.nanpercentile(v1, 95), np.nanpercentile(v2, 95))
        y_br  = y_top * 1.15
        _add_sig_bracket(ax, 0.0, 1.0, y_br, _sig_label(p))

        ax.set_xlim(-0.6, 1.6)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["G1\n(NSGA-II)", "G2\n(R-NSGA-II)"], fontsize=10)
        ax.set_ylabel(mlabel, fontsize=10)
        ax.set_title(f"({chr(97 + idx)}) {mlabel}", fontsize=11)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylim(bottom=0)

        p_txt = (f"Wilcoxon p = {p:.2e}" if p < 0.001
                 else f"Wilcoxon p = {p:.4f}") if not math.isnan(p) else ""
        ax.text(0.97, 0.03, p_txt + "\n(n=30, cuisine-indep.)",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7, color="dimgray")

    # ── Panel (d): G3 per-cuisine GD+ boxplots ────────────────────────────────
    ax4 = axes[3]
    x_pos   = np.arange(len(CUISINES))
    g3_gdp  = [g3_by_cuisine[c]["GD+"] for c in CUISINES]
    colors4 = [_CUISINE_COLORS[_CUISINE_EN[c]] for c in CUISINES]

    bp4 = ax4.boxplot(
        g3_gdp,
        positions=x_pos,
        widths=0.5,
        patch_artist=True,
        showfliers=True,
        flierprops=dict(marker=".", markersize=3, alpha=0.45),
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
    )
    for patch, color in zip(bp4["boxes"], colors4):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)

    ax4.set_xlim(-0.7, len(CUISINES) - 0.3)
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([_CUISINE_EN[c] for c in CUISINES], fontsize=9, rotation=15)
    ax4.set_ylabel("GD+ (↓)", fontsize=10)
    ax4.set_title("(d) G3 (R-NSGA-II + KG)\n4-obj convergence quality", fontsize=11)
    ax4.grid(axis="y", alpha=0.3)
    ax4.spines["top"].set_visible(False)
    ax4.spines["right"].set_visible(False)
    ax4.set_ylim(bottom=0)
    ax4.text(0.97, 0.97,
             "G3: 4-objective space\n(not comparable to G1/G2)",
             transform=ax4.transAxes, ha="right", va="top",
             fontsize=7.5, color="dimgray",
             bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

    # n= annotation
    for xi, c in enumerate(CUISINES):
        n = len(g3_by_cuisine[c]["GD+"])
        ax4.text(xi, -ax4.get_ylim()[1] * 0.06, f"n={n}",
                 ha="center", va="top", fontsize=7, color="gray")

    # ── Legend ────────────────────────────────────────────────────────────────
    cuisine_patches = [
        Patch(color=_CUISINE_COLORS[_CUISINE_EN[c]], label=_CUISINE_EN[c])
        for c in CUISINES
    ]
    fig.legend(handles=cuisine_patches, loc="upper right",
               bbox_to_anchor=(1.01, 1.0), title="Cuisine (dots = per-cuisine mean)",
               fontsize=8, title_fontsize=8, ncol=1)

    plt.tight_layout()
    path = out_dir / "plot_interp1_g1_vs_g2.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 1] Saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Figure 2: Interpretation 2 — G2 vs G3 KG integration effect
# ──────────────────────────────────────────────────────────────────────────────

def plot_interp2(out_dir: Path) -> None:
    """(a) Daily f4 trend by cuisine  (b) KG menu count vs f4 scatter."""
    summary = _load_cuisine_summary()
    daily   = {c: _load_daily_f4(c) for c in CUISINES}
    kg_cnt  = {row["cuisine"]: row["kg_menu_count"] for row in summary}

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "KG Integration Effect: G3 (R-NSGA-II + KG) — Loop B Simulation",
        fontsize=12, fontweight="bold", y=1.03,
    )

    # ── (a) Daily f4 trend ────────────────────────────────────────────────────
    ax = axes[0]
    for c in CUISINES:
        cname = _CUISINE_EN[c]
        color = _CUISINE_COLORS[cname]
        days  = [r["day"] for r in daily[c]]
        f4s   = [r["f4"]  for r in daily[c]]
        n     = kg_cnt.get(c, "?")
        ax.plot(days, f4s, marker="o", color=color, linewidth=2,
                markersize=6, label=f"{cname}  (n={n})", zorder=5)

    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("f4  (KG preference error rate, lower is better)", fontsize=10)
    ax.set_title("(a) Daily f4 Trend by Cuisine Preference", fontsize=11)
    ax.set_xticks(range(1, 8))
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # ── (b) KG menu count vs f4 scatter + regression ──────────────────────────
    ax = axes[1]
    xs    = np.array([row["kg_menu_count"] for row in summary], dtype=float)
    ys    = np.array([row["f4_mean"]        for row in summary], dtype=float)
    names = [row["cuisine"] for row in summary]

    # Log-x regression
    lx    = np.log(xs)
    coeff = np.polyfit(lx, ys, 1)
    x_fit = np.linspace(xs.min() * 0.6, xs.max() * 1.3, 300)
    y_fit = np.polyval(coeff, np.log(x_fit))
    r2    = float(np.corrcoef(lx, ys)[0, 1] ** 2)

    ax.plot(x_fit, y_fit, "--", color="gray", linewidth=1.5, alpha=0.85,
            label=f"Trend (log-linear, R²={r2:.3f})", zorder=3)

    for x_val, y_val, c_name in zip(xs, ys, names):
        cname_en = _CUISINE_EN.get(c_name, c_name)
        color    = _CUISINE_COLORS[cname_en]
        ax.scatter([x_val], [y_val], color=color, s=110, zorder=6,
                   edgecolors="white", linewidths=1.2)
        ax.annotate(cname_en, (x_val, y_val), xytext=(7, 5),
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
            "More KG menus -> lower f4\n(better preference coverage)",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="dimgray",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

    plt.tight_layout()
    path = out_dir / "plot_interp2_g2_vs_g3.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 2] Saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Figure 3: KG structure visualization
# ──────────────────────────────────────────────────────────────────────────────

def _build_kg_cuisine_local(
    all_foods: list[dict],
    cuisine: str,
    weight: float,
) -> object:
    """Build KG with cuisine preference (local copy, no extra imports)."""
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
    """Draw KG radial layout in one panel."""
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
    """Korean Cuisine KG: Day 0 vs Day 7 — NetworkX radial layout."""
    from experiment.core.loader import FoodDataLoader
    from experiment.core.nutrition import NutritionProfile
    from experiment.core.daily_exp3_problem import DailyExp3Problem
    from experiment.core.kg_manager import make_menu_id
    from experiment.tools.simulate_kg import _run_one_day

    print("  [Figure 3] Loading Supabase data...")
    loader     = FoodDataLoader.from_supabase()
    cats       = loader.get_category_lists()
    mains      = cats["MAIN"]
    sides_soup = cats["SIDE_SOUP"]
    drinks     = cats["DRINK"]
    snacks     = cats.get("SNACK", [])
    all_foods  = mains + sides_soup + drinks + snacks

    cuisine = "한식"
    weight  = 1.3

    # ── Day 0 KG ─────────────────────────────────────────────────────────────
    kg_day0 = _build_kg_cuisine_local(all_foods, cuisine, weight)

    korean_mids = [
        node for node, attrs in kg_day0.G.nodes(data=True)
        if attrs.get("type") == "menu" and attrs.get("cuisine") == cuisine
    ]
    random.seed(42)
    n_sample    = min(40, len(korean_mids))
    sample_mids = random.sample(korean_mids, n_sample)
    print(f"  [Figure 3] Korean cuisine: {len(korean_mids)} menus, sampling {n_sample}")

    # ── Day 7 KG — lightweight re-simulation (pop=30, gen=30) ────────────────
    print("  [Figure 3] Rebuilding Day 7 KG state (pop=30, gen=30) ...")
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

    # ── Visualization ─────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"Knowledge Graph Structure — Korean Cuisine (pref={weight})  "
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
        Patch(color="#27ae60",         label=f"pref={weight} (cuisine init, not yet eaten)"),
        Patch(color=(0.9, 0.28, 0.18), label="Eaten most recently (high decay)"),
        Patch(color=(0.9, 0.48, 0.24), label="Eaten earlier (partial decay)"),
        Patch(color="#bdc3c7",         label="Default pref (not in cuisine)"),
    ]
    fig.legend(handles=legend_items, loc="lower center",
               ncol=2, fontsize=9, bbox_to_anchor=(0.5, -0.04))

    plt.tight_layout()
    path = out_dir / "plot_kg_visualization.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 3] Saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Figure 4: G3 per-cuisine convergence quality (GD+ and IGD+)
# ──────────────────────────────────────────────────────────────────────────────

def plot_g3_cuisine(out_dir: Path) -> None:
    """G3 per-cuisine convergence quality — GD+ and IGD+ side by side (n=30 each).

    Panel (a): GD+ per cuisine — overall convergence accuracy
    Panel (b): IGD+ per cuisine — Pareto front coverage quality
                (shows extreme variance for low-KG-coverage cuisines)
    """
    # Collect G3 data per cuisine
    g3_gdp:  dict[str, list] = {}
    g3_igdp: dict[str, list] = {}
    g3_hv:   dict[str, list] = {}
    kg_counts: dict[str, int] = {}

    summary = _load_cuisine_summary()
    for row in summary:
        kg_counts[row["cuisine"]] = row["kg_menu_count"]

    for c in CUISINES:
        rows = _load_perrun_metrics(c)
        g3rows = [r for r in rows if r["group"] == "G3"]
        g3_gdp[c]  = [r["GD+"]  for r in g3rows if not np.isnan(r["GD+"])]
        g3_igdp[c] = [r["IGD+"] for r in g3rows if not np.isnan(r["IGD+"])]
        g3_hv[c]   = [r["HV"]   for r in g3rows if not np.isnan(r["HV"])]

    x_pos    = np.arange(len(CUISINES))
    x_labels = [f"{_CUISINE_EN[c]}\n(n_menu={kg_counts.get(c,'?')})" for c in CUISINES]
    colors   = [_CUISINE_COLORS[_CUISINE_EN[c]] for c in CUISINES]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        "G3 (R-NSGA-II + KG) — Per-Cuisine Convergence Quality  |  4-objective, n=30 runs each",
        fontsize=11, fontweight="bold", y=1.03,
    )

    metrics_panels = [
        (axes[0], g3_gdp,  "GD+ (↓)",  "(a) GD+ per Cuisine"),
        (axes[1], g3_igdp, "IGD+ (↓)", "(b) IGD+ per Cuisine"),
    ]

    for ax, data_dict, ylabel, title in metrics_panels:
        data_list = [data_dict[c] for c in CUISINES]

        bp = ax.boxplot(
            data_list,
            positions=x_pos,
            widths=0.5,
            patch_artist=True,
            showfliers=True,
            flierprops=dict(marker="o", markersize=4, alpha=0.5,
                            markeredgewidth=0.5),
            medianprops=dict(color="black", linewidth=2.0),
            whiskerprops=dict(linewidth=1.2),
            capprops=dict(linewidth=1.2),
        )
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)

        # Overlay individual run dots (jittered)
        random.seed(7)
        for xi, (c, vals) in enumerate(zip(CUISINES, data_list)):
            color = _CUISINE_COLORS[_CUISINE_EN[c]]
            jitter = np.array([xi + (random.random() - 0.5) * 0.3
                                for _ in vals])
            ax.scatter(jitter, vals, color=color, s=18, alpha=0.55,
                       zorder=5, edgecolors="none")

        # Mean marker
        for xi, vals in enumerate(data_list):
            if vals:
                ax.scatter([xi], [float(np.mean(vals))],
                           marker="D", color="white", s=45, zorder=7,
                           edgecolors="black", linewidths=1.0)

        ax.set_xlim(-0.7, len(CUISINES) - 0.3)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Stats annotation per cuisine (median ± IQR)
        for xi, (c, vals) in enumerate(zip(CUISINES, data_list)):
            if not vals:
                continue
            med = float(np.median(vals))
            q1  = float(np.percentile(vals, 25))
            q3  = float(np.percentile(vals, 75))
            ax.text(xi, ax.get_ylim()[1] * 0.97,
                    f"{med:.3f}",
                    ha="center", va="top", fontsize=7.5, color="black",
                    fontweight="bold")

        ax.text(0.98, 0.98,
                "Diamond = mean\nNumber = median",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color="dimgray",
                bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

    # Note about 4-objective space
    fig.text(0.5, -0.03,
             "Note: G3 uses 4-objective space (f1 nutrition, f2 price, f3 variety, f4 KG preference)."
             "  Higher KG menu count -> more constrained Pareto front -> lower IGD+ variance.",
             ha="center", fontsize=8.5, color="dimgray", style="italic")

    plt.tight_layout()
    path = out_dir / "plot_g3_per_cuisine.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 4] Saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Step2 experiment results — 3-figure visualization")
    parser.add_argument("--no_kg", action="store_true",
                        help="Skip KG visualization (Figure 1+2 only, no Supabase needed)")
    args = parser.parse_args()

    if not HAS_MPL:
        print("ERROR: matplotlib not installed — pip install matplotlib")
        sys.exit(1)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[Figure 1] G1 vs G2 algorithm comparison...")
    plot_interp1(_OUT_DIR)

    print("[Figure 2] G3 KG integration effect...")
    plot_interp2(_OUT_DIR)

    print("[Figure 4] G3 per-cuisine convergence quality...")
    plot_g3_cuisine(_OUT_DIR)

    if not args.no_kg:
        print("[Figure 3] KG structure visualization (Supabase connection required)...")
        plot_kg_visualization(_OUT_DIR)
    else:
        print("[Figure 3] --no_kg flag: skipping KG visualization")

    print(f"\nDone. Output directory: {_OUT_DIR}")


if __name__ == "__main__":
    main()
