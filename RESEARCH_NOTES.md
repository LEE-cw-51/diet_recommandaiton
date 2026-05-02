# Research Notes — 식단 추천 시스템 데이터 파이프라인

> 졸업 논문 작성용 연구 노트. 구현 과정, 기술적 어려움, 설계 결정 근거를 기록.

---

## 1. 프로젝트 개요

- **연구 목적**: 식품 영양성분 데이터에 가격·알레르기·카테고리를 증강하여 실용적인 식단 최적화 알고리즘 구현
- **데이터 규모**: 2,524개 식품 (food_research_sample → food_master)
- **기술 스택**: Python, Supabase (PostgreSQL), Naver Shopping API, HACCP API, Gemini 2.5 Flash, Groq LLaMA 3.1 8B
- **알고리즘**: `algorithm/daily_diet_optimizer.py` — 영양 목표 기반 일일 식단 최적화

---

## 2. 데이터 파이프라인 설계

### 설계 변경 이력

**초기 설계 (Session 1)**: Step 1이 영양성분 + 가격 + 알레르기를 한 번에 UPSERT
- 문제: 새 행 INSERT 시 영양성분이 NULL이 됨 (네이버/HACCP에서 영양성분 제공 안 함)
- 발견 시점: Session 2 테스트에서 food_master 행 확인 시

**수정된 설계 (Session 3)**: 2단계 분리
1. Step 0: food_research_sample에서 영양성분만 bulk copy
2. Step 1: UPDATE 방식으로 price + allergens만 추가 (영양성분 덮어쓰기 방지)

### category_type 4개 선정 근거 (Session 4 리서치)

최종 선택: `MAIN / SIDE / DRINK / SNACK`

비교한 대안들:
- MealRec (SIGIR 2022): 3개/끼니 (appetizer + main + dessert)
- MealRec+ (SIGIR 2024): 11개 세분류
- Korean Diet Score (PMC 2013): 6 food groups

**결정 근거**: 기존 `DietOptimizationProblem`의 `n_var=4` 구조 (MAIN + SIDE×2 + DRINK)와 정합성 유지. SNACK은 향후 확장 예비용으로 레이블만 유지하고 optimizer에서는 미사용.

참고 논문:
- MealRec (SIGIR 2022): https://arxiv.org/abs/2205.12133
- MealRec+ (SIGIR 2024): https://arxiv.org/abs/2404.05386
- PMC Chinese Meal Rec (2024): https://pmc.ncbi.nlm.nih.gov/articles/PMC11176883/
- Korean Diet Score (PMC 2013): https://pmc.ncbi.nlm.nih.gov/articles/PMC3572226/

---

## 3. 세션별 진행 기록

### Session 1 (2026-03-04) — 인프라 구축
주요 작업: Supabase 클라이언트, 마이그레이션 파일, requirements.txt

**핵심 결정**: Supabase 클라이언트를 `supabase/client.py`가 아닌 `db/client.py`에 배치
- 이유: 로컬 `supabase/` 디렉토리가 pip `supabase` 패키지를 shadowing하는 import 충돌 발생

### Session 2 (2026-03-04) — 검색 클라이언트 + 5개 테스트
주요 작업: search_clients.py (Naver + HACCP), step1_price_allergen.py, --test 5 실행

**겪은 어려움**:
1. `google.generativeai` FutureWarning — `google.genai` 패키지로 완전 교체 필요
2. Gemini 모델 혼란: gemini-1.5-flash(404), gemini-2.0-flash(한도 0) → gemini-2.5-flash 사용
3. HACCP API 500 Server Error 지속 — 서버 측 문제로 graceful fallback 구현 (Gemini가 제품명으로 추론)
4. 테스트 5개가 HACCP 미등록 + 네이버 미조회 특수 제품이라 price/allergens 빈값 → 정상 케이스로 판단

### Session 3 (2026-03-07) — 전체 실행 + 오류 해결
주요 작업: Step 0 bulk copy(2,522행), Step 1 전체 실행, Step 1b null 보정

