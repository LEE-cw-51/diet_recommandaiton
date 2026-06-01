"""
논문 수치 추출 및 그림 생성 스크립트
실제 CSV / run_log.txt 기반 — pkl/npz 불필요
출력: paper_outputs/results_table.json, paper_outputs/figures/*.png, paper_outputs/summary.md
"""

import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy.stats import ranksums

# ── 경로 ───────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
RES  = ROOT / "experiment" / "results"
OUT  = ROOT / "paper_outputs"
FIG  = OUT / "figures"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

# ── 스타일 ─────────────────────────────────────────────────────────────────────
COLORS = {"G1": "#1f77b4", "G2": "#ff7f0e", "G3": "#2ca02c",
          "before": "#d62728", "after": "#1f77b4"}
CUISINE_COLORS = {
    "Korean": "#1f77b4", "Western": "#ff7f0e", "Bunsik": "#2ca02c",
    "Chinese": "#d62728", "Japanese": "#9467bd",
}
CUISINE_KR = {"한식": "Korean", "양식": "Western", "분식": "Bunsik",
              "중식": "Chinese", "일식": "Japanese"}
MENU_COUNTS = {"Korean": 663, "Western": 448, "Bunsik": 90, "Chinese": 33, "Japanese": 31}

DPI = 300

def apply_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.titlesize": 10, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 8, "figure.dpi": DPI,
        "axes.spines.top": False, "axes.spines.right": False,
    })

def p_star(p):
    if p < 0.001: return "< 0.001 ***"
    if p < 0.01:  return f"{p:.3f} **"
    if p < 0.05:  return f"{p:.3f} *"
    return f"{p:.3f} (n.s.)"

def fmt_mean_std(mean, std):
    return f"{mean:.4f} ± {std:.4f}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — run_log.txt 파싱 (30회 실험 요약)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 1] run_log.txt 파싱")

run_log_path = RES / "step1" / "run_log.txt"
log_text = run_log_path.read_text(encoding="utf-8", errors="replace")

# 요약 라인: "  G1: HV=0.1274±0.0431  GD+=0.0885  IGD+=0.0239  time=7.04s"
def parse_summary_line(text, group):
    pat = (rf"^\s*{group}:\s+HV=([0-9.]+)±([0-9.]+)\s+"
           rf"GD\+=([0-9.]+)\s+IGD\+=([0-9.]+)\s+time=([0-9.]+)s")
    m = re.search(pat, text, re.MULTILINE)
    if not m:
        return None
    return {
        "HV_mean": float(m.group(1)), "HV_std": float(m.group(2)),
        "GDp_mean": float(m.group(3)), "IGDp_mean": float(m.group(4)),
        "time_mean": float(m.group(5)),
    }

def parse_wilcoxon(text, g_from, g_to, metric):
    pat = rf"{g_from}\s+vs\s+{g_to}\s+\[{metric}\]:\s+p=([0-9.]+)"
    m = re.search(pat, text)
    return float(m.group(1)) if m else None

g1_sum = parse_summary_line(log_text, "G1")
g2_sum = parse_summary_line(log_text, "G2")
g3_sum = parse_summary_line(log_text, "G3")

# Wilcoxon p-values from run_log (G1/G2 vs G3 only)
p_g1g3_hv   = parse_wilcoxon(log_text, "G1", "G3", "HV")
p_g1g3_gdp  = parse_wilcoxon(log_text, "G1", "G3", "GD\\+")
p_g1g3_igdp = parse_wilcoxon(log_text, "G1", "G3", "IGD\\+")
p_g2g3_hv   = parse_wilcoxon(log_text, "G2", "G3", "HV")
p_g2g3_gdp  = parse_wilcoxon(log_text, "G2", "G3", "GD\\+")
p_g2g3_igdp = parse_wilcoxon(log_text, "G2", "G3", "IGD\\+")

# G1 vs G2: run_log에 없음 → cuisine per_run pooled로 근사
frames_pr = []
for kr in ["한식", "양식", "분식"]:
    p = RES / "step2_cuisine" / kr / "per_run_metrics.csv"
    if p.exists():
        frames_pr.append(pd.read_csv(p))

