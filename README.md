# 🥗 예산 기반 AI 식단 추천 서비스

사용자가 **예산(예: 7,000원)**을 입력하면 AI가 그 금액 내에서 **영양 균형을 맞춘 구체적인 식품 조합**을 자동으로 추천하는 서비스입니다.

---

## 🎯 핵심 가치

| 구분 | 설명 |
|------|------|
| **편의성** | 수동 입력 최소화 (6단계 → 4단계) |
| **경제성** | 예산 제약 내 영양 균형 최적화 |
| **사회적 가치** | 건강 불평등 완화에 기여 |

---

## 📊 프로젝트 개요

### 타겟 사용자
- 대학생, 직장인
- 식단 관리를 원하지만 기존 앱의 번거로움과 식비 부담으로 어려움을 겪는 사용자

### 기존 앱의 문제점

#### 1. 직접 입력의 번거로움
- 사용자의 **36.8%**: "시간이 너무 많이 소요됨"
- **72%**: 건강 앱을 지속적으로 사용하지 않음
- 사진 촬영, 음식 검색 등 반복적인 수동 작업

#### 2. 경제적 부담 미고려
- 직장인의 **63.6%**: 점심값 부담 느낌
- 평균 점심값(7,761원) vs 적정 금액(6,076원) → **1,700원 격차**
- **44.8%**: 건강관리를 위한 식비 지출 시 경제적 어려움

### 서비스 차별화

#### 이용 흐름 비교
| 단계 | 기존 서비스 | 신규 서비스 |
|------|------------|------------|
| 1단계 | 앱 실행 | 앱 실행 |
| 2단계 | 음식 **직접 검색/입력** | **예산 선택** (7,000원) |
| 3단계 | 영양소 추적 및 기록 관리 | **AI 기반 식사 조합 추천** |
| 4단계 | 지속적 수동 관리 | **원터치 입력 완료** |

#### 핵심 차별화 요소

1. **AI 기반 맞춤형 추천**
   - 신체 스펙 + 건강 목표 + **예산 범위** 고려
   - 영양 균형을 맞춘 최적 식단 자동 구성

2. **구체적 식품 추천**
   - 예: "5,000원 → 편의점 참치마요 삼각김밥 + 프로틴 음료"
   - 실시간 가격 데이터 연동

3. **원터치 기록 시스템**
   - 추천 식단을 원터치로 선택 및 기록
   - 사용자 시간과 노력 획기적 절약

---

## 📈 시장 타당성

### 시장 기회
- **예산 현실성**: 제안 범위(7,000~10,000원)는 매우 현실적
- **시장 규모**: 글로벌 다이어트 앱 시장 2032년까지 **12억 5천만 달러** 성장 예상
- **블루오션**: 예산 기반 추천 서비스는 현재 시장에 드물음

### 기술적 실현 가능성
- AI 추천 정확도: **95% 이상** 목표
- 실시간 가격 API 연동 기술 성숙도 높음
- 영양 분석 알고리즘 구현 가능

---

## 🛠️ 기술 스택

### 개발 환경
- **언어**: Python 3.12+
- **가상환경**: venv
- **패키지 관리**: pip

### 주요 라이브러리

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| selenium | 4.27.1 | 웹 크롤링 (동적 콘텐츠) |
| webdriver-manager | 4.0.2 | Chrome 드라이버 관리 |
| beautifulsoup4 | 4.12.3 | HTML 파싱 |
| pandas | 2.2.3 | 데이터 처리 |
| requests | 2.32.3 | API 호출 |
| ortools | 9.7.2996 | 최적화 알고리즘 (선형계획법) |
| sqlite3 | (built-in) | 데이터베이스 |

---

## 📁 프로젝트 구조

