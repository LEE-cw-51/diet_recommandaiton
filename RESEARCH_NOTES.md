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
- [ ] Step 0b 잔여 21개 재시도: `step0b_csv_import.py --resume`
- [ ] Step 1b 재실행: 신규 행(프랜차이즈 메뉴) price Naver 조회
- [ ] Step 2: category_type 전체 분류 (Groq LLaMA) — 대상: 2,522+850행
- [ ] Step 3: `DailyDietOptimizer.from_supabase()` 구현, 알레르기 22종 확장
- [ ] price NULL 처리 — 프랜차이즈 메뉴는 Naver 조회율 낮을 가능성 있음
- [ ] HACCP API 안정화 — V3 엔드포인트 재시도 또는 대체 소스 탐색
