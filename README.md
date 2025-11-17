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