```
diet_recommendation/
├── venv/                          # 가상환경
├── config/
│   ├── __init__.py
│   └── settings.py                # 프로젝트 설정
├── data/
│   ├── raw/                       # 크롤링 원본 데이터 ✅
│   │   ├── cu_products.csv
│   │   ├── gs25_products.csv
│   │   ├── seven_products.csv
│   │   ├── emart24_products.csv
│   │   └── all_stores_products.csv
│   ├── processed/                 # 전처리 데이터 (예정)
│   └── test/                      # 테스트 데이터
├── crawlers/                      # 크롤링 스크립트 ✅
│   ├── __init__.py
│   ├── cu_crawler_final.py
│   ├── gs25_crawler.py
│   ├── seven_crawler.py
│   ├── emart24_crawler.py
│   └── crawl_all_stores.py
├── database/                      # DB 관련 (예정)
│   └── nutrition_data.db          # SQLite DB (생성 예정)
├── algorithm/                     # 추천 알고리즘 (예정)
│   ├── __init__.py
│   ├── optimizer.py               # OR-Tools 기반 최적화
│   ├── matcher.py                 # 제품명 매칭 로직
│   └── recommender.py             # 추천 엔진
├── utils/                         # 유틸리티 함수 (예정)
│   ├── __init__.py
│   ├── data_loader.py
│   └── validators.py
├── tests/                         # 테스트 코드
├── requirements.txt               # 패키지 목록
├── .gitignore
├── API_GUIDE.md                   # 공공 API 사용법
├── SIMPLE_DB_DESIGN.md            # DB 설계 가이드
└── README.md                      # 이 파일
```

---

## 🚀 빠른 시작

### 1. 환경 설정

#### Windows
```bash
# 프로젝트 폴더 이동
cd diet_recommendation

# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

#### Mac / Linux
```bash
cd diet_recommendation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 데이터 수집

#### 편의점 가격 데이터 크롤링
```bash
# 모든 편의점 통합 크롤링
python crawlers/crawl_all_stores.py

# 개별 편의점
python crawlers/cu_crawler_final.py
python crawlers/gs25_crawler.py
python crawlers/seven_crawler.py
python crawlers/emart24_crawler.py
```

**결과**: `data/raw/` 폴더에 CSV 파일 생성

### 3. 데이터베이스 구축 (준비 중)

#### 단계 1: 공공 API로 영양정보 수집
```python
# database/build_nutrition_db.py 실행 (예정)
python database/build_nutrition_db.py
```

#### 단계 2: 제품명 매칭
```python
# algorithm/matcher.py 실행 (예정)
python algorithm/matcher.py
```

---

## 📊 현재 진행 상황

### ✅ Phase 1: 데이터 수집 (완료)
- [x] CU 편의점 크롤링 (~100개 제품)
- [x] GS25 편의점 크롤링 (~80개 제품)
- [x] 7-Eleven 편의점 크롤링 (~70개 제품)
- [x] Emart24 편의점 크롤링 (~150개 제품)
- [x] 데이터 통합 및 정제

**수집 현황**: 총 ~400-500개 제품 데이터

### 🔄 Phase 2: 영양정보 통합 (진행 예정)
- [ ] 공공 API로 식품영양정보 수집 (~92,000개)
- [ ] SQLite 데이터베이스 구축
- [ ] 제품명과 식품 자동 매칭
- [ ] 매칭 검증 및 수정

### 📅 Phase 3: 데이터 전처리 (예정)
- [ ] 결측치 처리
- [ ] 이상치 제거
- [ ] 데이터 정규화
- [ ] 캐시 테이블 생성

### 🧠 Phase 4: 알고리즘 개발 (예정)
- [ ] OR-Tools 기반 최적화 알고리즘 개발
- [ ] 목표별 추천 로직 (다이어트, 근육증가, 균형)
- [ ] 영양 점수 계산
- [ ] 비용 효율성 지수 개발

### 🎯 Phase 5: 프로토타입 (예정)
- [ ] CLI 기반 추천 시스템
- [ ] API 서버 (선택)
- [ ] 웹 UI (선택)

---

## 📝 데이터베이스 설계