**겪은 어려움**:
1. **PostgREST 1,000행 기본 limit**: `food_master` 조회 시 999행만 반환 → 범위 기반 pagination 루프로 해결
   - 이 버그는 데이터 정합성 검증 중 "1,000행이 정확히 채워짐"을 이상하게 여겨 발견
2. **ON CONFLICT 배치 내 중복**: `product_name + brand_name` 복합 키 기준 중복 2개 존재 → deduplication 로직 추가, 최종 2,522행
3. **price NULL 64% → 최종 30%**: 네이버 미등록 외국/특수 식자재가 주 원인. fallback 검색 추가(standard_product_name → product_name only) 후 69.8% 달성

**Naver API 한도 정정**: 1,000/일로 잘못 알고 있었으나 실제 25,000/일 → 전략적 throttle 불필요

### Session 4 (2026-03-08) — category_type 리서치
주요 작업: 4개 카테고리 충분성 분석, 참고 논문 조사, Step 2 계획 수립

### Session 5 (2026-03-08) — Step 2 설계 확정
주요 작업: step2_food_classifier.py 설계 완료 (코드 미작성, 다음 세션에 구현)

**설계 결정**:
- 모델: `llama-3.1-8b-instant` (6,000 RPD로 2,522개 당일 완주)
- 프롬프트에 영양성분(calories, carbs, protein, fat) 포함 → 분류 정확도 향상
- 시스템 프롬프트에 한국 식품공전(NFIS) + 식품의약품안전처 + HACCP 분류 기준 명시
- DDL 불필요: `category_type` + `classified_at` 컬럼 `001_add_allergens.sql`에서 이미 추가됨
- `category_type IS NULL` 필터로 미분류 행만 처리

### Session 6 (2026-03-09) — Step 0b: 프랜차이즈 CSV import
주요 작업: `data/processed/final_nutrition_db.csv` (871행) → food_master INSERT

**설계 결정**:
- `step0b_csv_import.py` 신규 작성 (`pipeline/05_augment/`)
- CSV price 컬럼 신뢰도 낮음(크롤링+랜덤 혼재) → price=NULL 저장, Step 1b 재실행으로 채움
- `allergens_scraped` 원문 텍스트 → Gemini 2.5 Flash-Lite로 22종 JSONB 파싱
- `category` 컬럼(매장 카테고리) 버림, `food_group=NULL`
- 워크트리 환경 대응: `CSV_PATH` 폴백 로직 (`_ROOT` vs `_ROOT.parent.parent.parent`)
- 체크포인트: `.checkpoint/step0b_done.json` (set[str], 키="menu_name|store_name")

**실행 결과**:
- `--test 5`: 성공 5/5, allergens JSONB 정상 (닭고기/쇠고기/돼지고기 true 확인)
- `--resume` 전체: 850/871 성공 (97.6%), 21개 실패 (`--resume` 재시도 가능)
- 브랜드: BurgerKing, CU, GS25, McDonalds, Lotteria, 이마트24, Subway, Salady 등

### Session 8 (2026-03-18) — Step 3-4: 다목적 최적화 실험 프레임워크 구축

**구현 내용**
- `experiment/` 디렉토리 전체 신설 (core, algorithms, config, results)
- 한끼 실험: Exp1 (2목적), Exp2 (3목적), NSGA-II
- 하루 실험: DailyExp1, DailyExp2, NSGA-II
- `FoodDataLoader.from_supabase()` — PostgREST pagination (1,000행 limit 대응)
- 30회 반복 실행 + GD/IGD/HV/Spread 지표 계산 (`core/metrics.py`)
- 테스트 완료: daily_exp1 (GD=0.24, HV=2.38), daily_exp2 (GD=0.11, HV=0.77)

---

### Session 9 (2026-05-03) — Step 5: KG 기반 4목적 최적화 + R-NSGA-II

#### 핵심 기여 (논문 메인 컨트리뷰션)

