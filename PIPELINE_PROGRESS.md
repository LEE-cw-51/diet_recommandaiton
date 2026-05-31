# 파이프라인 진행 상황

## 현재 상태
- **완료**: Step 5 — KG 기반 4목적 최적화 (DailyExp3 + R-NSGA-II) + 7일 시뮬레이션 검증 + **30회 본실험** ✅
- **완료**: **프로젝트 구조 정리 + experiment/ 코드 품질 정리** ✅ (PR #3 merge)
- **완료**: **G1/G2/G3 기술적 검증 실험 (목적함수 정확화 + 본실험)** ✅ (Session 14, PR #5 준비)
- **완료**: **KGManager 리팩터링 — 카테고리 완전 제거, 메뉴 별점(1~5★) 기반 선호도** ✅ (Session 13)
- **완료**: **Step 6 — cuisine_type 분류 + Cold Start 문제 해결** ✅ (Session 15)
- **완료**: **Step 7 — 식문화별 G1/G2/G3 비교 실험 (5개 식문화 × 30회 본실험)** ✅ (Session 16)
- **완료**: **A/B 유저 스터디 전체 파이프라인 구축** ✅ (Session 18, PR #11~14)
- **완료**: **설문 앱 품질 보완 + 배포** ✅ (Session 19, PR #15~19)
- **완료**: **A/B 유저 스터디 응답 수집 + 분석 + 추첨** ✅ (Session 20)
- **완료**: **experiment/ 구조 개편 — 계산/시각화/평가 분리 + 모듈화** ✅ (Session 22)
- **완료**: **논문용 그림 전체 생성 + Loop B 7일 실험** ✅ (Session 23, PR #28)
- **완료**: **논문 Sec 4~6 스토리보드 문서 작성** ✅ (Session 24, PR #29 예정)
- **완료**: **논문 Sec 1~2 스토리보드 문서 작성 + 그림 2종 생성** ✅ (Session 26)
- **다음 작업**: 스토리보드(Sec 1~6) 기반으로 논문 본문(마크다운 초안) 작성
- 마지막 업데이트: 2026-05-31 (Session 26, 논문 Sec 1~2 스토리보드)

## Session 26 완료 내용 (2026-05-31)

### 논문 Sec 1~2 스토리보드 문서 작성 + 그림 2종 생성

**목표:** Sec 1(서론)과 Sec 2(이론적 배경) 스토리보드 확정 및 그림 생성.

**산출물:**
- `docs/storyboard_sec1_2.md` 신규 생성 (Sec 1: 1.1~1.4, Sec 2: 2.1~2.5)
- `experiment/results/paper_figures/sec1_intro/fig0_system_overview.png` (시스템 개요 블록 다이어그램)
- `experiment/results/paper_figures/sec2_theory/fig_kg_concept.png` (KG 삼중항 개념도)
- `experiment/visualization/paper_figures.py` — `--sec1` / `--sec2` 플래그 추가

**인용 근거 검증 결과:**
- ~~Wansink & Sobal (2007)~~ 사용 불가 (연구 부정직 스캔들) → 2020 한국인 영양소 섭취기준 + KNHANES 2023으로 대체
- ~~Das & Dennis (1998)~~ R-NSGA-II 아님 → Deb & Sundar (2006) GECCO '06, DOI:10.1145/1143997.1144112로 교정
- WHO 2025 지침 존재하지 않음 → 한국 공식 지침(보건복지부/질병관리청)으로 대체

**서론 구조 확정:**
- 1.1: 영양 불균형 사회적 배경 (KNHANES 2023, 한국인 영양소 섭취기준 2020)
- 1.2: 기존 서비스의 사용 피로감 (수동 입력·단일 기준 추천의 한계)
- 1.3: 연구 목적·기여 3항목 + 학술 차별점 (fig0_system_overview.png)
- 1.4: 논문 구성

## Session 24 완료 내용 (2026-05-31)

### 논문 Sec 4~6 스토리보드 문서 작성

**목표:** 본문 작성 전 논리 흐름·그림 배치·그림 설명 방향을 문서로 확정.

**산출물:** `docs/storyboard_sec4_5_6.md` 신규 생성

**주요 결정 사항:**
- 논문 포맷: 학부 졸업논문, 한국어, 마크다운 초안 먼저
- 유저스터디 결과: 논문 Sec 6에서 제외 (실험 설계 문제로 제거)
- fig5 배치: 한식·양식 (a)(b) 서브피겨로 나란히 배치
- fig3 설명 전략: G1/G2 비교 전용, G3는 fig6에서 별도 비교 (역할 텍스트로 분리)

**파라미터 근거 확정:**
| 파라미터 | 근거 |
|----------|------|
| 목표 칼로리 2,000 kcal | FDA 일반 에너지 참조값 |
| 목표 가격 8,000원/끼니 | 2024년 직장인 평균 점심(9,000~10,000원) 대비 비용 효율 목표가 |
| 영양소 비율 탄50/단20/지30 | WHO 2025 권장 기준 기반 |
| λ=0.5 시간 감쇠 | 반감기 ≈1.4일: 단기 반복 회피 유도 설계 |
| G3 참조점 [0.1,0.1,0.1,0] | 균형 해와 선호 우선 해 동시 탐색 설계 |
| 교차·변이·η·ε | NSGA-II/R-NSGA-II 표준 파라미터 (Deb et al., 2002) |
| Population/Gen 200/200 | fig2 수렴 곡선에서 200세대 내 수렴 확인 |

**다음 세션 작업:** `docs/storyboard_sec4_5_6.md` 기반으로 Sec 4~6 본문 마크다운 초안 작성

## Session 22 완료 내용 (2026-05-26)

### experiment/ 구조 개편 — 논문 목차 정합 + 계산/시각화 분리

**목표:** 시각화 시 알고리즘 재실행이 없도록 계산과 시각화를 분리하고, 공통 로직을 모듈화.

**핵심 변경:**
- 신규 패키지: `experiment/models/`(변형·상수 단일 출처), `experiment/simulation/`(계산),
  `experiment/visualization/`(시각화), `experiment/evaluation/`(사용자 평가)
- `experiment/tools/` 제거 — 스크립트를 역할별로 이동
- 공통 로직 추출: `algorithms/builders.py`(make_nsga2/make_rnsga2),
  `models/variants.py`(REF_G2/REF_G3/SEED_START/GROUP_*), `simulation/engine.py`(run_once/build_kg)
- 아티팩트 계약: `simulation/artifacts.py` — `run_step1`이 `artifacts.npz`(per-run F·스냅샷·머지 Pareto·메트릭)
  저장 → 시각화가 로드만 함
- **결합 제거**: `plot_pareto`(과거 5회 재실행) / Figure 3 KG viz(과거 7일 재최적화) → 저장 데이터 재생으로 대체

**신규 실행 커맨드:**
```
python -X utf8 -m experiment.simulation.run_step1 [--test] [--plot]
python -X utf8 -m experiment.visualization.plot_step1
python -X utf8 -m experiment.visualization.plot_pareto
python -X utf8 -m experiment.simulation.run_step2_cuisine [--test]
python -X utf8 -m experiment.visualization.plot_step2
python -X utf8 -m experiment.evaluation.{generate,analyze,raffle}_user_study
```

**문서:** 논문 목차 ↔ 코드 매핑은 [PAPER_OUTLINE.md](PAPER_OUTLINE.md).
**검증:** 14개 모듈 import OK + 합성 아티팩트로 시각화 5종 PNG 생성 확인(최적화 재실행 0회).
**주의:** 아래 과거 세션 로그의 `experiment/tools/...` 경로는 당시 기준 기록 — 현재 경로는 위 커맨드 참조.

## Session 20 완료 내용 (2026-05-21)

### A/B 유저 스터디 결과 분석

**응답 현황:** 총 26명 응답 → 30초 미만 2명 제외 → **유효 24명**

**식문화별 G3(개인화 알고리즘) 선택률:**
| 식문화 | 응답수 | G3 선택률(선호도) | 다양성 G3 승률 | 영양균형 G3 승률 |
|------|------|------|------|------|
| 한식 | 13명 | 53.8% | 38.5% | 53.8% |
| 일식 | 5명 | 60.0% | 40.0% | 60.0% |
| 양식 | 3명 | 100.0% | 66.7% | 100.0% |
| 중식 | 3명 | 0.0% | 66.7% | 0.0% |

**핵심 해석:**
- 양식·일식에서 G3(개인화) 전반적 우세
- 한식은 선호도·영양균형에서 G3 우세, 다양성은 G2 우세 (개인화가 특정 메뉴 집중 유발 가능성)
- 중식·양식은 샘플 3명으로 통계적 유의성 낮음

**분석 결과 저장:** `experiment/results/user_study/analysis_result.csv`

**경품 추첨:** 전화번호 입력 + 30초 이상 유효 응답 16명 중 5명 추첨
- 당첨자 저장: `experiment/results/user_study/raffle_winners.csv`

**기술적 이슈 해결:**
- Supabase RLS로 anon key SELECT 차단 → `db/client.py`에 `get_admin_client()` 추가 (service_role key 사용)

## 단계별 완료 현황
| 단계 | 내용 | 상태 | 수치 |
|------|------|------|------|
| Step 0 | food_research_sample → food_master bulk copy | ✅ | 2,522행 |
| Step 1 | 네이버 가격 + HACCP 알레르기 UPDATE | ✅ | 2,520/2,522 (99.9%) |
| Step 1b | price NULL 보정 (fallback 검색) | ✅ | 127개 보정, 최종 1,761개 유가격 (69.8%) |
| Step 0b | final_nutrition_db.csv → food_master INSERT | ✅ | 850/871 성공 (97.6%), 21개 실패 스킵 |
| Step 1c | 프랜차이즈 가격 조회 (Naver webkr → Gemini) | ✅ | 564/846 업데이트, 25 실패, 체크포인트 825개 |
| Step 2 | Gemini 2.5 Flash-Lite → category_type 분류 (5-class) | ✅ | 3,372/3,372 (100%), 503 fallback ~0.5% |
| Step 2b | 영양성분 불량 행 데이터 클렌징 | ✅ | 14개 삭제, 최종 3,358행 (SNACK 1,101 / MAIN 957 / SIDE 688 / DRINK 441 / SOUP 171) |
| Step 2c | price 이상치 처리 (IQR Tukey's fence → SQL NULL) | ✅ | LOW 16개 + HIGH 126개 → NULL (SQL 일괄 처리) |
| Step 3-4 | 다목적 최적화 실험 프레임워크 (NSGA-II, Exp1~2) | ✅ | GD/IGD/HV/Spread 지표 완비 |
| **Step 5** | **KG 기반 4목적 최적화 (DailyExp3 + R-NSGA-II)** | ✅ | **30회 본실험 완료: GD=0.0120, IGD=0.0329, HV=0.0069** |
| **Step 6** | **cuisine_type LLM 분류 + Cold Start 해결** | ✅ | **Gemini 배치 분류 2,183개 완료, f4 고정 0.25 → 동적 0.02~0.16** |
| **Step 7** | **식문화별 G1/G2/G3 비교 실험** | ✅ | **5개 식문화 × 30회 본실험 완료** |

## Session 14 완료 내용 (2026-05-13)

### PR #5: G1/G2/G3 기술적 검증 실험 — 목적함수 정확화 + 본실험 완료

#### Phase 1: 코드 검증 및 목적함수 재정의
**발견된 불일치:**
- 설계서: G2 = R-NSGA-II + **3목적** (f1, f2, f3) — KG 미포함, R-NSGA-II 순효과 검증용
- 코드: G2 = **4목적** (f1, f2, f3, f4) ← 불일치로 인해 G1↔G2 비교 의미 손상

**수정 사항:**
1. `experiment/core/daily_exp3_problem.py`: `use_f4` 토글 추가
   - `use_f4=False` → 3목적 (G1, G2)
   - `use_f4=True` → 4목적 (G3)

2. `experiment/tools/run_simulation_step1.py`:
   - 참조점 분리: `_REF_G2` (3D), `_REF_G3` (4D)
   - problem 분리: `problem_3obj` (G1/G2), `problem_4obj` (G3)
   - ref_front/nadir 그룹별 계산 (3D vs 4D 차원 불일치 해결)
   - Wilcoxon 검정: **G1 vs G2** (같은 차원, 직접 비교 가능)

3. `experiment/tools/plot_pareto_step1.py`:
   - 2×3 Pareto 산점도에서 G2의 f4 관련 쌍 자동 누락

#### Phase 2: 본 실험 실행 (Loop A 30회 + Loop B 7일)

**Loop A 결과 (30회 독립 실행, pop=200, gen=200):**
| 그룹 | HV | GD+ | IGD+ | 시간 | 해 개수 |
|------|-----|------|------|------|--------|
| G1 (NSGA-II, 3obj) | 3.1256±0.0010 | 0.1546 | 0.0036 | 4.84s | 30회 평균 44해 |
| G2 (R-NSGA-II, 3obj) | 3.1259±0.0018 | 0.0091 | 0.0012 | 5.85s | 30회 평균 81해 |
| G3 (R-NSGA-II+KG, 4obj) | 0.0229±0.0000 | 0.0239 | 0.0020 | 6.83s | 30회 평균 54해 |

**Wilcoxon 검정 결과:**
- **G1 vs G2** (R-NSGA-II 순효과, 3D 직접 비교):
  - HV: p=0.0760 (n.s.) ← 거의 동등 (R-NSGA-II 알고리즘 선택의 효과 미미)
  - GD+: p=0.0000 ✅ (G2가 유의하게 개선)
  - IGD+: p=0.0000 ✅ (G2가 유의하게 개선)
  - **해석**: R-NSGA-II 알고리즘 자체는 3D에서 GD+/IGD+ 지표로 측정된 내부 해의 배치를 개선하나, HV(전체 합) 관점에서는 NSGA-II와 차이 없음

- **G1/G2 vs G3** (KG 통합 효과):
  - 모든 지표에서 유의한 차이 (p<0.05)
  - 주의: 4D vs 3D 비교이므로 HV 절대값은 단위 다름

**Loop B 결과 (7일 KG 동적 시뮬레이션):**
- f4: 0.2500 (선호 메뉴 고정, 감쇠 x)
- f1: 0.0005~0.0046 (칼로리 오차 매우 낮음)
- 중복률: 0% (7일 간 메뉴 중복 없음)

**산출물 (experiment/results/step1/):**
- CSV: metrics_comparison.csv, daily_f4_trend.csv, daily_duplication.csv
- PNG: plot_convergence.png, plot_metrics_boxplot.png, plot_metrics_bar.png, plot_7days_f4.png, plot_pareto_scatter.png

#### Phase 3: 논문 준비 사항

**핵심 해석:**
1. **R-NSGA-II의 역할**: GD+/IGD+ 기준으로 파레토 해의 분포를 개선하나, HV(hypercube 부피)는 NSGA-II와 유사
2. **KG 통합의 효과**: f4 차원 추가로 인해 4D 목적공간 확대, f1/f2/f3는 유지하면서 선호도 최적화
3. **7일 시뮬레이션**: f4 고정으로 인해 동적 감쇠 효과 미측정 → 향후 개선 여지

## Session 18 완료 내용 (2026-05-20)

### A/B 유저 스터디 전체 파이프라인 구축

**KGManager 섭취 이력 분리** (`experiment/core/kg_manager.py`)
- `last_ate` edge 속성 완전 제거 → `_intake_log: list[tuple[str, str, datetime]]` 독립 관리
- 선호도(pref edge) ↔ 섭취 이력(intake_log) 개념 분리 (교수님 피드백 반영)
- `record_eating()` → log append만 / `_get_last_ate()` private 메서드로 조회
- `get_score()`, `get_batch_diet_score()` → `_get_last_ate()` 사용으로 교체

**A/B 식단 사전 생성** (`experiment/tools/generate_user_study.py`)
- 4개 식문화 × 5세트 = **20세트 생성 완료** (pop=200, gen=200)
- G2(use_f4=False, KG 미적용) vs G3(use_f4=True, KG 적용), 동일 seed 공정 비교
- A/B 라벨 랜덤 배정 → meta.json에만 정답 저장 (블라인드)
- 출력: `experiment/results/user_study/{cuisine}/set_XX_A.csv, B.csv, meta.json`

**Streamlit A/B 유저 스터디 앱** (`user_study_app/app.py`)
- Step 0: 연구 참여 동의서 (논문 심사 대응)
- Step 1: 식문화 선택 + 랜덤 세트 배정 (5세트 중 1개)
- Step 2: 식단 A/B 7일치 탭+카드형 표시 (모바일 최적화, 날짜 미표시)
- Step 3: 비교 질문 3개 (A/B 선택)
  - 🔄 어느 식단이 더 다양했나요? → `diversity_winner`
  - ⚖️ 어느 식단이 더 균형 잡혔나요? → `nutrition_winner`
  - 🙋 어느 식단이 선호도에 맞나요? → `chosen_overall`

**Supabase 스키마 변경** (`user_study_responses` 테이블)
- 기존 Likert 컬럼(diversity_a/b, nutrition_a/b) → 비교형 컬럼 추가
- `ALTER TABLE user_study_responses ADD COLUMN diversity_winner text, ADD COLUMN nutrition_winner text`

**분석 스크립트** (`experiment/tools/analyze_user_study.py`)
- A/B → G2/G3 blind decode (meta.json 참조)
- 식문화별 G3 승률(다양성/영양균형) + G3 선택률(선호도) 집계
- 출력: `experiment/results/user_study/analysis_result.csv`

**분석 스크립트 실행 방법 (설문 수집 완료 후):**
```bash
python -X utf8 -m experiment.tools.analyze_user_study
```

**PR 현황:**
- PR #11 merge: KGManager + generate_user_study + 20세트 데이터
- PR #12 merge: Streamlit 앱 v1
- PR #13 merge: Streamlit 앱 v2 (동의서 + 모바일)
- **PR #14 open** (`fix/app-scenario-text`): 시나리오 문구 + 비교형 3문항 + Step 통합

---

## Session 16 완료 내용 (2026-05-14)

### Step 7: 식문화별 G1/G2/G3 알고리즘 비교 실험 (`experiment/tools/run_simulation_step2_cuisine.py`)

**실험 설정**: 5개 식문화 × G1/G2/G3 × Loop A(30회) + Loop B(7일), pop=200, gen=200

**G1/G2 결과 (식문화 무관, 모두 동일 — KG 미사용)**:
| 그룹 | HV | GD+ | IGD+ | 시간 |
|------|-----|------|------|------|
| G1 (NSGA-II, 3obj) | 3.5361±0.0012 | 0.0358 | 0.0058 | ~4.9s |
| G2 (R-NSGA-II, 3obj) | 3.5371±0.0010 | 0.0052 | 0.0021 | ~5.9s |
- G1 vs G2: HV p=0.0006 ✅ / GD+ p=0.0000 ✅ / IGD+ p=0.0000 ✅

**G3 Loop A 결과 (식문화별 KG 차이 반영)**:
| 식문화 | KG메뉴 | G3 HV | G3 GD+ | 시간 |
|-------|-------|-------|-------|------|
| 한식 | 663 | 0.0088 | 0.0194 | 15.1s |
| 양식 | 448 | 0.0100 | 0.0097 | 10.6s |
| 분식 | 90 | 0.0167 | 0.0169 | ~8s |
| 중식 | 33 | 0.0060 | 0.0189 | 9.4s |
| 일식 | 31 | 0.0181 | 0.0168 | 9.2s |

**G3 Loop B 결과 (7일 KG 동적 시뮬레이션)**:
| 식문화 | KG메뉴 | f4 평균 | 중복률 |
|-------|-------|-------|------|
| 한식 | 663 | **0.0414** | 0.54% |
| 양식 | 448 | **0.0553** | 0.35% |
| 분식 | 90 | **0.1019** | 1.72% |
| 중식 | 33 | **0.1411** | 2.80% |
| 일식 | 31 | **0.1434** | 4.39% |

**핵심 발견**: 식문화 메뉴 수 ↑ → f4 ↓ (선호도 매칭 개선) + 중복률 ↓ (다양성 확보)
- 한식(663개)의 f4 0.0414 vs 일식(31개)의 f4 0.1434: 식문화 데이터 충분성이 추천 품질에 직접 영향

**산출물 (experiment/results/step2_cuisine/)**:
- `{cuisine}/metrics_comparison.csv`, `{cuisine}/daily_f4_trend.csv`
- `{cuisine}/plot_convergence.png`, `{cuisine}/plot_metrics_boxplot.png`, `{cuisine}/plot_metrics_bar.png`, `{cuisine}/plot_7days_f4.png`
- `cuisine_summary.csv`, `plot_cuisine_f4_comparison.png`, `plot_cuisine_loop_a_summary.png`

---

#### Phase 4: Loop B Cold Start 문제 해결 — Session 15 완료

**발견:**
- f4 = 0.2500 고정 (7일 내내 변화 없음)
- 원인: **KG cold start 문제**
  - TEST_USER의 KG_PREFERENCES: 비빔밥(4★), 된장찌개(3★) 만 2개
  - 매일 다른 seed로 최적화 → 대부분 선택된 메뉴는 KG에 새로운 메뉴(pref=1.0)
  - 따라서 avg_score = 1.0 고정 → f4 = (1.333 - 1.0) / 1.333 = 0.25 고정

**해결 완료 (Session 15):**

1. **Supabase `cuisine_type` 칼럼 추가** (DDL: Supabase Dashboard SQL Editor)
   - `ALTER TABLE food_master ADD COLUMN IF NOT EXISTS cuisine_type VARCHAR(50) DEFAULT NULL;`
   - `CREATE INDEX IF NOT EXISTS idx_food_master_cuisine_type ON food_master (cuisine_type);`

2. **LLM 배치 분류** (`pipeline/06_cuisine_classify/step0_classify_cuisine.py`)
   - Gemini 2.5-flash-lite (3.1-flash-lite 503 폴백) → 100개씩 배치
   - 2,183개 유가격 메뉴 분류 완료
   - 결과: 한식 663 / 카페 525 / 양식 453 / 기타 386 / 분식 90 / 중식 33 / 일식 33

3. **KGManager 확장** (`experiment/core/kg_manager.py`)
   - `add_menu()` 시그니처: `category`, `cuisine` 파라미터 추가
   - `set_category_preference()`: 카테고리별 대량 선호도 설정
   - `set_cuisine_preference()`: 식문화별 대량 선호도 설정

4. **simulate_kg.py 버그 수정** (`experiment/tools/simulate_kg.py`)
   - `add_menu(mid, cat)` → `add_menu(mid, category=cat, cuisine=cuisine_val)` (positional arg 버그)
   - `set_preference(user_id, "MAIN", weight)` → `set_category_preference(user_id, "MAIN", weight)` (메뉴 ID 혼동 버그)

5. **loader.py 수정** (`experiment/core/loader.py`)
   - `_SELECT_COLS`에 `cuisine_type` 추가 (미로딩 버그 수정)

6. **Cold Start 검증 실험** (`experiment/tools/run_simulation_step1_coldstart.py`)
   - `_build_kg_with_cuisine()`: cuisine 기반 KG 하이브리드 초기화
   - 7일 시뮬레이션 실행 (pop=200, gen=200)
   - 결과: f4 = 0.0192~0.0577 (동적 변화) vs 기존 0.2500 고정

**본실험 결과 (Loop B, cuisine=한식, pref=1.3, pop=200, gen=200):**
| Day | f4_before (cold start) | f4_after (hybrid init) | f1 | 중복률 |
|-----|----------------------|----------------------|-----|------|
| 1 | 0.2500 | **0.0192** | 0.0130 | 0% |
| 2 | 0.2500 | **0.0577** | 0.0645 | 0% |
| 3 | 0.2500 | **0.0385** | 0.0545 | 0% |
| 4 | 0.2500 | **0.0577** | 0.0595 | 0% |
| 5 | 0.2500 | **0.0385** | 0.0710 | 0% |
| 6 | 0.2500 | **0.0497** | 0.0220 | 1.4% |
| 7 | 0.2500 | **0.0284** | 0.0275 | 2.4% |

**산출물 (experiment/results/step1_coldstart/):**
- `daily_f4_trend_coldstart.csv`: before/after f4 비교
- `plot_coldstart_comparison.png`: 비교 플롯 (좌: cold start, 우: hybrid init)

**현재 상태:**
- Cold Start 해결 완료 ✅
- **다음: PR #5 merge → 논문 작성**

---

## Session 11 완료 내용 (2026-05-11)

### PR #3: 대규모 프로젝트 구조 정리 + experiment/ 코드 품질 개선 — MERGE 완료

**Phase A: 루트 산제 파일 재배치**
| 파일 | 이동 경로 | 비고 |
|------|---------|------|
| `analyze_pareto.py` | `experiment/results/analyze_pareto.py` | analyze_results.py와 공존 (별도 분석 스크립트) |
| `verify_schema.py` | `qa/verify_schema.py` | 기존 verify_final_db.py와 함께 |
| `figure1_core_metrics.png` | `experiment/results/figures/` | 실험 결과물 통합 |
| `figure2_macro_accuracy.png` | `experiment/results/figures/` | 동상 |
| `nutrition_raw_data.json` (루트) | 삭제 | `database/nutrition_raw_data.json`과 동일 내용 |

**Phase B: experiment/ 코드 품질 정리**

1. ✅ **sugar 키 버그 수정** (base_problem.py:79)
   - 변경: `"sugars"` → `"sugar"` (DB 컬럼명과 일치)
   - 영향: totals()["sugar"] 정상 합계 반환 (목적함수에 직접 영향은 없으나 향후 확장 대비)

2. ✅ **_PROJECT_ROOT 경로 단일화**
   - 기존: loader.py, runner.py, run_experiment.py에서 각각 `Path(__file__).resolve().parents[2]` 반복
   - 변경: `experiment/__init__.py`에 `_PROJECT_ROOT` 상수 정의 → 모든 모듈에서 `from experiment import _PROJECT_ROOT`로 import
   - 영향: 경로 관리 일관성 확보, 변경 시 한 곳만 수정

3. ✅ **macro_ratios() 중복 제거**
   - 기존: BaseDietProblem.macro_ratios() + BaseDailyDietProblem.macro_ratios() (동일 로직)
   - 변경: `experiment/core/nutrition.py`에 `compute_macro_ratios(t: dict)` 함수 추가 → 두 base 클래스는 해당 함수를 호출하는 thin wrapper로 변경
   - 영향: 코드 중복 제거, 단일 정의 원칙

4. ✅ **factory.py 데드코드 제거**
   - 삭제: lines 111-137 (주석처리된 `_build_moeaD()`, `_build_spea2()`)
   - 이유: docstring(1-9행)에 확장 패턴이 이미 안내되어 있어 정보 손실 없음

5. ✅ **simulate_kg.py 위치 정리**
   - 이동: `experiment/simulate_kg.py` → `experiment/tools/simulate_kg.py`
   - 이유: 본 실험 파이프라인이 아닌 디버깅/검증용 오프라인 스크립트 → tools 디렉토리로 명확화
   - 사용 명령어: `python experiment/tools/simulate_kg.py`

**검증 완료**
- ✅ analyze_pareto.py 신규 경로 동작 확인
- ✅ experiment/__init__.py import 정상 작동
- ✅ factory.py 알고리즘 리스트 출력 정상
- ✅ simulate_kg.py 실행 정상

**PR #3 merge 완료** (사용자 진행, branch 삭제)

---

## Session 9 완료 내용 (2026-05-03)

### Step 5: KG 기반 4목적 최적화 + R-NSGA-II

**신규 파일**
| 파일 | 역할 |
|------|------|
| `experiment/core/kg_manager.py` | NetworkX MultiDiGraph KG (IS_IN / PREFERS / ATE 엣지) |
| `experiment/core/daily_exp3_problem.py` | 4목적 문제 (f1 칼로리·f2 매크로·f3 가격·f4 KG오차율) |
| `experiment/config/daily_exp3_rnsga2.yaml` | R-NSGA-II 실험 설정 (pop=200, gen=200, n_runs=30) |
| `experiment/tools/simulate_kg.py` | 2페르소나 × 7일 시뮬레이션 검증 스크립트 (`python -m experiment.tools.simulate_kg ...`) |
| `experiment/results/simulation/` | 시뮬레이션 결과 CSV |

**수정 파일**
| 파일 | 변경 |
|------|------|
| `experiment/algorithms/factory.py` | RNSGA2 빌더 등록 |
| `experiment/core/runner.py` | DailyExp3Problem 레지스트리 + KG 파라미터 처리 |
| `experiment/core/loader.py` | `item["category"] = bucket` 추가 (KG 카테고리 매핑 버그 수정) |

**KG 설계 요약**
- 노드: user / menu / category
- 엣지: `IS_IN` (Menu→Category), `PREFERS` (User→Category/Menu, weight), `ATE` (User→Menu, timestamp)
- 점수 공식: `Score_KG(i) = P_i × (1 - D_i)`, `D_i = max_j(Sim·e^{-λΔt})`
- f4 오차율: `(max_score - avg_score) / max_score ∈ [0,1]`

**7일 시뮬레이션 결과**
| 페르소나 | Hit Rate | 중복률 | 평균 f1 |
|---------|---------|-------|--------|
| 한식_매니아 | 100% ✅ | 2.6% ✅ | 0.000 ✅ |
| 가성비_추구 | 100% ✅ | 1.2% ✅ | 0.000 ✅ |

**수정된 버그 4건**
1. sim_now 미전달 → 미래 ATE 타임스탬프로 음수 감쇠 발생
2. 카테고리 형제 탐색 O(N) → `_ate_by_category` 인덱스로 O(ATE수)로 최적화
3. DiGraph → MultiDiGraph (PREFERS·ATE 동일 엣지 충돌 방지)
4. `item["category"]` 미기록 → `loader.get_category_lists()`에서 bucket 기록 추가

**다음 작업**
```bash
# 30회 본실험
python -X utf8 experiment/run_experiment.py \
    --config experiment/config/daily_exp3_rnsga2.yaml \
    --cal_star 2000 --price_star 8000
```

---

## Step 2c 설계
- 스크립트: `pipeline/05_augment/step2c_price_outlier_fix.py`
- 방법: Tukey's Fence (IQR 1.5×), 카테고리별 별도 fence, 하한 500원 clamp
- Phase 1 SQL: `UPDATE food_master SET price = NULL WHERE price < 500;` (Supabase SQL Editor)
- Phase 2: HIGH 이상치 126개 → Naver webkr 재검색 → Gemini 가격 파싱 → fence 내면 UPDATE, 아니면 NULL
- Phase 3: 재검색 실패 항목 Claude in Chrome으로 Naver Shopping 직접 확인
- IQR fence: MAIN [500~24,625] / SOUP [500~43,830] / SIDE [500~35,250] / DRINK [500~53,500] / SNACK [500~39,965]

## Session 7 완료 내용
- `step1c_franchise_prices.py` 신규 작성 + 실행 완료: Naver webkr 검색 → Gemini price 파싱 → 564개 업데이트
- `step2_food_classifier.py` 신규 작성 + 실행 완료: Gemini 2.5 Flash-Lite → 3,372개 전부 분류 (100%)
  - v1: Groq LLaMA 3.1 8B → TPM 6K/min 초과로 923개에서 중단
  - v2: Gemini 2.5 Flash-Lite → 나머지 ~2,449개 약 41분 만에 완료 (503 fallback ~0.5%)
- `algorithm/daily_diet_optimizer.py` 수정: SOUP 카테고리 추가 (keywords, cat_keys, sides 병합)
- 분류 체계 변경: MAIN/SIDE/DRINK/SNACK → **MAIN/SOUP/SIDE/DRINK/SNACK** (5-class)
  - SOUP: 국/찌개/탕/라면/우동/짬뽕 (고나트륨, 국물+고형물 혼합)
  - sugar + sodium 입력 컬럼 추가 (step2 분류 신호 강화)

## Step 1c 설계
- 스크립트: `pipeline/05_augment/step1c_franchise_prices.py`
- 대상: `food_master WHERE price IS NULL AND data_source='final_nutrition_db'`
- API: Naver webkr `openapi.naver.com/v1/search/webkr.json` → Gemini 2.5 Flash-Lite price 파싱
- 쿼리: `"{brand} {product} 메뉴 가격"` → fallback `"{product} 가격"`
- 체크포인트: `.checkpoint/step1c_done.json` (key: `"product_name|brand_name"`)
- sleep: 0.3s (Naver), 3s (Gemini)

## Step 2 설계 (완료)
- 스크립트: `pipeline/05_augment/step2_food_classifier.py`
- API: Gemini 2.5 Flash-Lite (`GOOGLE_API_KEY`) — v1 Groq에서 전환
- 소스: `food_master WHERE category_type IS NULL` (3,372행)
- 입력: product_name, brand_name, food_group, calories, carbs, sugar, protein, fat, sodium
- 출력: `{"category_type": "MAIN|SOUP|SIDE|DRINK|SNACK"}` (5-class)
- UPDATE: `category_type`, `classified_at`  by `id`
- 체크포인트: `.checkpoint/step2_done.json`
- 결과: 3,372/3,372 (100%), 503 ServiceUnavailable fallback ~0.5%

## 아키텍처
```
food_research_sample (2,524행)
  ↓ [Step 0] bulk copy
food_master (2,522행, 영양성분 채워진 상태)
  ↓ [Step 1] 네이버 가격 + HACCP 알레르기 → Gemini 파싱
food_master (price 69.8% 채워짐, allergens JSON)

data/processed/final_nutrition_db.csv (871행, 프랜차이즈 메뉴)
  ↓ [Step 0b] Gemini allergens 파싱 + UPSERT
food_master (+850행, price=NULL)
  ↓ [Step 1b 재실행] Naver 가격 조회
food_master (신규 행 price 채움)
  ↓ [Step 2] Gemini 2.5 Flash-Lite (v1 Groq TPM 초과로 전환)
food_master (category_type: MAIN/SOUP/SIDE/DRINK/SNACK)
  ↓ [Step 3] algorithm/daily_diet_optimizer.py → from_supabase()
```

## food_master 주요 컬럼
| 컬럼 | 설명 | 채워진 시점 |
|------|------|-----------|
| product_name, brand_name | 식별자 | Step 0 |
| calories, protein, fat, carbs, sugar, sodium | 영양성분 | Step 0 |
| price | 네이버 쇼핑 가격 | Step 1 |
| allergens (JSONB) | 22종 알레르기 | Step 1 |
| raw_label_text | HACCP 원재료명 원문 | Step 1 |
| category_type | MAIN/SOUP/SIDE/DRINK/SNACK | Step 2 |
| augmented_at / classified_at | 처리 시각 | Step 1/2 |

## Supabase
- URL: `https://ealcjovjcnbmxflpofzp.supabase.co`
- 키: `.env` 파일의 `SUPABASE_KEY` 참조