### nutrition 테이블 (공공 API)
```sql
CREATE TABLE nutrition (
    id INTEGER PRIMARY KEY,
    food_code TEXT UNIQUE NOT NULL,
    food_name TEXT NOT NULL,
    food_group TEXT,
    food_standard TEXT,
    energy REAL,           -- kcal
    protein REAL,          -- g
    fat REAL,              -- g
    carbohydrate REAL,     -- g
    sugar REAL,
    fiber REAL,
    calcium REAL,
    iron REAL,
    sodium REAL,
    -- ... 기타 영양소
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### products 테이블 (크롤링)
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    product_code TEXT UNIQUE NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT,
    price REAL NOT NULL,
    store_name TEXT NOT NULL,
    location TEXT,
    image_url TEXT,
    nutrition_food_code TEXT,      -- nutrition 테이블과 연결
    match_confidence REAL,         -- 매칭 신뢰도 (0-1)
    manually_verified BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔗 API 정보

### 공공 API: 전국통합식품영양성분정보

**엔드포인트**
```
https://api.data.go.kr/openapi/tn_pubr_public_nutri_info_api
```

**인증키**
```
ba3c5e17002f3a476792cc25414bc972865b5360a19bfc9d1d5bdcda8038ada7
```

**유효기간**
- 2025-11-01 ~ 2027-11-01

**데이터 규모**
- 약 92,000개 식품
- 페이지당 최대 100개
- 약 920페이지

**자세한 사용법**: [API_GUIDE.md](./API_GUIDE.md) 참고

---

## 🧮 추천 알고리즘

### 목적함수
```
Maximize: Σ(nutrition_score_i × x_i)

nutrition_score = (protein × 4 + fiber × 2) / price

where x_i = 각 제품 선택 개수
```

### 제약조건
1. **가격 제약**: `Σ(price_i × x_i) ≤ budget` (예: 7,000원)
2. **칼로리 범위**: `target × 0.9 ≤ Σ(calories_i) ≤ target × 1.1`
3. **영양소 비율**: 탄수화물 50-60%, 단백질 15-25%, 지방 20-30%
4. **필수 영양소**: 단백질 ≥ 20g, 나트륨 ≤ 2000mg
5. **정수 제약**: `0 ≤ x_i ≤ 3` (중복 선택 최대 3개)

### 사용자 목표 타입
- **다이어트**: 저칼로리, 고단백 (단백질 25%+)
- **근육 증가**: 고단백, 적정 탄수화물 (단백질 30%+)
- **균형 식단**: 표준 탄단지 비율

---

## 📖 사용 예시

### (준비 중) CLI 실행 예시
```bash
python main.py --budget 7000 --goal balanced --store CU
```

**출력**:
```
🥗 예산 7,000원 내 추천 식단 (균형식)

1. 참치마요 삼각김밥 (CU) - 2,500원
   - 단백질: 8g
   - 칼로리: 200kcal
   - 나트륨: 450mg

2. 프로틴 요구르트 (CU) - 2,800원
   - 단백질: 15g
   - 칼로리: 120kcal
   - 나트륨: 100mg

3. 당근 스틱 (CU) - 1,500원
   - 단백질: 1g
   - 칼로리: 40kcal
   - 나트륨: 50mg

---
📊 총합
- 총 가격: 6,800원 (남은 예산: 200원)
- 총 칼로리: 360kcal
- 총 단백질: 24g
- 나트륨: 600mg
- 영양 점수: 8.5/10

✅ 추천 완료!
```

---

## 🔧 개발 가이드

### 새로운 기능 추가

#### 1. 새로운 편의점 크롤러 추가
```python
# crawlers/new_store_crawler.py 생성
class NewStoreCrawler:
    def __init__(self):
        self.base_url = "..."
    
    def crawl(self):
        # 크롤링 로직
        pass
    
    def save_to_csv(self, data):
        # CSV 저장
        pass
```

#### 2. 새로운 DB 테이블 추가
```python
# database/schema.py에 테이블 정의 추가
cursor.execute('''
    CREATE TABLE new_table (
        id INTEGER PRIMARY KEY,
        ...
    )
''')
```

#### 3. 새로운 알고리즘 추가
```python
# algorithm/new_algorithm.py 생성
class NewAlgorithm:
    def __init__(self, products, nutrition):
        self.products = products
        self.nutrition = nutrition
    
    def recommend(self, budget, goal):
        # 추천 로직
        pass
