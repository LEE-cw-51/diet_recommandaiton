# 예산 기반 식단 추천 시스템

사용자의 예산과 건강 목표를 입력받아 편의점·프랜차이즈 음식 중 영양 균형에 최적화된 하루 식단을 추천하는 알고리즘.

## 프로젝트 구조

```
diet_recommendation/
├── algorithm/                        # 핵심 추천 알고리즘
│   ├── daily_diet_optimizer.py       # 메인 알고리즘 (v2.6 기반)
│   └── matcher.py                    # 제품명-영양정보 퍼지 매칭
│
├── crawlers/                         # 데이터 수집 크롤러
│   ├── convenience/                  # 편의점 (CU, GS25, 7-Eleven, Emart24)
│   ├── franchise/                    # 프랜차이즈 (버거킹, 롯데리아, 맥도날드, 맘스터치)
│   └── run_all.py                    # 전체 편의점 통합 크롤링 실행
│
├── pipeline/                         # 단계별 데이터 처리
│   ├── 01_parse/                     # HTML/Excel 원본 파싱
│   ├── 02_clean/                     # 매장별 데이터 클렌징
│   ├── 03_enrich/                    # 영양소·가격 결측치 보정
│   └── 04_merge/                     # 통합 DB 병합
│
├── api/                              # 영양성분 공공 API 연동
│   ├── nutrition_api_client.py       # 공공데이터포털 API 클라이언트
│   ├── api_cache.py                  # 중복 호출 방지 캐시
│   └── api_to_db.py                  # API 결과 -> DB 반영
│
├── qa/                               # 데이터 품질 검증
│   ├── verify_final_db.py
│   ├── analyze_providers.py
│   └── check_standard_duplicates.py
│
├── data/
│   ├── raw/
│   │   ├── convenience/              # 편의점 크롤링 결과 CSV
│   │   ├── franchise/                # 프랜차이즈 데이터 (CSV, xlsx, pdf)
│   │   └── html/                     # HTML 원본 파일
│   └── processed/                    # 가공 완료 데이터
│       └── final_nutrition_db.csv    # 최종 통합 DB
│
├── database/                         # SQLite DB 및 원본 JSON
├── config/settings.py                # 프로젝트 설정 (API 키, 경로 등)
├── archive/algorithm/                # 구버전 알고리즘 보관 (v1.0 ~ v2.5.2)
└── tests/
```

## 데이터 처리 흐름

```
[크롤링]  crawlers/run_all.py
              |
[파싱]    pipeline/01_parse/
              |
[클렌징]  pipeline/02_clean/
              |
[병합]    pipeline/04_merge/merge_franchise_db.py
              |
[보정]    pipeline/03_enrich/   +   api/api_to_db.py
              |
[검증]    qa/verify_final_db.py
              |
[추천]    algorithm/daily_diet_optimizer.py
```

## 알고리즘 개요 (v2.6)

- **몬테카를로 시뮬레이션**: 20,000회 식단 조합 무작위 생성
- **파레토 최적화**: 가격 최소화 vs 영양 오차 최소화 균형
- **3단계 재시도 전략**: Strict -> Relaxed -> Fallback
- **해밍 거리 다양성**: 카테고리 중복 방지

## 실행 방법

```bash
# 알고리즘 실행
python algorithm/daily_diet_optimizer.py

# 크롤링 실행
python crawlers/run_all.py

# DB 검증
python qa/verify_final_db.py

# API로 결측 영양성분 보완
python api/api_to_db.py
```

## 설정

`config/settings.py`에서 다음을 설정:
- `NUTRITION_API_KEY`: 공공데이터포털에서 발급받은 API 키
- `DATA_RAW`, `DATA_PROCESSED`: 데이터 저장 경로

## 데이터 현황

| 구분 | 매장 | 상태 |
|------|------|------|
| 편의점 | CU, GS25, 세븐일레븐, 이마트24 | 크롤링 완료 |
| 프랜차이즈 | 버거킹, 롯데리아, 맥도날드, 맘스터치, 서브웨이, 샐러디, PREPS | 수집 완료 |

## 의존성

```bash
pip install -r requirements.txt
```

주요 라이브러리: `pandas`, `numpy`, `selenium`, `rapidfuzz`, `ortools`, `matplotlib`
