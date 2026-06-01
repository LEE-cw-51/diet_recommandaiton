"""
특정 메뉴의 KG 시간 감쇠 추적 그래프
kg_eaten_sequence.json에서 Day 1 메뉴를 기준으로
7일간 KG score 변화를 꺾은선으로 시각화
"""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from db.client import get_client

ROOT     = Path(__file__).parent
SEQ_PATH = ROOT / "experiment/results/step2_cuisine/한식/kg_eaten_sequence.json"
OUT_PATH = ROOT / "paper_outputs/figures/fig_kg_decay_trace.png"
OUT_PATH.parent.mkdir(exist_ok=True)

LAMBDA   = 0.5    # 감쇠 계수
PREF     = 1.3    # 한식 선호 초기값
MAX_SCORE = PREF  # max_possible_score = pref (decay=0일 때)
N_DAYS   = 7
DPI      = 300

# ── 1. kg_eaten_sequence 로드 ─────────────────────────────────────────────────
seq = json.loads(SEQ_PATH.read_text(encoding="utf-8"))

# Day별 섭취 menu_id 목록
day_menus = {d["day"]: d["menu_ids"] for d in seq["days"]}

# ── 2. Day 1 메뉴 중 추적할 MAIN 선택 ─────────────────────────────────────────
day1_ids = day_menus[1]
client   = get_client()
res = client.table("food_master") \
    .select("id,product_name,category_type,cuisine_type") \
    .in_("id", [int(i) for i in day1_ids]).execute()
id2row = {str(r["id"]): r for r in res.data}

# MAIN 카테고리 중 첫 번째 선택
target_id = None
target_name = None
for mid in day1_ids:
    r = id2row.get(str(mid))
    if r and r.get("category_type") == "MAIN":
        target_id   = str(mid)
        target_name = r["product_name"]
        break

print(f"추적 메뉴: {target_name} (ID: {target_id})")

# ── 3. 이 메뉴가 몇 일에 섭취됐는지 확인 ────────────────────────────────────
eaten_days = [day for day, ids in day_menus.items() if target_id in ids]
print(f"섭취된 날: {eaten_days}")

# ── 4. 날짜별 KG score 계산 ───────────────────────────────────────────────────
# 규칙: 가장 최근 섭취일 기준 감쇠 적용
# score = pref × (1 - exp(-λ × Δday))
# Δday = 0이면 score = 0 (방금 먹음), Δday → ∞이면 score → pref

days     = list(range(1, N_DAYS + 1))
scores   = []
last_ate = None   # 마지막으로 먹은 날 (int)

for day in days:
    if last_ate is None:
        # 아직 한 번도 안 먹음 → 초기 선호도 그대로 (decay=0)
        score = PREF
    else:
        delta = day - last_ate
        decay = math.exp(-LAMBDA * delta)
        score = PREF * (1 - decay)
    scores.append(score)

    # 오늘 먹었으면 last_ate 갱신
    if day in eaten_days:
        last_ate = day

print(f"날짜별 KG score: {[round(s,3) for s in scores]}")

# ── 5. 그래프 ─────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 11, "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})

fig, ax = plt.subplots(figsize=(6.5, 4.0))

# 점수 곡선
ax.plot(days, scores, "o-", color="#2ca02c", linewidth=2.0,
        markersize=7, zorder=5, label="KG Score")

# 최대 점수 기준선
ax.axhline(y=PREF, color="gray", linestyle="--", linewidth=0.9,
           alpha=0.7, label=f"Max score (pref={PREF})")

# 반감기 기준선
half_life = math.log(2) / LAMBDA
ax.axvline(x=1 + half_life, color="#ff7f0e", linestyle=":",
           linewidth=1.0, alpha=0.7,
           label=f"Half-life ({half_life:.1f} days after eating)")

# 섭취 이벤트 마커
for ed in eaten_days:
    score_at = scores[ed - 1]
    ax.annotate(
        f"Eaten\n(Day {ed})",
        xy=(ed, score_at),
        xytext=(ed + 0.15, score_at - 0.18),
        fontsize=8, color="#d62728",
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.0),
    )
    ax.scatter([ed], [score_at], color="#d62728", s=80, zorder=6)

# 회복 영역 음영
if eaten_days:
    first_eat = eaten_days[0]
    ax.axvspan(first_eat, N_DAYS + 0.4, alpha=0.06, color="#2ca02c",
               label="Recovery zone")

# 축 설정
ax.set_xlabel("Day", fontsize=10)
ax.set_ylabel("KG Preference Score", fontsize=10)
ax.set_title(f"KG Time-Decay Trace: 'Buldak Chicken Mayo' (Day 1 eaten)", fontsize=11, fontweight="bold")
ax.set_xticks(days)
ax.set_xlim(0.5, N_DAYS + 0.5)
ax.set_ylim(-0.05, PREF * 1.15)
ax.legend(fontsize=8, loc="lower right", frameon=True)
ax.grid(axis="y", alpha=0.3)

# score 값 레이블
for day, score in zip(days, scores):
    ax.text(day, score + 0.04, f"{score:.2f}",
            ha="center", fontsize=7.5, color="#2ca02c")

plt.tight_layout()
fig.savefig(OUT_PATH, dpi=DPI, bbox_inches="tight")
plt.close(fig)
print(f"\n✅ 저장 → {OUT_PATH}")
