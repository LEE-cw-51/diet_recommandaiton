# 논문 목차 ↔ 프로젝트 구조 매핑

다목적 최적화 기반 일일 식단 추천 시스템의 논문 목차와,
각 절을 구현·재현하는 코드/디렉토리/결과물을 연결한 문서다.

---

## 1. 논문 목차

### 1. 서론
- 연구 배경: 매 끼니 기록·결정의 반복으로 인한 인지적 피로(decision fatigue)
- 문제 정의: 개인정보(알레르기·선호)·칼로리·가격·탄단지 비율을 입력하면 하루 식사를 즉시 추천하는 알고리즘의 부재
- 연구 목적 및 기여: KG 기반 개인화를 결합한 4목적 R-NSGA-II 식단 추천 시스템 제안

### 2. 이론적 배경
- 다목적 최적화(MOO)와 파레토 최적
- NSGA-II / R-NSGA-II (참조점 기반) 알고리즘
- 지식그래프 기반 추천 및 시간 감쇠(time decay) 개인화
- 기존 식단 추천 연구와의 차별점

### 3. 데이터 수집 및 정제
1. 식약처(MFDS) 데이터 가공 — 핵심 칼럼 추출, 결측치 처리, 대분류 비율 유지
2. 프랜차이즈 데이터 크롤링 — 영양성분·알레르기·가격 (Naver Shopping / HACCP API)
3. LLM 식사 분류 태깅 — 5분류(MAIN/SOUP/SIDE/DRINK/SNACK), 식문화 7분류
4. LLM + API 가격·영양 추론 및 태깅

**최종 데이터셋**: 3,358행 — SNACK 1,101 / MAIN 957 / SIDE 688 / DRINK 441 / SOUP 171  
**주요 식문화**: 한식 663 / 양식 448 / 분식 90 / 중식 33 / 일식 31

### 4. 모델 설계
1. **문제 정형화**
   - 목적함수: f1 칼로리 오차, f2 탄단지 비율 오차, f3 가격 오차, f4 KG 오차율
   - 결정변수·인코딩: 카테고리별 정수 인덱스 조합
   - 하드 제약: 알레르기 유발 음식 사전 필터 (데이터 로드 시 적용)
   - KG 점수·시간 감쇠: D_time = e^(−λ·Δt), Score = P_i·(1 − D_i)
2. **NSGA-II (G1)** — 3목적 베이스라인, pop=200, gen=200, 2-point 교차(0.9), PM 변이(0.083)
3. **R-NSGA-II (G2)** — 참조점 REF_G2 = [[0,0,0]], 수리적 최적 집중
4. **R-NSGA-II + KG (G3)** — 4목적, 참조점 REF_G3, f4(KG 선호·시간 감쇠) 통합, 제안 모델

### 5. 실험 설계 및 환경
1. **평가지표** — HV(초부피, 높을수록 우수), GD+·IGD+(수렴·포괄, 낮을수록 우수, weakly Pareto compliant)
2. **실험 환경** — 30회 독립 실행(seed 42~71 고정), Wilcoxon rank-sum 검정(유의수준 0.05)
3. **시나리오**
   - 식문화 5종(한식·양식·분식·중식·일식): 각 식문화 풀에서 G3 단독 최적화 (Loop A)
   - Cold Start: 사전 섭취 이력 없이 7일 KG 학습 과정 관찰
   - 7일 KG 동적 업데이트(Loop B): 전일 섭취 결과를 KG에 반영, 중복률 측정

### 6. 실험 결과 및 평가
1. **알고리즘 비교 (G1/G2/G3)** — HV·GD+·IGD+ mean±std 테이블, Wilcoxon 검정 결과
2. **식문화 5종 시나리오** — 데이터 수 ↔ 추천 품질(IGD+, f4) 상관, 커버리지 한계 논의
3. **콜드 스타트 & KG 동적 업데이트** — f4 오차 0.25→0.028 (89% 감소, Day 7 기준) 곡선, 중복률 0.0
4. **정성 평가** — 한식 선호 사용자 7일 G3 식단 표, G1 vs G3 동일 날짜 비교

### 7. 결론 및 향후 과제
- **한계**: 단일 테스트 유저 KG, cold start 제약, 중식·일식 데이터 소수
- **향후**: 다중 사용자 KG, 실시간 가격 연동, 장기 사용자 적응

---

## 2. 목차 ↔ 코드/결과 매핑

| 논문 절 | 코드 / 디렉토리 | 결과물 |
|--------|----------------|--------|
| 3-1 MFDS 정제 | `pipeline/01_parse/`, `02_clean/`, `03_enrich/`, `04_merge/` | `data/raw/`, food_master 테이블 |
| 3-2 프랜차이즈 크롤링 | `pipeline/05_augment/step0b_csv_import.py`, `step1_price_allergen.py`, `step1c_franchise_prices.py` | `data/raw/search_cache/` (Naver/HACCP 캐시) |
| 3-3 LLM 식사 분류 | `pipeline/05_augment/step2_food_classifier.py`, `pipeline/06_cuisine_classify/step0_classify_cuisine.py` | category_type, cuisine_type 컬럼 |
| 3-4 가격·영양 태깅 | `pipeline/05_augment/step1_price_allergen.py`, `step1c_franchise_prices.py`, `pipeline/03_enrich/*` | price, allergens(JSONB) |
| 3 스키마 | `migrations/001_add_allergens.sql` | Supabase DDL |
| 4 문제 정형화 | `experiment/core/daily_exp{1,2,3}_problem.py`, `experiment/core/nutrition.py`, `experiment/core/kg_manager.py` | — |
| 4 모델 변형 G1/G2/G3 | `experiment/models/variants.py`, `experiment/algorithms/{factory,builders}.py` | — |
| 5·6 시뮬레이션 (계산) | `experiment/simulation/run_step1.py`, `run_step1_coldstart.py`, `run_step2_cuisine.py`, `engine.py`, `artifacts.py` | `experiment/results/step1/`, `step1_coldstart/`, `step2_cuisine/` |
| 6 시각화 (그림) | `experiment/visualization/plot_step1.py`, `plot_pareto.py`, `plot_step2.py` | `figure1_core_metrics.png`, `box_plot_comparison.png`, `pareto_scatter_exp3.png`, `plot_coldstart_comparison.png` |

> **핵심 원칙**: `simulation/`은 계산 후 아티팩트만 저장, `visualization/`은 아티팩트·CSV만 로드 — 그래프 재생성 시 최적화 재실행 없음.

---

## 3. 재현 절차

데이터 수집·실험은 완료 상태(food_master 3,358행)이므로, 시뮬레이션/시각화 재현 위주다.

```bash
# 1) G1/G2/G3 비교 — 소규모 검증 실행
python -X utf8 -m experiment.simulation.run_step1 --test

# 2) 시각화 (저장된 아티팩트만 로드 — 최적화 재실행 없음)
python -X utf8 -m experiment.visualization.plot_step1
python -X utf8 -m experiment.visualization.plot_pareto

# 3) 식문화 5종 (Loop A·B) + 시각화
python -X utf8 -m experiment.simulation.run_step2_cuisine --test
python -X utf8 -m experiment.visualization.plot_step2

# 4) 콜드 스타트 + 시각화
python -X utf8 -m experiment.simulation.run_step1_coldstart --test

# 5) 전체 규모 30회 (사용자 확인 후)
python -X utf8 -m experiment.simulation.run_step1 --n_runs 30
```

> 계산과 시각화를 한 번에: `run_step1 --plot` (계산 직후 저장된 아티팩트를 로드해 그림 생성)