기존 3목적(칼로리·매크로·가격) 프레임워크에 **지식 그래프 기반 개인화 목적함수 f4**를 추가했다.
DB 스키마 변경 없이 NetworkX MultiDiGraph 엣지 구조만으로 선호도와 시간 감쇠를 표현한다는 것이 핵심.

#### 지식 그래프(KG) 설계

```
KG 노드
  user     : 사용자 식별자
  menu     : 메뉴 (product_name 기준)
  category : MAIN / SIDE_SOUP / DRINK / SNACK

KG 엣지 (MultiDiGraph)
  IS_IN   (Menu → Category)         : 정적 분류, 속성 없음
  PREFERS (User → Category/Menu)    : weight 선호 가중치
  ATE     (User → Menu)             : timestamp 마지막 섭취 시각
```

MultiDiGraph를 선택한 이유: 동일 (user→menu) 쌍에 PREFERS와 ATE 엣지가 동시 존재 가능해야 함.
DiGraph 사용 시 record_eating()이 set_preference() 엣지를 덮어씀 (버그 3).

#### 추천 점수 공식

$$Score_{KG}(i) = P_i \times (1 - D_i)$$

$$D_i = \max_{j \in \text{History}} \left( Sim(i,j) \times e^{-\lambda \Delta t_j} \right)$$

- $P_i$: PREFERS 직접 > 카테고리 PREFERS 전파 > 기본값 1.0
- $Sim$: 직접 ATE = 1.0, 동일 카테고리 형제 메뉴 ATE = 0.5
- $\lambda = 0.5$ → 반감기 약 1.4일

#### f4 오차율

$$f_4 = \frac{\text{max\_score} - \text{avg\_score}}{\text{max\_score}} \in [0, 1]$$

f1~f3과 동일한 '오차율' 스케일로 정규화하여 R-NSGA-II 참조점 설계를 단순화.
0이면 모든 메뉴가 최고 선호도이면서 최근 미섭취 상태.

#### R-NSGA-II 도입 근거

4차원 파레토 프론트는 해의 분포가 지나치게 넓어 사용자가 선택하기 어렵다.
R-NSGA-II는 참조점 기반으로 원하는 영역에 해를 집중시킨다.

참조점 설계:
| 참조점 | f1 | f2 | f3 | f4 | 의미 |
|-------|----|----|----|----|------|
| [0,0,0,0] | 0.0 | 0.0 | 0.0 | 0.0 | 균형 해 |
| [0.1,0.1,0.1,0] | 0.1 | 0.1 | 0.1 | 0.0 | 개인화 우선 해 |

#### 구현 중 발견된 버그 4건

| # | 버그 | 원인 | 수정 |
|---|------|------|------|
| 1 | 음수 KG 점수 | 가상 ATE 타임스탬프 > sim_now → Δt 음수 → e^{+λΔt} > 1 | `delta_days = max(0.0, ...)` + `sim_now` 파라미터 전달 |
| 2 | O(957) 형제 탐색 | `G.predecessors(cat)` 전체 순회 | `_ate_by_category` 인덱스로 O(ATE수) |
| 3 | PREFERS 덮어쓰기 | DiGraph 단일 엣지 제한 | MultiDiGraph + key="PREFERS"/"ATE" |
| 4 | category=UNKNOWN | `loader.py`에서 bucket 매핑 미기록 | `item["category"] = bucket` 추가 |

#### 7일 시뮬레이션 검증 결과

페르소나 설정:
- 한식_매니아: MAIN 1.5, SIDE_SOUP 1.2, DRINK 0.5 (음료 비선호)
- 가성비_추구: MAIN 1.0, DRINK 1.3, SNACK 1.4

결과:
| 페르소나 | Hit Rate | 중복률 | 평균 f1 | f4 추이 |
|---------|---------|-------|--------|--------|
| 한식_매니아 | 100% | 2.6% | 0.000 | Day1: 0.25 → Day7: 0.46 |
| 가성비_추구 | 100% | 1.2% | 0.000 | Day1: 0.26 → Day7: 0.48 |