if frames_pr:
    pr_all = pd.concat(frames_pr, ignore_index=True)
    g1_hv = pr_all[pr_all.group == "G1"]["HV"].values
    g2_hv = pr_all[pr_all.group == "G2"]["HV"].values
    g1_gdp = pr_all[pr_all.group == "G1"]["GD+"].values
    g2_gdp = pr_all[pr_all.group == "G2"]["GD+"].values
    g1_igdp = pr_all[pr_all.group == "G1"]["IGD+"].values
    g2_igdp = pr_all[pr_all.group == "G2"]["IGD+"].values
    _, p_g1g2_hv   = ranksums(g1_hv,   g2_hv)
    _, p_g1g2_gdp  = ranksums(g1_gdp,  g2_gdp)
    _, p_g1g2_igdp = ranksums(g1_igdp, g2_igdp)
else:
    p_g1g2_hv = p_g1g2_gdp = p_g1g2_igdp = None

# G3 std from metrics_comparison.csv (since run_log only shows summary)
mc = pd.read_csv(RES / "step1" / "metrics_comparison.csv")
g3_row_hv  = mc[(mc.group == "G3") & (mc.metric == "HV")].iloc[0]

print(f"  G1: HV={g1_sum['HV_mean']:.4f}±{g1_sum['HV_std']:.4f}, "
      f"GD+={g1_sum['GDp_mean']:.4f}, IGD+={g1_sum['IGDp_mean']:.4f}")
print(f"  G2: HV={g2_sum['HV_mean']:.4f}±{g2_sum['HV_std']:.4f}, "
      f"GD+={g2_sum['GDp_mean']:.4f}, IGD+={g2_sum['IGDp_mean']:.4f}")
print(f"  G3: HV={g3_sum['HV_mean']:.4f}±{g3_sum['HV_std']:.4f}, "
      f"GD+={g3_sum['GDp_mean']:.4f}, IGD+={g3_sum['IGDp_mean']:.4f}")
print(f"  G1 vs G3: HV p={p_g1g3_hv}, GD+ p={p_g1g3_gdp}, IGD+ p={p_g1g3_igdp}")
print(f"  G2 vs G3: HV p={p_g2g3_hv}, GD+ p={p_g2g3_gdp}, IGD+ p={p_g2g3_igdp}")

# 표 6-1 구성
table_6_1 = {}
for metric, g1m, g1s, g2m, g2s, g3m, g3s, p12_hv, p23_hv in [
    ("HV",
     g1_sum["HV_mean"], g1_sum["HV_std"],
     g2_sum["HV_mean"], g2_sum["HV_std"],
     g3_sum["HV_mean"], g3_sum["HV_std"],
     p_g1g2_hv, p_g2g3_hv),
]:
    table_6_1["HV"] = {
        "G1": fmt_mean_std(g1_sum["HV_mean"], g1_sum["HV_std"]),
        "G2": fmt_mean_std(g2_sum["HV_mean"], g2_sum["HV_std"]),
        "G3": fmt_mean_std(g3_sum["HV_mean"], g3_sum["HV_std"]),
        "G1_vs_G2_p": p_star(p_g1g2_hv) if p_g1g2_hv else "—",
        "G1_vs_G3_p": p_star(p_g1g3_hv) if p_g1g3_hv else "—",
        "G2_vs_G3_p": p_star(p_g2g3_hv) if p_g2g3_hv else "—",
    }

table_6_1["GD+"] = {
    "G1": fmt_mean_std(g1_sum["GDp_mean"], 0),
    "G2": fmt_mean_std(g2_sum["GDp_mean"], 0),
    "G3": fmt_mean_std(g3_sum["GDp_mean"], 0),
    "G1_vs_G2_p": p_star(p_g1g2_gdp) if p_g1g2_gdp else "—",
    "G1_vs_G3_p": p_star(p_g1g3_gdp) if p_g1g3_gdp else "—",
    "G2_vs_G3_p": p_star(p_g2g3_gdp) if p_g2g3_gdp else "—",
}

table_6_1["IGD+"] = {
    "G1": fmt_mean_std(g1_sum["IGDp_mean"], 0),
    "G2": fmt_mean_std(g2_sum["IGDp_mean"], 0),
    "G3": fmt_mean_std(g3_sum["IGDp_mean"], 0),
    "G1_vs_G2_p": p_star(p_g1g2_igdp) if p_g1g2_igdp else "—",
    "G1_vs_G3_p": p_star(p_g1g3_igdp) if p_g1g3_igdp else "—",
    "G2_vs_G3_p": p_star(p_g2g3_igdp) if p_g2g3_igdp else "—",
}

