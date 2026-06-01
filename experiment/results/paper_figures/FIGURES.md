# 논문 그림 목록

## Sec3 — 데이터 수집 및 정제

| 파일 | 설명 |
|------|------|
| [sec3_data/table_data_pipeline.png](sec3_data/table_data_pipeline.png) | 데이터 수집·정제 파이프라인 개요: Step 0~6 단계별 처리 내용·도구·입출력 행수 |
| [sec3_data/table_franchise_sources.png](sec3_data/table_franchise_sources.png) | 프랜차이즈 7개 브랜드 데이터 수집 개요: 수집 방법·항목 수·가격·알레르기 출처 |
| [sec3_data/table_category_criteria.png](sec3_data/table_category_criteria.png) | 5-class 식사 카테고리 분류 기준표: NFIS·식약처·HACCP 기반 정의·영양특성·예시 |
| [sec3_data/fig_dataset_distribution.png](sec3_data/fig_dataset_distribution.png) | food_master 3,358건의 (a) 카테고리 분포 및 (b) 식문화 분포 |
| [sec3_data/table_price_outlier.png](sec3_data/table_price_outlier.png) | 카테고리별 Tukey's Fence (IQR×1.5) 이상치 처리 결과: HIGH 126개 + LOW 16개 → NULL |

## Sec4 — 수식 & 표

| 파일 | 설명 |
|------|------|
| [sec4_formulas/formula_f1.png](sec4_formulas/formula_f1.png) | 목적함수 f1: 칼로리 오차율 수식 (C* = 2000 kcal) |
| [sec4_formulas/formula_f2.png](sec4_formulas/formula_f2.png) | 목적함수 f2: 탄단지 비율 오차율 수식 (carb/prot/fat 평균) |
| [sec4_formulas/formula_f3.png](sec4_formulas/formula_f3.png) | 목적함수 f3: 가격 오차율 수식 (P* = 8,000 KRW) |
| [sec4_formulas/formula_f4.png](sec4_formulas/formula_f4.png) | 목적함수 f4: KG 선호도 오차율 수식 (시간 감쇠 Score 기반) |
| [sec4_formulas/formula_objectives.png](sec4_formulas/formula_objectives.png) | f1~f4 4개 목적함수 통합 수식 (한 장 요약) |
| [sec4_formulas/formula_kg_decay.png](sec4_formulas/formula_kg_decay.png) | KG 시간 감쇠 수식: D_time = e^(-λ·Δt), Score = p_i · e^(-λ·Δt_i) |
| [sec4_formulas/table_model_params.png](sec4_formulas/table_model_params.png) | G1/G2/G3 알고리즘별 하이퍼파라미터 비교표 (pop, gen, 참조점 등) |

## Sec5 — 실험 설계

| 파일 | 설명 |
|------|------|
| [sec5_experiment/table_experiment_design.png](sec5_experiment/table_experiment_design.png) | Loop A/B/A′/Cold Start 4개 시나리오 요약표 (데이터 풀, 실행 수, 평가지표) |

## Sec6 — 결과 그래프

| 파일 | 설명 |
|------|------|
| [sec6_results/fig1_g1_g2_boxplot.png](sec6_results/fig1_g1_g2_boxplot.png) | G1 vs G2: HV·GD+·IGD+ 박스플롯 + Wilcoxon 유의성 표시 |
| [sec6_results/fig2_g1_g2_convergence.png](sec6_results/fig2_g1_g2_convergence.png) | G1 vs G2: 세대별 HV 수렴 곡선 (30회 평균 ± std) |
| [sec6_results/fig3_pareto_scatter.png](sec6_results/fig3_pareto_scatter.png) | G1/G2/G3 파레토 전선 산점도 (f1-f2, f1-f3, f2-f3 3쌍 투영) |
| [sec6_results/fig4_g3_f4_coldstart.png](sec6_results/fig4_g3_f4_coldstart.png) | Cold Start: KG 초기화 전후 f4 비교 (0.25 → 0.028, 89% 감소 (Day 7 기준)) |
| [sec6_results/fig5_korean_7days.png](sec6_results/fig5_korean_7days.png) | 한식 Loop B: 7일간 f4 추이 + 중복률 (Day 6~7 시간 감쇠 회복 확인) |
| [sec6_results/fig5_western_7days.png](sec6_results/fig5_western_7days.png) | 양식 Loop B: 7일간 f4 추이 + 중복률 (Day 7 시간 감쇠 회복 확인) |
| [sec6_results/fig6_g2_vs_g3_3d.png](sec6_results/fig6_g2_vs_g3_3d.png) | G2 vs G3: f1/f2/f3 3D 투영 비교 (KG 추가가 기존 3목적 품질을 해치지 않음을 입증) |
| [sec6_results/fig7_cuisine_coverage.png](sec6_results/fig7_cuisine_coverage.png) | 식문화별 KG 메뉴 수 vs 평균 f4 산점도 (데이터 풀이 클수록 개인화 품질 향상) |
| [sec6_results/fig8_cuisine_metrics.png](sec6_results/fig8_cuisine_metrics.png) | 식문화 5종 G3 IGD+ 박스플롯 (한식이 가장 안정적, 중식·분식은 분산 큼) |
| [sec6_results/plot_kg_visualization.png](sec6_results/plot_kg_visualization.png) | 한식 KG 구조 시각화: Day 0 초기 상태 vs Day 7 이후 시간 감쇠 적용 상태 비교 |
