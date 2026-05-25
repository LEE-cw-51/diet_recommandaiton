# 예산 기반 식단 추천 시스템

사용자의 예산·건강 목표·식문화 선호를 반영해 영양 균형에 최적화된 7일 식단을 추천하는 다목적 최적화 연구 프로젝트 (졸업논문).

식단 추천을 **다목적 최적화 문제**로 정식화하고, 지식 그래프(Knowledge Graph) 기반 개인 선호를 목적함수에 통합한 R-NSGA-II 알고리즘의 효과를 A/B 유저 스터디로 검증한다.

> 📌 **진행 상황·실험 결과·세션 기록은 [PIPELINE_PROGRESS.md](PIPELINE_PROGRESS.md) 참조** (현재 상태의 단일 출처)

## 프로젝트 구조

```
diet_recommendation/
├── experiment/                # ⭐ 핵심 실험 프레임워크
│   ├── core/                  # 문제 정의 (DailyExp3Problem), KGManager, 데이터 로더, 지표
│   ├── algorithms/            # NSGA-II / R-NSGA-II 팩토리
│   ├── config/                # 실험 설정 YAML (daily_exp3_rnsga2.yaml)
│   ├── tools/                 # 실험·시뮬레이션·유저스터디 생성/분석 스크립트
│   └── results/               # 실험 결과 CSV / 그림 (output/는 git 제외, 재생성 가능)
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

# 핵심 실험 (G1/G2/G3 비교)
python -X utf8 -m experiment.tools.run_simulation_step1

# 식문화별 비교 실험
python -X utf8 -m experiment.tools.run_simulation_step2_cuisine

# A/B 유저 스터디 식단 생성
python -X utf8 -m experiment.tools.generate_user_study

# 유저 스터디 응답 분석
python -X utf8 -m experiment.tools.analyze_user_study

# Streamlit 설문 앱 (로컬)
streamlit run user_study_app/app.py
```

## 데이터

- **food_master** (Supabase): 3,358행 — 편의점·프랜차이즈·영양DB 통합, 5-class 분류 (MAIN/SOUP/SIDE/DRINK/SNACK), cuisine_type 분류
- 구축 과정은 `pipeline/` Step 0~7 및 [PIPELINE_PROGRESS.md](PIPELINE_PROGRESS.md) 참조

## 의존성

주요 라이브러리: `pymoo`(최적화), `networkx`(KG), `supabase`, `pandas`, `numpy`, `scipy`, `matplotlib`, `streamlit`, `google-genai`, `groq`