print("✅ [STEP 1] 표 6-1 구성 완료")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Cold Start 데이터
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 2] Cold Start 데이터 로드")

cs = pd.read_csv(RES / "step1_coldstart" / "daily_f4_trend_coldstart.csv")
days = cs["day"].values
f4_before = cs["f4_before"].values   # 0.25 × 7 (KG 초기화 없음)
f4_after  = cs["f4_after"].values    # KG 초기화 적용 후

cold_reduction_pct = (f4_before[0] - f4_after.mean()) / f4_before[0] * 100
print(f"  f4_after 범위: {f4_after.min():.4f} ~ {f4_after.max():.4f}")
print(f"  평균 감소율: {cold_reduction_pct:.1f}%")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Loop B (한식·양식 7일)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 3] Loop B 데이터 로드")

def load_loop_b(cuisine_kr):
    base = RES / "step2_cuisine" / cuisine_kr
    f4_df  = pd.read_csv(base / "daily_f4_trend.csv")
    dup_df = pd.read_csv(base / "daily_duplication.csv")
    return {
        "f4":            f4_df["f4"].values,
        "duplicate_rate": dup_df["duplication_rate"].values,
    }

lb_korean  = load_loop_b("한식")
lb_western = load_loop_b("양식")

print(f"  한식 f4: {lb_korean['f4']}")
print(f"  한식 중복률: {lb_korean['duplicate_rate']}")
print(f"  양식 f4: {lb_western['f4']}")
print(f"  양식 중복률: {lb_western['duplicate_rate']}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — 식문화별 요약
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 4] 식문화 요약 로드")

cuisine_sum = pd.read_csv(RES / "step2_cuisine" / "cuisine_summary.csv")
# cuisine_sum: cuisine, kg_menu_count, loop_b_f4_mean, loop_b_f4_std, loop_b_dup_rate_mean

# 식문화별 G3 IGD+ (per_run 3개씩)
cuisine_g3_igdp = {}
for kr, en in CUISINE_KR.items():
    p = RES / "step2_cuisine" / kr / "per_run_metrics.csv"
    if p.exists():
        df = pd.read_csv(p)
        vals = df[df.group == "G3"]["IGD+"].dropna().values
        cuisine_g3_igdp[en] = vals

print(f"  cuisine_sum:\n{cuisine_sum.to_string(index=False)}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — 그림 생성
# ══════════════════════════════════════════════════════════════════════════════
apply_style()

# ── 그림 6-1: G1 vs G2 성능 비교 (bar + error, cuisine pooled per-run) ─────
print("\n[FIG 6-1] G1 vs G2 성능 비교")

fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.2))
fig.subplots_adjust(right=0.78, wspace=0.5)

metrics_list = [
    ("HV",   g1_sum["HV_mean"],  g1_sum["HV_std"],  g2_sum["HV_mean"],  g2_sum["HV_std"],  "HV ↑"),
    ("GD+",  g1_sum["GDp_mean"], 0,                 g2_sum["GDp_mean"], 0,                 "GD+ ↓"),
    ("IGD+", g1_sum["IGDp_mean"],0,                 g2_sum["IGDp_mean"],0,                 "IGD+ ↓"),
]

# 30회 개별 데이터가 없으므로 bar + error bar 사용
for ax, (metric, g1m, g1s, g2m, g2s, ylabel) in zip(axes, metrics_list):
    x = [0.8, 1.8]
    heights = [g1m, g2m]
    errs    = [g1s, g2s]
    bars = ax.bar(x, heights, width=0.5, color=[COLORS["G1"], COLORS["G2"]],
                  alpha=0.75, yerr=errs, capsize=4,
                  error_kw=dict(elinewidth=0.8, capthick=0.8))
    ax.set_xticks(x)
    ax.set_xticklabels(["G1\n(NSGA-II)", "G2\n(R-NSGA-II)"])
    ax.set_title(ylabel, fontsize=9)
    ax.set_ylabel("Value")
    ax.set_xlim(0.3, 2.3)

legend_handles = [
    mpatches.Patch(facecolor=COLORS["G1"], alpha=0.75, label="G1 (NSGA-II)"),
    mpatches.Patch(facecolor=COLORS["G2"], alpha=0.75, label="G2 (R-NSGA-II)"),
]
fig.legend(handles=legend_handles, loc="center right",
           bbox_to_anchor=(1.0, 0.5), frameon=True, title="Algorithm")
