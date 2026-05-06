# -*- coding: utf-8 -*-
"""분석 및 시각화 스크립트.

DailyExp2 (3목적) vs DailyExp3 (4목적) 비교 분석.
민감도 분석 결과 시각화.

Usage:
    python analyze_results.py [--exp3-path /path/to/exp3/results]

Environment Variables:
    DAILY_EXP3_OUTPUT_DIR: Override EXP3 results directory
"""

import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats
from glob import glob


def find_exp3_results():
    """자동으로 exp3 결과 디렉토리 검색 (most recent first)."""
    RESULTS_DIR = Path(__file__).parent / "output"

    # 패턴: daily_exp3_rnsga2_base_*
    pattern = str(RESULTS_DIR / "daily_exp3_rnsga2_base_*")
    matches = sorted(glob(pattern), reverse=True)  # 최신순

    if matches:
        return Path(matches[0])
    return None


def resolve_exp3_path():
    """
    EXP3 결과 경로를 우선순위에 따라 해석:
    1. CLI argument --exp3-path
    2. 환경변수 DAILY_EXP3_OUTPUT_DIR
    3. 자동 검색 (experiment/results/output/ 내 일반 파일)
    4. None (스킵)
    """
    # CLI 인자 파싱
    parser = argparse.ArgumentParser(description="분석 및 시각화 스크립트")
    parser.add_argument("--exp3-path", type=str, default=None,
                        help="EXP3 결과 디렉토리 경로 (예: /path/to/daily_exp3_rnsga2_base_20260506_193432)")
    args, _ = parser.parse_known_args()

    # 1. CLI 인자
    if args.exp3_path:
        exp3_path = Path(args.exp3_path)
        if exp3_path.exists():
            return exp3_path
        print(f"⚠️ CLI 인자로 지정한 EXP3 경로 없음: {exp3_path}")
        return None

    # 2. 환경변수
    if "DAILY_EXP3_OUTPUT_DIR" in os.environ:
        exp3_path = Path(os.environ["DAILY_EXP3_OUTPUT_DIR"])
        if exp3_path.exists():
            return exp3_path
        print(f"⚠️ 환경변수 DAILY_EXP3_OUTPUT_DIR 경로 없음: {exp3_path}")
        return None

    # 3. 자동 검색
    exp3_path = find_exp3_results()
    if exp3_path:
        print(f"📍 EXP3 결과 자동 검색: {exp3_path}")
        return exp3_path

    print("⚠️ EXP3 결과를 찾을 수 없습니다. --exp3-path를 지정하거나 DAILY_EXP3_OUTPUT_DIR 환경변수를 설정하세요.")
    return None


# 설정
RESULTS_DIR = Path(__file__).parent / "output"
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# EXP3 경로 해석
EXP3_PATH = resolve_exp3_path()

# 결과 경로 정의
RESULTS_PATHS = {
    "exp2": RESULTS_DIR / "daily_exp2_nsga2_base_20260506_193745",
    "high_carb": RESULTS_DIR / "exp1_nsga2_high_carb_20260506_194045",
    "low_carb": RESULTS_DIR / "exp1_nsga2_low_carb_20260506_194314",
    "mid_balanced": RESULTS_DIR / "exp1_nsga2_mid_balanced_20260506_194545",
    "low_protein": RESULTS_DIR / "exp1_nsga2_low_protein_20260506_194820",
}

# EXP3 경로가 있으면 추가
if EXP3_PATH:
    # EXP3 결과 디렉토리 자동 검색 (가장 최신)
    exp3_result_dirs = sorted(glob(str(EXP3_PATH.parent / "daily_exp3_rnsga2_base_*")), reverse=True)
    if exp3_result_dirs:
        RESULTS_PATHS["exp3"] = Path(exp3_result_dirs[0])
    else:
        exp3_result_dir = EXP3_PATH / "daily_exp3_rnsga2_base_*"
        matches = sorted(glob(str(exp3_result_dir)), reverse=True)
        if matches:
            RESULTS_PATHS["exp3"] = Path(matches[0])

# ============================================================================
# 데이터 로딩
# ============================================================================

def load_summary(path):
    """결과 디렉토리에서 runs_summary.csv 로드."""
    summary_file = path / "runs_summary.csv"
    if not summary_file.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_file}")
    return pd.read_csv(summary_file)

print("📊 결과 로딩 중...")
data = {}
for name, path in RESULTS_PATHS.items():
    try:
        data[name] = load_summary(path)
        print(f"  {name}: {len(data[name])} runs")
    except FileNotFoundError as e:
        print(f"  ⚠️ {name}: {e}")