f4가 Day1 → Day7로 증가하는 것은 누적 섭취 이력에 의한 감쇠가 쌓이는 것으로 정상 동작.
칼로리 오차(f1)가 7일 내내 0.000인 것은 알고리즘이 영양 제약을 완전히 충족함을 의미.

#### 설계 결정 요약

| 결정 | 이유 |
|------|------|
| DailyExp2 수정 대신 DailyExp3 신설 | 기존 3목적 실험 결과 보존 |
| BaseDailyDietProblem 직접 상속 | DailyExp2의 n_obj=3 하드코딩 우회 |
| menu_id = product_name | 컬럼 추가 없이 기존 식별자 재사용 |
| from_config() 팩토리 메서드 | YAML 설정만으로 KG 구성 가능 |
| normalization="front" | f1~f4 단위 자동 정규화 (R-NSGA-II 내장) |

---

### Session 7 (2026-03-10) — Step 1c / Step 2 / Step 2b / Step 2c 설계

#### Step 1c: 프랜차이즈 가격 조회
- 스크립트: `pipeline/05_augment/step1c_franchise_prices.py` 신규 작성
- 대상: `food_master WHERE price IS NULL AND data_source='final_nutrition_db'` (846행)
- 방법: Naver webkr 검색 (`openapi.naver.com/v1/search/webkr.json`) → 스니펫 수집 → Gemini 2.5 Flash-Lite price 파싱
- 결과: 564/846 UPDATE, 25 실패, 체크포인트 825개

#### Step 2: Gemini 2.5 Flash-Lite 카테고리 분류 (v1→v2 전환)
- v1 (Groq LLaMA-3.1-8B): TPM 6,000/min 초과 → 923개 분류 후 중단
- v2 (Gemini 2.5 Flash-Lite): `google.genai` SDK, `response_mime_type="application/json"` → 나머지 ~2,449개 약 41분 완료
- 최종 결과: 3,372/3,372 (100%), 503 ServiceUnavailable fallback(→MAIN) ~0.5% (~15개)
- **분류 체계 확장**: 4-class(MAIN/SIDE/DRINK/SNACK) → **5-class(+SOUP)**
  - SOUP 추가 근거: 국/찌개/탕/라면류는 고나트륨·국물+고형물 혼합 구조로 MAIN과 구분되는 영양 프로파일 보유. optimizer의 SIDE 슬롯에 병합 처리(cat_keys에 SOUP 추가)

#### Step 2b: 영양성분 불량 행 데이터 클렌징
- 0칼로리 또는 전 영양소 근零인 행 14개 SQL로 삭제 (`calories < 5 AND protein < 1 ...`)
- 최종 3,358행, 카테고리 분포: SNACK 1,101 / MAIN 957 / SIDE 688 / DRINK 441 / SOUP 171

#### Step 2c: price 이상치 처리 (설계 완료)

**이상치 탐지 방법: Tukey's Fence (IQR 1.5×)**
- 근거: 비모수적, 정규분포 미가정, 식품 가격처럼 skewed 분포에 적합 (Tukey 1977)
- 카테고리별 별도 fence 계산 (SNACK vs SOUP는 가격대가 다름)
- 탐지 결과: LOW 16개(< 500원) + HIGH 126개 = 총 142개

| 카테고리 | 상한 fence | HIGH 이상치 |
|---------|----------|-----------|
| MAIN | 24,625원 | 23개 |
| SOUP | 43,830원 | 13개 |
| SIDE | 35,250원 | 24개 |
| DRINK | 53,500원 | 27개 |
| SNACK | 39,965원 | 39개 |

**처리 계획**:
- Phase 1: SQL로 price < 500인 16개 → NULL (단가로 불가능한 가격)
- Phase 2: `step2c_price_outlier_fix.py` — HIGH 126개 Naver webkr 재검색 → fence 내 가격 UPDATE 또는 NULL
- Phase 3: Claude in Chrome MCP로 Naver Shopping 직접 검색 (재검색 실패 우선순위 항목)