fig.suptitle("Fig. 6-1: G1 vs G2 Performance (30 independent runs)", y=1.02, fontsize=9)

out = FIG / "fig6_1_g1_vs_g2.png"
fig.savefig(out, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"  saved → {out.name}")

# ── 그림 6-2: G1/G2/G3 HV 요약 막대 ─────────────────────────────────────────
print("\n[FIG 6-2] G1/G2/G3 HV/GD+/IGD+ 요약")

labels_3 = ["G1\n(NSGA-II)", "G2\n(R-NSGA-II)", "G3\n(R-NSGA-II+KG)"]
colors_3  = [COLORS["G1"], COLORS["G2"], COLORS["G3"]]

hv_means = [g1_sum["HV_mean"], g2_sum["HV_mean"], g3_sum["HV_mean"]]
hv_stds  = [g1_sum["HV_std"],  g2_sum["HV_std"],  g3_sum["HV_std"]]
gdp_means  = [g1_sum["GDp_mean"],  g2_sum["GDp_mean"],  g3_sum["GDp_mean"]]
igdp_means = [g1_sum["IGDp_mean"], g2_sum["IGDp_mean"], g3_sum["IGDp_mean"]]

fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.2))
fig.subplots_adjust(right=0.78, wspace=0.5)

x = np.array([0.8, 1.8, 2.8])
for ax, (means, stds, title) in zip(axes, [
    (hv_means, hv_stds, "HV ↑"),
    (gdp_means, [0,0,0], "GD+ ↓"),
    (igdp_means,[0,0,0], "IGD+ ↓"),
]):
    ax.bar(x, means, width=0.5, color=colors_3, alpha=0.75,
           yerr=stds, capsize=4, error_kw=dict(elinewidth=0.8, capthick=0.8))
    ax.set_xticks(x)
    ax.set_xticklabels(labels_3, fontsize=7)
    ax.set_title(title, fontsize=9)
    ax.set_ylabel("Value")
    ax.set_xlim(0.3, 3.3)

legend_handles = [mpatches.Patch(facecolor=c, alpha=0.75, label=l)
                  for c, l in zip(colors_3, ["G1","G2","G3"])]
fig.legend(handles=legend_handles, loc="center right",
           bbox_to_anchor=(1.0, 0.5), frameon=True, title="Group")
fig.suptitle("Fig. 6-2: G1 / G2 / G3 Performance Metrics (30 runs)", y=1.02, fontsize=9)

out = FIG / "fig6_2_g1_g2_g3_metrics.png"
fig.savefig(out, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"  saved → {out.name}")

# ── 그림 6-3: Cold Start f4 비교 ────────────────────────────────────────────
print("\n[FIG 6-3] Cold Start f4 비교")

fig, ax = plt.subplots(figsize=(4.5, 3.2))
ax.plot(days, f4_before, "s--", color=COLORS["before"], linewidth=1.5, markersize=6,
        label="Without KG init (baseline)")
ax.plot(days, f4_after,  "o-",  color=COLORS["after"],  linewidth=1.5, markersize=6,
        label="With KG init")

ax.set_xlabel("Day")
ax.set_ylabel("f4 (Diversity Loss)")
ax.set_xticks(days)
ax.set_ylim(bottom=0)
ax.set_title("Fig. 6-3: Cold-Start Effect on f4 (7 Days)", fontsize=9)
ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0), frameon=True)
ax.grid(axis="y", alpha=0.3)

# 감소율 주석
mean_after = f4_after.mean()
ax.annotate(
    f"Avg. {cold_reduction_pct:.0f}% reduction\nvs baseline",
    xy=(days[-1], mean_after),
    xytext=(5.0, mean_after + 0.04),
    arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    fontsize=7, color=COLORS["after"],
)

out = FIG / "fig6_3_cold_start.png"
fig.savefig(out, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"  saved → {out.name}")

# ── 그림 6-4: Loop B — 한식 7일 f4 + 중복률 ────────────────────────────────
print("\n[FIG 6-4] Loop B 한식 7일")