```

---

## 🐛 문제 해결

### 크롤링 오류
- **문제**: Selenium 드라이버 찾을 수 없음
- **해결**: `webdriver-manager` 재설치
  ```bash
  pip install --upgrade webdriver-manager
  ```

### API 호출 실패
- **문제**: `403 Forbidden` 오류
- **해결**: API 키 활성화 확인 (24시간 소요)

### 매칭 실패
- **문제**: 제품명과 식품명이 완벽히 일치하지 않음
- **해결**: 수동 검증 후 `manually_verified` 플래그 설정

---

## 📚 참고 자료

### 알고리즘
- [Stigler's Diet Problem](https://en.wikipedia.org/wiki/Stigler%27s_diet_problem)
- [Google OR-Tools 문서](https://developers.google.com/optimization)
- [선형계획법 기초](https://en.wikipedia.org/wiki/Linear_programming)

### 웹 크롤링
- [Selenium 공식 문서](https://www.selenium.dev/documentation/)
- [BeautifulSoup 문서](https://www.crummy.com/software/BeautifulSoup/)

### 식품 데이터
- [식품의약품안전처 식품영양성분 DB](https://www.foodsafetykorea.go.kr/fcdb/)
- [공공데이터포털](https://www.data.go.kr/)

---

## 📞 문의 및 기여

### 기여 방법
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### 버그 리포트
[Issues](https://github.com/yourname/diet-recommendation/issues) 탭에서 버그 보고

---

## 📜 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다. [LICENSE](./LICENSE) 파일 참고

---

## 🎓 학습 목표

이 프로젝트를 통해 다음을 학습합니다:

- ✅ 웹 크롤링 (Selenium, BeautifulSoup)
- ✅ REST API 호출 및 데이터 처리
- ✅ 데이터베이스 설계 및 구축 (SQLite)
- ✅ 선형계획법 및 최적화 알고리즘 (OR-Tools)
- ✅ 데이터 매칭 및 정규화
- ✅ 프로젝트 관리 및 협업

---

## 📈 향후 계획 (Roadmap)

### v1.0 (MVP)
- [x] 데이터 수집 완료
- [ ] 기본 추천 알고리즘
- [ ] CLI 인터페이스

### v1.1 (Beta)
- [ ] API 서버 구축
- [ ] 사용자 선호도 학습
- [ ] 더 많은 편의점 추가

### v2.0 (Production)
- [ ] 웹 UI/UX
- [ ] 모바일 앱
- [ ] 실시간 가격 업데이트
- [ ] AI 기반 개인화 추천

---

## ✨ 핵심 성공 요인

1. **시장 수요 충족**: 사용자 부담(시간+비용) 동시 해결
2. **기술적 차별화**: 예산 제약 + 영양 최적화 동시 구현
3. **지속 가능성**: 반복 사용 → AI 학습 → 정확도 향상

---

**마지막 업데이트**: 2025년 11월 3일

**프로젝트 진행률**: Phase 1 완료 (약 20%)

---

*이 프로젝트는 건강 불평등을 완화하고, 대학생과 직장인이 경제적 부담 없이 건강한 식단을 유지하도록 돕기 위해 시작되었습니다.* 🥗✨

**주요 변경 사항:**

1.  **알고리즘 설명 수정:** 단순 선형계획법(Linear Programming)에서 **'몬테카를로 시뮬레이션 + 파레토 최적화'** 방식으로 변경된 로직을 반영했습니다. (v1.6 코드 기준)
2.  **진행 상황(Status) 업데이트:** 데이터 수집 단계를 넘어 **데이터 매칭(RapidFuzz 도입)** 및 **추천 알고리즘(v1.6)** 구현이 완료된 상태로 변경했습니다.
3.  **기술 스택 추가:** `rapidfuzz` (고속 데이터 매칭), `tqdm` 등 실제 사용된 라이브러리를 추가했습니다.
4.  **프로젝트 구조 현행화:** 실제 파일명(`daily_diet_optimizer_1.6.py` 등)에 맞춰 트리 구조를 수정했습니다.

아래 마크다운 코드를 그대로 복사하여 `README.md` 파일에 덮어쓰시면 됩니다.

-----

````markdown
# 🥗 예산 기반 편의점 AI 식단 추천 서비스 (Diet Recommendation)

사용자가 **예산(예: 7,000원)**과 **목표(다이어트/근육증가/건강관리)**를 입력하면, AI가 편의점 음식 중에서 **영양 균형(탄단지 비율)과 나트륨/당류 제약**을 고려한 최적의 조합을 찾아 추천해주는 서비스입니다.

---

## 🎯 핵심 가치

| 구분 | 설명 |
|------|------|
| **초개인화** | 사용자 체중, 목표, **알레르기 정보**까지 고려한 맞춤 추천 |
| **경제성** | 예산 제약 내에서 영양소 섭취를 극대화하는 가성비 식단 |
| **접근성** | 접근성이 높은 4대 편의점(CU, GS25, 세븐일레븐, 이마트24) 통합 지원 |

---

## 📊 프로젝트 개요

### 1. 문제 정의
- **식비 부담**: 직장인 평균 점심값 상승(런치플레이션)으로 인한 경제적 부담
- **영양 불균형**: 저렴한 편의점 음식은 '건강에 나쁘다'는 인식과 실제 고나트륨/고탄수화물 문제
- **선택의 어려움**: 수많은 제품 중 영양 성분을 일일이 확인하고 조합하기 번거로움

### 2. 솔루션: AI 영양사
- **시뮬레이션 기반 추천**: 10만 번 이상의 식단 조합 시뮬레이션을 통해 최적의 해답 도출
- **파레토 최적화**: 가격은 낮추면서 영양 오차는 줄이는 '파레토 효율적' 식단 선별
- **데이터 기반**: 공공데이터포털의 영양정보와 편의점 실시간 가격 정보 매칭

---

## 🛠️ 기술 스택 (Tech Stack)

### 개발 환경
- **Language**: Python 3.12+
- **Version Control**: Git
- **Virtual Env**: venv

### 핵심 라이브러리
| 라이브러리 | 용도 | 비고 |
|-----------|------|------|
| **Pandas** | 데이터 전처리 및 분석 | 결측치 처리, 데이터 프레임 관리 |
| **Selenium** | 웹 크롤링 | 동적 페이지(편의점 행사 상품 등) 수집 |
| **RapidFuzz** | 고속 텍스트 매칭 | 제품명과 영양성분 DB 간 유사도 매칭 (최적화) |
| **FuzzyWuzzy** | 문자열 유사도 분석 | 보조 매칭 알고리즘 |
| **Tqdm** | 진행률 시각화 | 데이터 처리 과정 모니터링 |

---

## 📁 프로젝트 구조 (Current Structure)

```bash
diet_recommendation/
├── venv/
├── config/
│   └── settings.py                # 프로젝트 설정
├── data/
│   ├── raw/                       # 크롤링 원본 데이터
│   │   ├── all_stores_products.csv # 4대 편의점 통합 데이터
│   │   └── ...
│   └── processed/                 # 전처리 및 매칭 완료 데이터
│       ├── final_nutrition_db.csv
│       └── matched_nutrition_db.csv
├── crawlers/                      # 데이터 수집 (크롤러)
│   ├── crawl_all_stores.py        # 통합 크롤링 실행 스크립트
│   ├── cu_crawler_final.py
│   ├── gs25_crawler.py
│   ├── seven_crawler.py
│   └── emart24_crawler.py
├── algorithm/                     # 추천 알고리즘 엔진
│   ├── daily_diet_optimizer_2.6_test.py  # ✅ v2.6 실행 파일 (병렬 처리+시각화)
│   └── daily_diet_optimizer_2.5.py       # (Legacy) v2.5 로직
├── utils/
│   └── master_db_merge.py         # 제품명-영양정보 매칭 (RapidFuzz 적용)   
│   └── fill_real_prices.py        # 가격 보정 로직       
├── requirements.txt               # 의존성 패키지 목록
└── README.md
````