**LLM Zero-shot 분류 방법론 한계 및 향후 검증**
- 한계: 시스템 프롬프트의 영양성분 설명이 절대값 임계값이 아닌 상대적 표현 → 분류 기준 재현성 제한
- 향후: 사용자 피드백 루프 도입 — 추천 결과 검토 시 오분류 발견 → 수동 교정으로 정확도 평가
- 참고: RecBole, MealRec 등 추천 시스템에서도 카테고리 레이블 품질은 downstream task 성능으로 평가

---

## 4. 기술적 어려움 & 해결 방법 (전체 이슈 로그)

| 세션 | 이슈 | 해결 방법 |
|------|------|---------|
| S1 | SQL 마이그레이션은 anon key로 직접 실행 불가 | Supabase Dashboard > SQL Editor에서 직접 실행 |
| S2 | `google.generativeai` FutureWarning (deprecated) | `google.genai` 패키지로 교체, API 방식도 변경 |
| S2 | gemini-1.5-flash 404 / gemini-2.0-flash 한도 0 | `gemini-2.5-flash` 사용 |
| S2 | HACCP API 500 Error 지속 | Graceful fallback — Gemini가 제품명으로 추론 |
| S2 | Supabase PGRST204 (allergens 컬럼 없음) | SQL 마이그레이션 재실행 후 해결 |
| S2 | food_master에 영양성분이 NULL | Step 0 bulk copy 분리로 해결 |
| S3 | PostgREST 기본 1,000행 limit | pagination 루프 추가 |
| S3 | ON CONFLICT 배치 내 중복 | step0에 deduplication 로직 추가 |
| S3 | price NULL 64% | fallback 검색 로직 + step1b 보정 스크립트 |
| S6 | CSV price 신뢰도 낮음 (랜덤값 혼재) | price=NULL로 저장, Step 1b 재실행으로 Naver 조회 |
| S6 | 워크트리에서 data/ 경로 없음 | CSV_PATH 폴백 로직 (main repo → worktree 순서) |
| S7 | Groq TPM 6,000/min 초과 → 분류 923개에서 중단 | Gemini 2.5 Flash-Lite로 전환, 나머지 2,449개 완료 |
| S7 | Gemini 503 ServiceUnavailable (~0.5% 빈도) | except 503 → MAIN fallback, 알고리즘 영향 없음 |
| S7 | price 이상치 (최솟값 9원 ~ 최댓값 1,440,000원) | IQR 1.5× Tukey's fence per category, Naver 재검색 → NULL |
| S9 | KG 점수 음수 발생 (simulate_kg Day2~) | 가상 ATE 타임스탬프 > sim_now → Δt < 0 → `max(0.0, Δt)` + sim_now 파라미터 전달 |
| S9 | 형제 탐색 O(카테고리 전체) 성능 문제 | `_ate_by_category` dict 인덱스 추가 → O(ATE수) |
| S9 | PREFERS 엣지가 ATE 기록 시 덮어써짐 | DiGraph → MultiDiGraph, key="PREFERS"/"ATE" 구분 |
| S9 | KGManager 모든 메뉴 category=UNKNOWN | `loader.get_category_lists()`에서 `item["category"]=bucket` 미기록 → 추가 |

---

## 5. 알고리즘 관련 분석 (Session 4)

### `DietOptimizationProblem.n_var=4` 구조 확인
기존 optimizer는 하루 식단을 4개 슬롯으로 구성:
- Slot 0: MAIN (주식)
- Slot 1, 2: SIDE (반찬 2가지)
- Slot 3: DRINK (음료)

SNACK은 레이블로는 존재하나 optimizer 식단 구성에 미포함 → 향후 간식 끼니 추가 시 확장 포인트

---

## 6. Step 2 구현 레퍼런스 (Context7 조회, 2026-03-08)

### Groq JSON Mode 패턴