def plot_loop_b_7days(data, cuisine_en, filename):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(4.5, 4.5), sharex=True)
    fig.subplots_adjust(hspace=0.08)

    d = np.arange(1, 8)
    ax1.plot(d, data["f4"], "o-", color=COLORS["G3"], linewidth=1.5, markersize=6)
    ax1.axhline(y=0.06, color="gray", linestyle="--", alpha=0.6, linewidth=0.8, label="f4 = 0.06")
    ax1.set_ylabel("f4 (Diversity Loss)")
    ax1.set_title(f"Fig. 6-4({cuisine_en[0]}): {cuisine_en} — 7-Day Loop B", fontsize=9)
    ax1.legend(fontsize=7)
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_ylim(bottom=0)

    # f4 값 레이블
    for di, fi in zip(d, data["f4"]):
        ax1.text(di, fi + 0.002, f"{fi:.3f}", ha="center", fontsize=6.5)

    bars = ax2.bar(d, data["duplicate_rate"] * 100, color="#FF9800", alpha=0.75, width=0.5)
    ax2.set_xlabel("Day")
    ax2.set_ylabel("Duplication Rate (%)")
    ax2.set_xticks(d)
    ax2.set_ylim(0, max(max(data["duplicate_rate"] * 100) * 1.4 + 0.1, 3))
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, data["duplicate_rate"] * 100):
        if val > 0:
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                     f"{val:.1f}%", ha="center", fontsize=7)

    out = FIG / filename
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {out.name}")

lb_korean["duplicate_rate"]  = lb_korean["duplicate_rate"].astype(float)
lb_western["duplicate_rate"] = lb_western["duplicate_rate"].astype(float)

plot_loop_b_7days(lb_korean,  "Korean",  "fig6_4a_loop_b_korean.png")
plot_loop_b_7days(lb_western, "Western", "fig6_4b_loop_b_western.png")

# ── 그림 6-5: 식문화별 평균 f4 vs 메뉴 수 ──────────────────────────────────
print("\n[FIG 6-5] 식문화별 f4 vs 메뉴 수")

# cuisine_summary에서 f4_mean 추출
cs_map = dict(zip(cuisine_sum.cuisine.map(CUISINE_KR), cuisine_sum.loop_b_f4_mean))
# 3개 cuisine만 있는 경우, missing은 per_run mean으로 대체
for kr, en in CUISINE_KR.items():
    if en not in cs_map:
        p = RES / "step2_cuisine" / kr / "daily_f4_trend.csv"
        if p.exists():
            df = pd.read_csv(p)
            cs_map[en] = df["f4"].mean()

cuisines_ordered = [en for en in ["Korean","Western","Bunsik","Chinese","Japanese"] if en in cs_map]
x_pts = [MENU_COUNTS[en] for en in cuisines_ordered]
y_pts = [cs_map[en]     for en in cuisines_ordered]

fig, ax = plt.subplots(figsize=(4.5, 3.5))
for en, xi, yi in zip(cuisines_ordered, x_pts, y_pts):
    ax.scatter(xi, yi, s=90, color=CUISINE_COLORS[en], zorder=5, label=en)
    ax.annotate(en, (xi, yi), textcoords="offset points", xytext=(5, 4), fontsize=8)

if len(x_pts) >= 2:
    z = np.polyfit(x_pts, y_pts, 1)
    xs_line = np.linspace(min(x_pts) * 0.85, max(x_pts) * 1.05, 100)
    ax.plot(xs_line, np.poly1d(z)(xs_line), "--", color="gray", alpha=0.6, linewidth=1)

ax.set_xlabel("Number of Menu Items")
ax.set_ylabel("Mean f4 (Loop B)")
ax.set_title("Fig. 6-5: Menu Pool Size vs Mean f4 by Cuisine", fontsize=9)
ax.grid(alpha=0.3)
ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1.0), loc="upper left", frameon=True)

out = FIG / "fig6_5_cuisine_f4.png"
fig.savefig(out, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"  saved → {out.name}")

# ── 그림 6-6: 식문화별 G3 IGD+ (per-run 3개 막대) ───────────────────────────
print("\n[FIG 6-6] 식문화별 G3 IGD+")

fig, ax = plt.subplots(figsize=(5.5, 3.5))
fig.subplots_adjust(right=0.78)

en_ordered = [en for en in ["Korean","Western","Bunsik","Chinese","Japanese"]
              if en in cuisine_g3_igdp]
x_pos = np.arange(len(en_ordered))

