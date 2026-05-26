"""experiment.simulation — 계산 전담 계층.

이 패키지의 스크립트는 최적화를 실행하고 결과를 results/에 **아티팩트로 저장**한다.
기본적인 시각화 책임은 experiment.visualization 가 아티팩트를 로드해 담당한다.
다만 일부 시나리오 스크립트는 진단/확인용 plot을 선택적으로 생성할 수 있다.

  engine.py      — run_once(), build_kg(), F 스냅샷 Callback
  artifacts.py   — save_artifacts()/load_artifacts() (npz + CSV 계약)
  run_step1.py   — G1/G2/G3 비교 (Loop A) + 7일 KG (Loop B)
  run_step1_coldstart.py / run_step2_cuisine.py — 시나리오 변형
  simulate_kg.py — 단일 날 R-NSGA-II 실행 헬퍼 + 페르소나 검증
"""

from __future__ import annotations

__all__ = []
