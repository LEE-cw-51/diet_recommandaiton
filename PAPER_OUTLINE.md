# 논문 목차 ↔ 프로젝트 구조 매핑

다목적 최적화 기반 일일 식단 추천 시스템의 논문 목차와, 각 절을 구현·재현하는
코드/디렉토리/결과물을 연결한 문서다. 구조 개편(`experiment/` 계산·시각화 분리) 이후
기준으로 작성되었다.

---

## 1. 보완된 논문 목차

> 사용자 초안을 검토해 (1) 서론과 이론적 배경 분리, (2) 문제 정형화 절 추가,
> (3) 실험·사용자 평가 구체화를 반영했다.

### 1. 서론
- 연구 배경: 매 끼니 기록·결정의 반복으로 인한 피로(decision fatigue)
- 문제 정의: 개인정보(알레르기·선호)·칼로리·가격·탄단지 비율을 입력하면
  하루 식사를 즉시 추천하는 알고리즘의 부재
- 연구 목적 및 기여: 지식그래프(KG) 기반 개인화를 결합한 4목적 R-NSGA-II 식단 추천

### 2. 이론적 배경 (관련 연구)
- 다목적 최적화(MOO)와 파레토 최적
- NSGA-II / R-NSGA-II (참조점 기반) 알고리즘
- 지식그래프 기반 추천, 시간 감쇠(time decay) 개인화
- 기존 식단 추천 연구와의 차별점

### 3. 데이터 수집 및 정제
1. 식약처(MFDS) 데이터 가공 — 핵심 칼럼만 유지, 결측치 처리, 대분류 비율 유지 추출
2. 프랜차이즈 데이터 크롤링 — 영양성분·알레르기·브랜드
3. LLM 식사 분류 태깅 — 5분류(MAIN/SOUP/SIDE/DRINK/SNACK), 식문화 7분류
4. LLM + API 가격·영양 추론 및 태깅
- 데이터셋 통계: 최종 3,358행 (SNACK 1,101 / MAIN 957 / SIDE 688 / DRINK 441 / SOUP 171),
  주요 식문화 한식 663 / 양식 448 / 분식 90 / 중식 33 / 일식 31

### 4. 모델 설계
1. **문제 정형화** *(신설)*
   - 목적함수: f1 칼로리 오차, f2 탄단지 비율 오차, f3 가격 오차, f4 KG 오차율
   - 결정변수·인코딩: 카테고리별 정수 인덱스 조합
   - 제약: 알레르기(데이터 로드 시 사전 필터)
   - KG 점수·시간 감쇠: D_time = e^(−λ·Δt), Score = P_i·(1 − D_i)
2. 알레르기 제약
3. NSGA-II 단독 (**G1**) — 하이퍼파라미터: pop=200, gen=200, 2-point 교차(0.9), PM 변이(0.083)
4. R-NSGA-II (**G2**) — 참조점 REF_G2 = [[0,0,0]]
5. R-NSGA-II + 개인화 (**G3**) — 4목적, 참조점 REF_G3, KG f4(선호·시간감쇠) 통합

### 5. 실험 시뮬레이션
- 평가지표: HV, GD+, IGD+ (weakly Pareto compliant)
- 실험 설계: 30회 독립 실행(seed 고정), Wilcoxon rank-sum 검정
- 시나리오: 식문화 5종, Cold Start, 7일 KG 동적 업데이트(Loop B)

### 6. 사용자 평가
- A/B 블라인드 설계(라벨 무작위, 정답은 meta.json), 유효 응답 24명
- 식문화별 G3 선택률 / 기준별 승률, 통계 검정

### 7. 결론 및 향후 과제
- 한계: 단일 테스트 유저 KG, cold start, 데이터 커버리지(중식/일식 소수)
- 향후: 다중 사용자 KG, 실시간 가격 연동, 장기 사용자 적응

---

## 2. 목차 ↔ 코드/디렉토리/결과 매핑

| 논문 절 | 코드 / 디렉토리 | 결과물 |
|--------|----------------|--------|
| 3-1 MFDS 정제 | `pipeline/01_parse/`, `pipeline/02_clean/`, `pipeline/03_enrich/`, `pipeline/04_merge/` | `data/raw/`, food_master 테이블 |
| 3-2 프랜차이즈 크롤링 | `pipeline/05_augment/step0b_csv_import.py`, `step1_price_allergen.py`, `step1c_franchise_prices.py` | Naver/HACCP 캐시 `data/raw/search_cache/` |
| 3-3 LLM 식사 분류 | `pipeline/05_augment/step2_food_classifier.py`, `pipeline/06_cuisine_classify/step0_classify_cuisine.py` | category_type, cuisine_type |
| 3-4 LLM+API 가격·영양 태깅 | `pipeline/05_augment/step1_price_allergen.py`, `step1c_franchise_prices.py`, `pipeline/03_enrich/*` | price, allergens(JSONB) |
| (스키마) | `migrations/001_add_allergens.sql` | Supabase DDL |
| 4 문제 정형화·목적함수 | `experiment/core/daily_exp{1,2,3}_problem.py`, `experiment/core/nutrition.py`, `experiment/core/kg_manager.py` | — |
| 4 모델 변형 G1/G2/G3 (단일 정의) | `experiment/models/variants.py`, `experiment/algorithms/{factory,builders}.py` | — |
| 4 알레르기 제약 | `experiment/core/loader.py` (로드 시 필터) | — |
| 5 시뮬레이션 (계산) | `experiment/simulation/run_step1.py`, `run_step1_coldstart.py`, `run_step2_cuisine.py`, `simulate_kg.py`, `engine.py`, `artifacts.py` | `experiment/results/step1`, `step1_coldstart`, `step2_cuisine` (CSV + `artifacts.npz`) |
| 5 시각화 (그림) | `experiment/visualization/plot_step1.py`, `plot_pareto.py`, `plot_step2.py` | `plot_*.png`, 논문 Figure 1~4 |
| 6 사용자 평가 | `experiment/evaluation/generate_user_study.py`, `analyze_user_study.py`, `raffle_user_study.py` | `experiment/results/user_study/` |

핵심 원칙: **`simulation/`은 계산 후 아티팩트만 저장**하고, **`visualization/`은 아티팩트·CSV만 로드**한다.
그래프 재생성에 최적화 재실행이 없다.

---

## 3. 재현 절차

데이터 수집·실험은 완료 상태(food_master 3,358행)이므로, 아래는 시뮬레이션/시각화 재현 위주다.

```bash
# 1) 검증용 소규모 실행 (계산 → CSV + artifacts.npz)
python -X utf8 -m experiment.simulation.run_step1 --test

# 2) 시각화 (저장된 아티팩트만 로드 — 최적화 재실행 없음)
python -X utf8 -m experiment.visualization.plot_step1
python -X utf8 -m experiment.visualization.plot_pareto

# 3) 식문화 5종 실험 + 사용자 평가 그림
python -X utf8 -m experiment.simulation.run_step2_cuisine --test   # kg_eaten_sequence.json 포함
python -X utf8 -m experiment.visualization.plot_step2              # Figure 1~4 (Figure 3은 시퀀스 재생)

# 4) 전체 규모 (사용자 확인 후)
python -X utf8 -m experiment.simulation.run_step1 --n_runs 30
```

> 계산과 시각화를 한 번에: `run_step1 --plot` (계산 직후 저장된 아티팩트를 로드해 그림 생성).