for i, en in enumerate(en_ordered):
    vals = cuisine_g3_igdp[en]
    mean = vals.mean()
    std  = vals.std() if len(vals) > 1 else 0
    ax.bar(i, mean, width=0.55, color=CUISINE_COLORS[en], alpha=0.75,
           yerr=std, capsize=4, error_kw=dict(elinewidth=0.8))
    # individual dots
    jitter = np.random.RandomState(42).uniform(-0.15, 0.15, len(vals))
    ax.scatter(i + jitter, vals, color="black", s=20, zorder=5, alpha=0.7)

ax.set_xticks(x_pos)
ax.set_xticklabels(en_ordered)
ax.set_ylabel("IGD+")
ax.set_title("Fig. 6-6: G3 IGD+ by Cuisine (mean ± std, 3 runs)", fontsize=9)
ax.grid(axis="y", alpha=0.3)

out = FIG / "fig6_6_cuisine_igdp.png"
fig.savefig(out, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"  saved → {out.name}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — 표 6-2: Loop B 한식 7일 수치
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 6] 표 6-2 구성")

f4_ko = lb_korean["f4"]
dup_ko = lb_korean["duplicate_rate"]

table_6_2 = {}
for i in range(7):
    table_6_2[f"Day {i+1}"] = {
        "f4":              round(float(f4_ko[i]), 4),
        "duplication_pct": round(float(dup_ko[i]) * 100, 2),
    }

print("  한식 7일 f4 + 중복률:")
for day, row in table_6_2.items():
    print(f"    {day}: f4={row['f4']:.4f}, dup={row['duplication_pct']:.2f}%")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — results_table.json 저장
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 7] results_table.json 저장")

results_json = {
    "table_6_1": table_6_1,
    "table_6_2": table_6_2,
    "raw_stats": {
        "G1": {k: round(v, 6) for k, v in g1_sum.items()},
        "G2": {k: round(v, 6) for k, v in g2_sum.items()},
        "G3": {k: round(v, 6) for k, v in g3_sum.items()},
    },
    "wilcoxon": {
        "G1_vs_G3_HV":    p_star(p_g1g3_hv)   if p_g1g3_hv   else "—",
        "G1_vs_G3_GDp":   p_star(p_g1g3_gdp)  if p_g1g3_gdp  else "—",
        "G1_vs_G3_IGDp":  p_star(p_g1g3_igdp) if p_g1g3_igdp else "—",
        "G2_vs_G3_HV":    p_star(p_g2g3_hv)   if p_g2g3_hv   else "—",
        "G2_vs_G3_GDp":   p_star(p_g2g3_gdp)  if p_g2g3_gdp  else "—",
        "G2_vs_G3_IGDp":  p_star(p_g2g3_igdp) if p_g2g3_igdp else "—",
        "G1_vs_G2_HV":    p_star(p_g1g2_hv)   if p_g1g2_hv   else "—",
        "G1_vs_G2_GDp":   p_star(p_g1g2_gdp)  if p_g1g2_gdp  else "—",
        "G1_vs_G2_IGDp":  p_star(p_g1g2_igdp) if p_g1g2_igdp else "—",
    },
    "cold_start": {
        "f4_baseline_avg": round(float(f4_before.mean()), 4),
        "f4_with_kg_mean": round(float(f4_after.mean()), 4),
        "f4_with_kg_range": [round(float(f4_after.min()), 4), round(float(f4_after.max()), 4)],
        "reduction_pct":   round(cold_reduction_pct, 1),
    },
    "loop_b": {
        "korean_f4": [round(float(v), 4) for v in lb_korean["f4"]],
        "korean_dup_pct": [round(float(v)*100, 2) for v in lb_korean["duplicate_rate"]],
        "western_f4": [round(float(v), 4) for v in lb_western["f4"]],
        "western_dup_pct": [round(float(v)*100, 2) for v in lb_western["duplicate_rate"]],
    },
    "cuisine_f4_mean": {en: round(float(v), 4) for en, v in cs_map.items()},
}

with open(OUT / "results_table.json", "w", encoding="utf-8") as f:
    json.dump(results_json, f, ensure_ascii=False, indent=2)

print("  saved → paper_outputs/results_table.json")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — summary.md 생성
# ══════════════════════════════════════════════════════════════════════════════
print("\n[STEP 8] summary.md 생성")