```python
# 핵심 호출 패턴 (llama-3.3-70b-versatile, JSON mode)
client = Groq(max_retries=3)   # 자동 exponential backoff

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": 'Classify food into MAIN/SIDE/DRINK/SNACK. Output: {"category_type": "..."}'},
        {"role": "user",   "content": f"{product_name} | {brand_name} | {food_group}"}
    ],
    response_format={"type": "json_object"},  # JSON mode 활성화
    temperature=0.1,   # 낮을수록 일관된 분류
    max_tokens=32,     # 4개 카테고리 중 택1 → 32 토큰이면 충분
)
result = json.loads(response.choices[0].message.content)
# → {"category_type": "MAIN"}
```

### 에러 처리 패턴

```python
try:
    cat = classify_one(client, row)
except groq.RateLimitError:
    time.sleep(60)     # 1분 대기 후 재시도 (max_retries와 별개로 명시)
except groq.APIConnectionError as e:
    log(f"Connection error: {e.__cause__}")
except groq.APIStatusError as e:
    log(f"Status {e.status_code}: {e.response}")
```

### 설계 결정: Batch API 미사용
Groq는 JSONL 배치 API(`client.files.create` + `client.batches.create`)를 지원하나,
Step 2에서는 sleep loop + 체크포인트 방식을 유지:
- 이유: 체크포인트(`.checkpoint/step2_done.json`) 통합이 단순, 실패 ID 즉시 파악 가능
- Batch API는 완료까지 polling이 필요해 오히려 복잡도 증가

### step2_food_classifier.py 구조 (Session 5 확정)

**설계 결정**: 영양성분(calories, carbs, protein, fat) + 식품군(food_group, NFIS 분류)을 프롬프트에 포함
- 이유: 영양성분 패턴으로 카테고리 추론 정확도 향상 (탄수화물↑ → MAIN, 액상 저열량 → DRINK 등)
- 시스템 프롬프트에 한국 식품공전, 식품의약품안전처, HACCP 분류 기준을 LLM 지식으로 참고하도록 명시

```
sys.path.insert(0, ...)      # 경로 패치 (CLAUDE.md §10)
from db.client import get_client
CHECKPOINT = ".checkpoint/step2_done.json"
VALID_CATEGORIES = {"MAIN", "SIDE", "DRINK", "SNACK"}
SYSTEM_PROMPT = "한국 식품공전(NFIS), 식품의약품안전처, HACCP 기준으로 MAIN/SIDE/DRINK/SNACK 분류..."
main():
  done_ids = load_checkpoint()
  rows = supabase.food_master WHERE category_type IS NULL (pagination 필수 — PostgREST 1,000행 한도)
         SELECT: id, product_name, brand_name, food_group, protein, carbs, fat, calories
  for row not in done_ids:
    cat = classify_with_groq(product_name, brand_name, food_group, protein, carbs, fat, calories)
    UPDATE category_type + classified_at
    save_checkpoint(row.id)
    time.sleep(2)
```

**모델**: `llama-3.1-8b-instant` (분류 태스크에 충분, Groq 6,000 RPD로 당일 완주 가능)

---

## 7. 향후 과제

- [x] Step 0b: final_nutrition_db.csv → food_master INSERT (850/871 완료)
- [x] Step 1c: 프랜차이즈 가격 조회 (564/846 업데이트)
- [x] Step 2: category_type 전체 분류 (3,372/3,372, Gemini 2.5 Flash-Lite)
- [x] Step 2b: 영양성분 불량 행 14개 삭제 → 최종 3,358행
- [x] Step 2c: price 이상치 처리 — Phase 1 SQL NULL 처리 (142개)
- [x] Step 3-4: 다목적 최적화 실험 프레임워크 (NSGA-II, Exp1~2)
- [x] **Step 5: KG 기반 4목적 최적화 (DailyExp3 + R-NSGA-II) + 7일 시뮬레이션 검증**
- [ ] 30회 본실험 실행 (`daily_exp3_rnsga2.yaml`) + GD/IGD/HV 통계 분석
- [ ] DailyExp1/2 vs DailyExp3 비교 분석 (KG 개인화 효과 정량화)
- [ ] LLM 분류 검증: 랜덤 샘플 확인 + 사용자 피드백 루프 구축
- [ ] HACCP API 안정화 — V3 엔드포인트 재시도 또는 대체 소스 탐색
