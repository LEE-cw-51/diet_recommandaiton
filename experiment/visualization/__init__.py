"""experiment.visualization — 시각화 전담 계층.

이 패키지의 스크립트는 results/ 의 **아티팩트(npz)와 CSV만 읽어** 그래프를 그린다.
최적화(optimizer)는 절대 호출하지 않는다 — 그래프 재생성에 알고리즘 재실행이 없도록 보장.

  plot_step1.py  — 수렴 곡선·지표 박스/바·7일 f4 (results/step1 아티팩트)
  plot_pareto.py — G1/G2/G3 Pareto front 2D 투영 (저장된 PF 로드)
  plot_step2.py  — 논문 Figure 1~4 (results/step2_cuisine CSV + 섭취 이력)
"""

from __future__ import annotations

__all__ = []