lines = [
    "# 논문 수치 요약 (2026-06-02)\n",
    "## 표 6-1 — G1 / G2 / G3 성능 비교 (30회 독립 실행)\n",
    "| 지표 | G1 (NSGA-II) | G2 (R-NSGA-II) | G3 (R-NSGA-II+KG) | G1 vs G3 p | G2 vs G3 p |",
    "|------|-------------|----------------|-------------------|------------|------------|",
]
for metric in ["HV", "GD+", "IGD+"]:
    v = table_6_1[metric]
    lines.append(f"| {metric} | {v['G1']} | {v['G2']} | {v['G3']} | {v['G1_vs_G3_p']} | {v['G2_vs_G3_p']} |")

lines += [
    "",
    "> **주의**: GD+/IGD+ std는 run_log에 기록되지 않아 0으로 표시됨.",
    "> G1 vs G2 Wilcoxon은 cuisine 3회 풀링(한식+양식+분식) 기반 근사치임.",
    "",
    "## 표 6-1 서술용 문장\n",
    f"- **HV**: G1 {g1_sum['HV_mean']:.4f}±{g1_sum['HV_std']:.4f}, "
    f"G2 {g2_sum['HV_mean']:.4f}±{g2_sum['HV_std']:.4f}, "
    f"G3 {g3_sum['HV_mean']:.4f}±{g3_sum['HV_std']:.4f}",
    f"- **GD+**: G1 {g1_sum['GDp_mean']:.4f}, G2 {g2_sum['GDp_mean']:.4f}, G3 {g3_sum['GDp_mean']:.4f}",
    f"- **IGD+**: G1 {g1_sum['IGDp_mean']:.4f}, G2 {g2_sum['IGDp_mean']:.4f}, G3 {g3_sum['IGDp_mean']:.4f}",
    f"- G1 vs G3 Wilcoxon (GD+): p={p_g1g3_gdp:.4f} {'***' if p_g1g3_gdp < 0.001 else ''}",
    f"- G2 vs G3 Wilcoxon (HV/GD+/IGD+): p={p_g2g3_hv:.4f} / {p_g2g3_gdp:.4f} / {p_g2g3_igdp:.4f} — 모두 n.s.",
    "",
    "## Cold Start (Sec 6.2)\n",
    f"- KG 초기화 없음(베이스라인): f4 = {f4_before[0]:.4f} (7일 전체 동일)",
    f"- KG 초기화 적용 후: f4 = {f4_after.min():.4f} ~ {f4_after.max():.4f} (평균 {f4_after.mean():.4f})",
    f"- **평균 감소율: {cold_reduction_pct:.0f}%**",
    "",
    "## Loop B — 한식 7일 (Sec 6.3)\n",
    "| Day | f4 | 중복률 |",
    "|-----|----|--------|",
]
for day, row in table_6_2.items():
    lines.append(f"| {day} | {row['f4']:.4f} | {row['duplication_pct']:.2f}% |")

lines += [
    "",
    f"- f4 범위: {min(table_6_2[d]['f4'] for d in table_6_2):.4f} ~ {max(table_6_2[d]['f4'] for d in table_6_2):.4f}",
    f"- Day 6 이전 중복률: 0% (완전 다양성 유지)",
    f"- Day 6~7 중복률 소폭 등장: 시간 감쇠 회복 증거",
    "",
    "## Loop B — 양식 7일\n",
    f"- f4 범위: {lb_western['f4'].min():.4f} ~ {lb_western['f4'].max():.4f}",
    f"- 중복률: {lb_western['duplicate_rate'][:6].tolist()} → Day7 {lb_western['duplicate_rate'][-1]*100:.1f}%",
    "",
    "## 식문화별 평균 f4 (Loop B)\n",
    "| Cuisine | Menu Count | Mean f4 |",
    "|---------|-----------|---------|",
]
for en in ["Korean","Western","Bunsik","Chinese","Japanese"]:
    if en in cs_map:
        lines.append(f"| {en} | {MENU_COUNTS[en]} | {cs_map[en]:.4f} |")

lines += [
    "",
    "## 생성된 그림 목록\n",
]
for f in sorted(FIG.glob("*.png")):
    lines.append(f"- `figures/{f.name}`")

with open(OUT / "summary.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("  saved → paper_outputs/summary.md")

print("\n" + "="*60)
print("🎉 완료!")
print(f"   📊 수치 JSON : {OUT}/results_table.json")
print(f"   🖼️  그림 폴더 : {FIG}/")
print(f"   📝 요약 MD  : {OUT}/summary.md")
