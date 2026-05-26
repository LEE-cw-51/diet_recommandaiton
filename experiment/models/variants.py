"""모델 변형(G1/G2/G3) 정의 + 재현성 상수 — 단일 출처.

세 모델 변형(논문 4.2~4.4절):
  G1: NSGA-II,        f1/f2/f3 (3목적, KG 미사용)        — baseline
  G2: R-NSGA-II,      f1/f2/f3 (3목적, KG 미사용)        — 알고리즘 순효과
  G3: R-NSGA-II + KG, f1/f2/f3/f4 (4목적, KG f4 사용)    — 본 제안 모델

여기 정의된 상수는 시뮬레이션(experiment.simulation)과
시각화(experiment.visualization) 양쪽에서 import 되어,
참조점·색·라벨·시드의 정의가 한 곳에만 존재하도록 한다.
"""

from __future__ import annotations

import numpy as np

# ── 재현성 상수 ──────────────────────────────────────────────────────────────
SEED_START = 42        # 독립 실행 seed = SEED_START + run_idx
N_MEALS = 3            # 하루 3끼 (간식 미포함)
HV_SAMPLE_EVERY = 10   # Callback: 매 N세대마다 F 스냅샷 수집

# ── 초기 KG 상태 — 고정 테스트 유저 (재현 가능 조건) ──────────────────────────
# 비어있는 KG에서는 G2/G3 모두 f4가 동일해 비교 의미가 없어, 사전 선호/이력을 세팅.
TEST_USER = "test_user_1"
KG_PREFERENCES = {
    "비빔밥":   4,   # 4★ → P_i = 4/3 ≈ 1.33
    "된장찌개": 3,   # 3★ → P_i = 1.0 (중립)
}
KG_HISTORY = [
    {"menu_id": "비빔밥",   "timestamp": "2026-05-06T12:00:00"},
    {"menu_id": "된장찌개", "timestamp": "2026-05-06T19:00:00"},
]

# ── R-NSGA-II 참조점 — 반드시 2D ndarray (shape: n_ref × n_obj) ───────────────
# G2: 3목적(f1, f2, f3) — KG 미포함, R-NSGA-II 알고리즘 순효과 검증용
# G3: 4목적(f1, f2, f3, f4) — KG 통합, 본 제안 모델
REF_G2 = np.array([[0.0, 0.0, 0.0]])
REF_G3 = np.array([[0.0, 0.0, 0.0, 0.0], [0.1, 0.1, 0.1, 0.0]])

# ── 그룹 표기 ────────────────────────────────────────────────────────────────
GROUPS = ("G1", "G2", "G3")

GROUP_COLORS = {"G1": "#e74c3c", "G2": "#2980b9", "G3": "#27ae60"}

GROUP_LABELS = {
    "G1": "G1: NSGA-II (3-obj, no KG)",
    "G2": "G2: R-NSGA-II (3-obj, no KG)",
    "G3": "G3: R-NSGA-II + KG (4-obj, Proposed)",
}