# ============================================================================
# 1. Box Plot: GD/IGD/HV/Spread (Exp2 vs Exp3)
# ============================================================================

if "exp3" in data and "exp2" in data:
    print("\n📈 생성 중: box_plot_comparison.png")
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle("DailyExp2 (3-obj) vs DailyExp3 (4-obj) 비교", fontsize=14, fontweight='bold')

    metrics = ["GD", "IGD", "HV", "Spread"]
    ax_list = axes.flatten()

    for idx, metric in enumerate(metrics):
        ax = ax_list[idx]

        box_data = [
            data["exp2"][metric].values,
            data["exp3"][metric].values
        ]

        bp = ax.boxplot(box_data, labels=["Exp2 (NSGA-II)", "Exp3 (R-NSGA-II)"],
                         patch_artist=True)

        # 색상
        colors = ['lightblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)

        ax.set_ylabel(metric, fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

        # 평균값 텍스트 추가
        mean_exp2 = data["exp2"][metric].mean()
        mean_exp3 = data["exp3"][metric].mean()
        ax.text(1, ax.get_ylim()[1]*0.95, f"{mean_exp2:.4f}", ha='center', fontsize=9)
        ax.text(2, ax.get_ylim()[1]*0.95, f"{mean_exp3:.4f}", ha='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "box_plot_comparison.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ 저장: {FIGURES_DIR / 'box_plot_comparison.png'}")
else:
    if "exp3" not in data:
        print("\n⚠️  box_plot_comparison.png 생성 스킵 (EXP3 결과 없음)")
    else:
        print("\n⚠️  box_plot_comparison.png 생성 스킵 (EXP2 결과 없음)")

# ============================================================================
# 2. Pareto Scatter: 2D 투영 (Exp3)
# ============================================================================

print("\n📈 생성 중: pareto_scatter_exp3.png")

# Exp3의 ref_pareto_front.csv 로드
ref_pf_file = None
if "exp3" in RESULTS_PATHS:
    ref_pf_file = RESULTS_PATHS["exp3"] / "ref_pareto_front.csv"

if ref_pf_file and ref_pf_file.exists():
    ref_pf = pd.read_csv(ref_pf_file)

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle("DailyExp3 기준 Pareto Front (30회 합집합)", fontsize=14, fontweight='bold')

    # 2D 투영: f1 vs f3, f1 vs f4, f2 vs f3, f2 vs f4
    projections = [
        ("f1", "f3", axes[0, 0]),
        ("f1", "f4", axes[0, 1]),
        ("f2", "f3", axes[1, 0]),
        ("f2", "f4", axes[1, 1]),
    ]

    for fx, fy, ax in projections:
        if fx in ref_pf.columns and fy in ref_pf.columns:
            ax.scatter(ref_pf[fx], ref_pf[fy], alpha=0.6, s=30, color='darkblue')
            ax.set_xlabel(fx, fontweight='bold')
            ax.set_ylabel(fy, fontweight='bold')
            ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "pareto_scatter_exp3.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ 저장: {FIGURES_DIR / 'pareto_scatter_exp3.png'}")
else:
    print(f"  ⚠️ ref_pareto_front.csv 없음")

# ============================================================================
# 3. Bar Plot: 평균 Pareto 크기 비교
# ============================================================================

if "exp2" in data and "exp3" in data:
    print("\n📈 생성 중: bar_pareto_size.png")

    fig, ax = plt.subplots(figsize=(10, 6))

    names = ["Exp2", "Exp3"]
    pf_sizes = [
        data["exp2"]["n_pareto"].mean(),
        data["exp3"]["n_pareto"].mean()
    ]
    pf_stds = [
        data["exp2"]["n_pareto"].std(),
        data["exp3"]["n_pareto"].std()
    ]

    x = np.arange(len(names))
    colors = ['lightblue', 'lightcoral']

    bars = ax.bar(x, pf_sizes, yerr=pf_stds, capsize=10, color=colors,
                   edgecolor='black', linewidth=1.5, alpha=0.8)

    ax.set_ylabel("Mean |PF| (± std)", fontsize=12, fontweight='bold')
    ax.set_title("평균 Pareto Front 크기 비교", fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.grid(axis='y', alpha=0.3)

    # 값 표시
    for i, (bar, size, std) in enumerate(zip(bars, pf_sizes, pf_stds)):
        ax.text(bar.get_x() + bar.get_width()/2, size + std + 5,
                f"{size:.1f}±{std:.1f}", ha='center', fontweight='bold')

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "bar_pareto_size.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ 저장: {FIGURES_DIR / 'bar_pareto_size.png'}")
else:
    print("\n⚠️  bar_pareto_size.png 생성 스킵 (EXP2 또는 EXP3 결과 없음)")

# ============================================================================
# 4. Sensitivity Analysis: HV 비교
# ============================================================================

print("\n📈 생성 중: sensitivity_hv.png")

fig, ax = plt.subplots(figsize=(10, 6))

sensitivity_names = ["Base\n(50-20-30)", "High Carb\n(65-18-17)",
                     "Low Carb\n(35-22-43)", "Mid-Balanced\n(45-25-30)",
                     "Low Protein\n(50-10-40)"]
sensitivity_keys = ["exp2", "high_carb", "low_carb", "mid_balanced", "low_protein"]

hv_values = []
hv_stds = []

for key in sensitivity_keys:
    if key in data:
        hv_values.append(data[key]["HV"].mean())
        hv_stds.append(data[key]["HV"].std())
    else:
        hv_values.append(0)
        hv_stds.append(0)

x = np.arange(len(sensitivity_names))
colors = ['lightgray', 'skyblue', 'lightyellow', 'lightgreen', 'lightcoral']

bars = ax.bar(x, hv_values, yerr=hv_stds, capsize=8, color=colors,
              edgecolor='black', linewidth=1.5, alpha=0.8)

ax.set_ylabel("HV (± std)", fontsize=12, fontweight='bold')
ax.set_title("영양 프로필 민감도 분석 — Hypervolume", fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(sensitivity_names, fontsize=10)
ax.grid(axis='y', alpha=0.3)

# 값 표시
for bar, hv, std in zip(bars, hv_values, hv_stds):
    ax.text(bar.get_x() + bar.get_width()/2, hv + std + 0.05,
            f"{hv:.3f}", ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig(FIGURES_DIR / "sensitivity_hv.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"  ✓ 저장: {FIGURES_DIR / 'sensitivity_hv.png'}")

# ============================================================================
# 통계 검정: Wilcoxon 부호순위 검정
# ============================================================================

if "exp3" in data and "exp2" in data:
    print("\n📊 통계 분석: Wilcoxon 부호순위 검정 (Exp2 vs Exp3)")
    print("-" * 60)

    metrics_to_test = ["GD", "IGD", "HV", "Spread"]

    for metric in metrics_to_test:
        exp2_vals = data["exp2"][metric].values
        exp3_vals = data["exp3"][metric].values

        statistic, p_value = stats.wilcoxon(exp2_vals, exp3_vals)

        mean_exp2 = exp2_vals.mean()
        mean_exp3 = exp3_vals.mean()

        significant = "✓" if p_value < 0.05 else "✗"

        print(f"{metric:8s} | Exp2: {mean_exp2:.4f} | Exp3: {mean_exp3:.4f} | p={p_value:.6f} {significant}")
else:
    if "exp3" not in data:
        print("\n⚠️  Wilcoxon 검정 스킵 (EXP3 결과 없음)")

# ============================================================================
# 요약 통계
# ============================================================================

print("\n" + "=" * 60)
print("📋 실험별 성능 요약")
print("=" * 60)

# 사용 가능한 실험만 표시
experiments_to_show = []
if "exp2" in data:
    experiments_to_show.append(("DailyExp2 (3-obj, NSGA-II)", "exp2"))
if "exp3" in data:
    experiments_to_show.append(("DailyExp3 (4-obj, R-NSGA-II)", "exp3"))

for exp_name, exp_key in experiments_to_show:
    print(f"\n{exp_name}")
    print("-" * 40)
    df = data[exp_key]
    print(f"  GD      : {df['GD'].mean():.4f} ± {df['GD'].std():.4f}")
    print(f"  IGD     : {df['IGD'].mean():.4f} ± {df['IGD'].std():.4f}")
    print(f"  HV      : {df['HV'].mean():.4f} ± {df['HV'].std():.4f}")
    print(f"  Spread  : {df['Spread'].mean():.4f} ± {df['Spread'].std():.4f}")
    print(f"  |PF|    : {df['n_pareto'].mean():.1f} ± {df['n_pareto'].std():.1f}")

# 민감도 분석 요약
sensitivity_keys = ["high_carb", "low_carb", "mid_balanced", "low_protein"]
sensitivity_available = [k for k in sensitivity_keys if k in data]
if sensitivity_available:
    print("\n" + "=" * 60)
    print("📋 민감도 분석 요약 (HV 값)")
    print("=" * 60)
    for key in sensitivity_available:
        hv_mean = data[key]["HV"].mean()
        hv_std = data[key]["HV"].std()
        print(f"  {key:15s}: {hv_mean:.4f} ± {hv_std:.4f}")

print("\n✅ 분석 완료!")
print(f"📁 시각화 저장 경로: {FIGURES_DIR}")