-----

## 🚀 기능 및 알고리즘 (Algorithm)

본 프로젝트는 단순한 랜덤 추천이 아닌, **영양학적 목표를 달성하기 위한 수학적 알고리즘**을 사용합니다.

### 1\. 데이터 수집 및 매칭 (Data Pipeline)

  - **크롤링**: Selenium을 이용해 4대 편의점(CU, GS25, 7-Eleven, Emart24)의 신선식품/간편식 가격 정보를 수집합니다.
  - **Fuzzy Matching**: `RapidFuzz`를 활용하여 크롤링한 '상품명'과 식약처 '영양성분 DB'를 유사도 기반으로 자동 매칭합니다. (정확도 90% 이상)

### 2\. 추천 엔진 (Optimization Engine v1.6)

**DailyDietOptimizer**는 다음 과정을 통해 식단을 생성합니다:

1.  **필터링 (Filtering)**:
      * 사용자 알레르기 유발 성분(예: 난류, 땅콩) 제외
      * 예산 범위 및 최소 칼로리 조건 확인
2.  **몬테카를로 시뮬레이션 (Monte Carlo Simulation)**:
      * 약 100,000가지 이상의 메뉴 조합을 무작위 생성
3.  **영양 적합성 평가 (Validation)**:
      * **EER 비율**: 탄수화물/단백질/지방 비율이 목표(다이어트 등)에 부합하는지 검사
      * **제약 조건**: 나트륨(2500mg 이하), 당류(총 칼로리의 10% 이하) 제한 준수 여부 확인
