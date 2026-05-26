# 예산 기반 식단 추천 시스템

사용자의 예산·건강 목표·식문화 선호를 반영해 영양 균형에 최적화된 7일 식단을 추천하는 다목적 최적화 연구 프로젝트 (졸업논문).

식단 추천을 **다목적 최적화 문제**로 정식화하고, 지식 그래프(Knowledge Graph) 기반 개인 선호를 목적함수에 통합한 R-NSGA-II 알고리즘의 효과를 A/B 유저 스터디로 검증한다.

> 📌 **진행 상황·실험 결과·세션 기록은 [PIPELINE_PROGRESS.md](PIPELINE_PROGRESS.md) 참조** (현재 상태의 단일 출처)

## 프로젝트 구조

```
diet_recommendation/
├── experiment/                # ⭐ 핵심 실험 프레임워크
│   ├── core/                  # 문제 정의 (DailyExp3Problem), KGManager, 데이터 로더, 지표
│   ├── models/                # 모델 변형(G1/G2/G3) + 재현성 상수 (variants.py)
│   ├── algorithms/            # NSGA-II / R-NSGA-II 팩토리 + 빌더
│   ├── config/                # 실험 설정 YAML (daily_exp3_rnsga2.yaml)
│   ├── simulation/            # 계산 전담 — 최적화 실행 후 아티팩트 저장 (plot은 옵션)
│   ├── visualization/         # 시각화 전담 — 아티팩트/CSV만 로드 (최적화 재실행 X)
│   ├── evaluation/            # 사용자 평가(A/B) 도구
│   └── results/               # 결과 CSV / 그림 / artifacts.npz (output/는 git 제외)
│
├── pipeline/                  # 데이터셋 구축 파이프라인 (Step 0~7, 방법론 기록)
│   ├── 01_parse/ 02_clean/ 03_enrich/ 04_merge/
│   └── 05_augment/ 06_cuisine_classify/
│
├── user_study_app/            # A/B 유저 스터디 Streamlit 앱
│   └── app.py
│
├── db/                        # Supabase 클라이언트 (from db.client import get_client)
├── migrations/                # Supabase SQL 마이그레이션
├── qa/                        # 데이터 품질 검증 스크립트
├── config/                    # 파이프라인 설정 (config/settings.py)
└── data/                      # 원본·가공 데이터 (대용량 CSV는 git 제외)
```

## 아키텍처: 계산과 시각화의 분리

실험 프레임워크는 **계산(compute)과 시각화(plot)를 분리**한다. 핵심 원칙은
**그림을 다시 그릴 때 알고리즘(optimizer)을 재실행하지 않는다**는 것이다.
`simulation/`이 한 번의 실행에서 그래프 재생성에 필요한 raw 데이터를 모두 `artifacts.npz`로
저장하고, `visualization/`은 그 아티팩트만 로드해 PNG를 만든다.

```
[Supabase food_master]
        │  FoodDataLoader (core/loader.py)
        ▼
  simulation/            최적화 실행 (NSGA-II / R-NSGA-II, 30회·7일)
   run_step1 · run_step2_cuisine · run_step1_coldstart · simulate_kg
        │  계산 결과 저장 (기본은 계산만 — `--plot` 옵션 시 직후 시각화 호출)
        ▼
  results/<scenario>/
    ├── *.csv                   논문 표용 지표·일별 추이
    ├── artifacts.npz           per-run F · 세대 스냅샷 · 머지 Pareto · 메트릭
    └── kg_eaten_sequence.json  Loop B 섭취 시퀀스 (Figure 3 재생용)
        │  load_artifacts() — 로드 전용, optimizer 호출 없음
        ▼
  visualization/         plot_step1 · plot_pareto · plot_step2 → *.png
```

| 패키지 | 역할 |
|--------|------|
| `core/` | 문제 정의(DailyExp3Problem)·KGManager·데이터 로더·지표 (변경 없음) |
| `models/` | G1/G2/G3 변형·참조점·시드 **단일 출처** (`variants.py`) |
| `algorithms/` | NSGA-II / R-NSGA-II `factory` + `builders` |
| `simulation/` | 최적화 실행 → `artifacts.npz` + CSV 저장 (기본은 계산만, plot은 `--plot` 옵션) |
| `visualization/` | 아티팩트·CSV 로드 → PNG (optimizer 재실행 X) |
| `evaluation/` | A/B 유저 스터디 생성·분석·추첨 |

> **보장**: 시각화 스크립트는 `artifacts.npz` / CSV / `kg_eaten_sequence.json`만 읽는다.
> 따라서 그림 재생성에 알고리즘 재실행이 없다 — 과거의 결합(`plot_pareto` 5회 재실행,
> Figure 3의 7일 재최적화)은 제거됐다.
> 논문 목차와의 상세 매핑은 [PAPER_OUTLINE.md](PAPER_OUTLINE.md) 참조.

## 알고리즘 개요

- **다목적 최적화**: f1 칼로리 오차 · f2 매크로 영양비 · f3 가격 · f4 KG 선호도 오차
- **R-NSGA-II**: 참조점 기반 NSGA-II로 선호 영역 집중 탐색
- **Knowledge Graph**: 사용자-메뉴-식문화 선호 그래프로 개인화 (cold start 하이브리드 초기화)
- **검증 그룹**: G1(NSGA-II 3목적) / G2(R-NSGA-II 3목적) / G3(R-NSGA-II + KG 4목적)

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 설정 (.env.example 참고)

# 핵심 실험 (G1/G2/G3 비교) — 계산 후 CSV + artifacts.npz 저장
python -X utf8 -m experiment.simulation.run_step1

# 시각화 (저장된 아티팩트만 로드 — 최적화 재실행 없음)
python -X utf8 -m experiment.visualization.plot_step1
python -X utf8 -m experiment.visualization.plot_pareto

# 식문화별 비교 실험 + 논문 Figure 1~4
python -X utf8 -m experiment.simulation.run_step2_cuisine
python -X utf8 -m experiment.visualization.plot_step2

# A/B 유저 스터디 식단 생성 / 응답 분석
python -X utf8 -m experiment.evaluation.generate_user_study
python -X utf8 -m experiment.evaluation.analyze_user_study

# Streamlit 설문 앱 (로컬)
streamlit run user_study_app/app.py
```

## 데이터

- **food_master** (Supabase): 3,358행 — 편의점·프랜차이즈·영양DB 통합, 5-class 분류 (MAIN/SOUP/SIDE/DRINK/SNACK), cuisine_type 분류
- 구축 과정은 `pipeline/` Step 0~7 및 [PIPELINE_PROGRESS.md](PIPELINE_PROGRESS.md) 참조

## 의존성

주요 라이브러리: `pymoo`(최적화), `networkx`(KG), `supabase`, `pandas`, `numpy`, `scipy`, `matplotlib`, `streamlit`, `google-genai`, `groq`