4.  **파레토 최적화 (Pareto Optimization)**:
      * **다목적 최적화**: '가격 최소화'와 '영양 오차 최소화'라는 상충되는 목표를 동시에 만족하는 \*\*파레토 최적해(Pareto Frontier)\*\*를 도출하여 최종 추천

-----

## 💻 빠른 시작 (Quick Start)

### 1\. 환경 설정 및 설치

```bash
# 레포지토리 클론 (예시)
git clone [https://github.com/username/diet-recommendation.git](https://github.com/username/diet-recommendation.git)

# 가상환경 생성 및 활성화
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 필수 패키지 설치
pip install -r requirements.txt
```

### 2\. 데이터 수집 (크롤링)

최신 편의점 가격 정보를 가져오려면 아래 명령어를 실행하세요.

```bash
python crawlers/crawl_all_stores.py
```

> 결과 파일은 `data/raw/all_stores_products.csv`에 저장됩니다.

### 3\. 데이터 매칭 (전처리)

수집된 가격 데이터와 영양 정보를 매칭합니다. (RapidFuzz 사용)

```bash
python data/master_db_merge.py
```

### 4\. 식단 추천 실행

AI 추천 엔진을 실행하여 결과를 확인합니다.

```bash
python algorithm/daily_diet_optimizer_1.6.py
```

-----

## 📊 개발 진행 상황 (Dev Status)

### ✅ Phase 1: 데이터 인프라 구축 (완료)

  - [x] 4대 편의점(CU, GS25, 7-Eleven, Emart24) 크롤러 구현 완료
  - [x] 식약처 영양성분 데이터베이스 확보
  - [x] **RapidFuzz 기반** 대용량 텍스트 매칭 파이프라인 구축 (`master_db_merge.py`)

### ✅ Phase 2: 알고리즘 고도화 (완료)

  - [x] 영양소 섭취 비율(탄단지) 계산 로직 구현
  - [x] 나트륨, 당류, 포화지방 등 건강 위험 요소 제약 조건 추가
  - [x] 알레르기 필터링 기능 구현
  - [x] **v1.6 업데이트**: 몬테카를로 시뮬레이션 및 파레토 최적화 적용으로 추천 품질 향상

### 🔄 Phase 3: 서비스 확장 (진행 중)

  - [ ] 사용자 인터페이스(UI) 개발 (Web/App)
  - [ ] 실제 편의점 재고 API 연동 (Future Work)
  - [ ] 추천 속도 최적화

-----

## 📝 라이선스

MIT License

-----

*Last Updated: 2025.11 (v1.6)*

```
---

# 🚀 [업데이트] 알고리즘 고도화 (Algorithm v2.6)

기존 선형 계획법(v1.0)에서 진화하여, **다양성(Diversity)**과 **현실성(Feasibility)**을 대폭 강화한 최신 추천 엔진입니다.

## 1. 🧠 핵심 로직 개선 사항

| 구분 | v1.x (초기 모델) | **v2.6 (현재 모델)** |
| :--- | :--- | :--- |
| **목표 설정** | 고정 비율 (단순 N빵) | **체중 기반 동적 할당** (사용자 체중 × 목표 계수) |
| **식단 구성** | 단순 영양소 최적화 | **브랜드 세트(One-Stop) + 카테고리 템플릿** |
| **다양성** | 고려 없음 | **해밍 거리(Hamming Distance) + 재료 중복 방지** |
| **실패 처리** | 추천 실패 | **3단계 재시도 전략** (Strict → Relaxed → Fallback) |

### 상세 로직 설명
1.  **동적 목표 할당:** 하루 목표(P/C/F)를 설정하고, 이전 끼니의 섭취량에 따라 남은 끼니의 목표를 자동으로 보정합니다.
2.  **3단계 재시도 전략:**
    * **1차(Strict):** 영양 목표 95% 이상 + 브랜드 중복 금지 (최적해)
    * **2차(Relaxed):** 영양 목표 70% 이상 + 브랜드 유지 (다양성 우선)
    * **3차(Fallback):** 브랜드 제약 해제 (최후의 수단)
3.  **다양성 필터링:** `밥+밥` 같은 탄수화물 중복이나 `참치+참치` 같은 재료 중복을 수학적으로 계산하여 차단합니다.

---

## 🏗️ 데이터 파이프라인 & 아키텍처
diet_recommendation/
├── venv/
├── config/
│   └── settings.py                # 프로젝트 설정
├── data/
│   ├── raw/                       # 크롤링 원본 데이터
│   │   ├── all_stores_products.csv # 4대 편의점 통합 데이터
│   │   └── ...
│   └── processed/                 # 전처리 및 매칭 완료 데이터
│       ├── final_nutrition_db.csv
│       └── matched_nutrition_db.csv
├── crawlers/                      # 데이터 수집 (크롤러)
│   ├── crawl_all_stores.py        # 통합 크롤링 실행 스크립트
│   ├── cu_crawler_final.py
│   ├── gs25_crawler.py
│   ├── seven_crawler.py
│   └── emart24_crawler.py
├── algorithm/                     # 추천 알고리즘 엔진
│   ├── daily_diet_optimizer_2.6_test.py  # ✅ v2.6 실행 파일 (병렬 처리+시각화)
│   └── daily_diet_optimizer_2.5.py       # (Legacy) v2.5 로직
├── utils/
│   └── master_db_merge.py         # 제품명-영양정보 매칭 (RapidFuzz 적용)   
│   └── fill_real_prices.py        # 가격 보정 로직       
├── requirements.txt               # 의존성 패키지 목록
└── README.md

## 📊 최신 개발 진행률 (Update)

### ✅ Phase 1.5: 데이터 고도화 (완료)
- [x] **통합 마스터 DB 구축:** 공공 데이터 포털 영양정보 + 5대 편의점/프랜차이즈 가격 매칭 완료
- [x] **가격 보정:** 결측된 가격 정보를 카테고리별 표준 가격으로 보정 (`fill_real_prices.py`)

### ✅ Phase 2: 알고리즘 최적화 (완료)
- [x] **파레토 최적화:** 가격 vs 영양 오차 상충 관계 해결
- [x] **다양성 알고리즘:** 해밍 거리(Hamming Distance) 기반 메뉴 추천 다양화
- [x] **시뮬레이션 검증:** 1,000명 랜덤 유저 대상 병렬 처리 성능 테스트 완료 (`2.6_test.py`)

### 🔜 Phase 4: 개인화 추천 (진행 예정)
- [ ] 사용자 선호도(맛, 재료) 학습을 위한 딥러닝 모델(NCF) 도입 준비
- [ ] 실제 사용자 피드백 데이터 수집 파이프라인 설계

---

*Last Updated: 2025.12 (Logic v2.6 Applied)*