# 연구 파이프라인 진행 상황

## 현재 상태
- 현재 세션: Session 3 진행 중 (Step 1 31% 완료, 내일 재개 예정)
- 플랜 파일: `C:\Users\chanw\.claude\plans\cheeky-hopping-llama.md`
- 마지막 업데이트: 2026-03-07 (Step 1 중단, price NULL 원인 분석, fallback 계획 수립)
- **다음 작업**: 코드 수정 (search_clients.py fallback + step1 food_group) → --test 5 검증 → --resume 재개

## 프로젝트 경로
- 워킹 디렉토리: `C:\Users\chanw\Desktop\diet_recommendation\.claude\worktrees\distracted-boyd`

## Supabase 연결 정보
- URL: `https://ealcjovjcnbmxflpofzp.supabase.co`
- 테이블: `food_master` (증강 대상, 현재 5행), `food_research_sample` (원본 2,524행)
- anon key: `.env` 파일의 `SUPABASE_KEY` 참조

## 테이블 컬럼 현황 (Session 2에서 확인)

### food_research_sample (원본, 수정 불가)
| 컬럼 | 설명 |
|------|------|
| id, product_name, brand_name | 식별자 |
| calories, protein, fat, carbs, sugar, sodium | 영양성분 |
| cholesterol, saturated_fat, trans_fat | 추가 영양성분 |
| food_code, main_category, standard_product_name | 분류 |
| ref_serving_size, serving_standard, total_weight | 용량 |
| **⚠️ price 컬럼 없음** | 가격은 네이버 API에서 수집 |

### food_master (증강 대상)
| 컬럼 | 설명 |
|------|------|
| id, product_name, brand_name | 식별자 |
| food_group, calories, protein, fat, carbs, sugar, sodium | 영양성분 |
| **price** | 네이버 쇼핑 API로 수집 (Step 1) |
| category_type | Groq LLaMA 분류 (Step 2) |
| data_source, is_verified, created_at | 메타데이터 |
| **allergens** (JSONB) | 22종 알레르기 (Step 1에서 추가) |
| **raw_label_text** | HACCP 원재료명 원문 (Step 1에서 추가) |
| **augmented_at** | Step 1 완료 시각 |
| **classified_at** | Step 2 완료 시각 |

## API 키 현황 (.env 기준)
- [x] GOOGLE_API_KEY (Gemini 2.5 Flash — Step 1 파싱) ✅
- [x] GROQ_API_KEY (LLaMA 3.1 8B — Step 2 분류) ✅
- [x] NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (쇼핑 가격 검색) ✅
- [x] HACCP_API_KEY (식품안전정보원 포장지표기정보 — data.go.kr 발급) ✅
- [x] SUPABASE_URL / SUPABASE_KEY ✅

## 수정된 파이프라인 아키텍처 (Session 2에서 발견)

```
food_research_sample (2,524행)
  │
  [Step 0] 영양성분 BULK COPY ← Session 3에서 구현 필요
  │  INSERT INTO food_master (product_name, brand_name, calories, ...)
  │  SELECT ... FROM food_research_sample
  │  ON CONFLICT (product_name, brand_name) DO NOTHING
  ↓
food_master (영양성분 채워진 2,524행)
  │
  [Step 1] 네이버 가격 + HACCP 알레르기 UPDATE ← step1_price_allergen.py 수정 필요
  │  UPDATE food_master SET price=?, allergens=?, augmented_at=now()
  │  (기존 UPSERT → UPDATE로 변경, 영양성분 덮어쓰기 방지)
  ↓
  [캐시] data/raw/search_cache/{id}.json (재현성 보장)
  ↓
  Gemini 2.5 Flash → allergens 22종 JSONB + price 추출
  ↓
food_master (영양성분 + 가격 + 알레르기 채워진 상태)
  │
  [Step 2] Groq LLaMA 3.1 8B → category_type (MAIN/SIDE/DRINK/SNACK)
  ↓
algorithm/daily_diet_optimizer.py → from_supabase()
```

## 22종 알레르기 (식약처 기준)
난류, 우유, 메밀, 땅콩, 대두, 밀, 고등어, 게, 새우, 돼지고기, 복숭아, 토마토, 아황산류, 호두, 닭고기, 쇠고기, 오징어, 조개류, 잣, 아몬드, 캐슈넛, 키위

---

## 세션별 완료 현황

### Session 1: 인프라 세팅 (30분)
- [x] 완료
- 완료 일시: 2026-03-04
- 작업 내용:
  - [x] `PIPELINE_PROGRESS.md` 생성
  - [x] `supabase/migrations/001_add_allergens.sql` 생성
  - [x] `.env.example` 생성
  - [x] `db/__init__.py` + `db/client.py` 생성 (주의: supabase/ 폴더 이름이 pip 패키지와 충돌하여 db/로 변경)
  - [x] `requirements.txt` 업데이트 (supabase>=2.0.0, google-generativeai>=0.8.0, groq>=0.9.0, tqdm>=4.0.0 추가)
- 완료 기준: `python -c "from db.client import get_client; print(get_client())"` → .env 설정 후 에러 없이 실행
- **중요 변경사항**: 클라이언트는 `supabase/client.py` → `db/client.py`로 변경됨
  - 이유: 로컬 `supabase/` 디렉토리가 pip `supabase` 패키지를 shadowing하는 문제 방지
  - 이후 모든 파일에서 `from db.client import get_client` 사용
- 메모:
  - SQL 마이그레이션(`supabase/migrations/001_add_allergens.sql`)은 Supabase Dashboard > SQL Editor에서 직접 실행 필요
  - `.env.example` → `.env` 복사 후 API 키 입력 필요
  - HACCP API 키는 data.go.kr에서 발급 (즉시 발급, 무료)
  - 네이버 API는 developers.naver.com에서 앱 등록 후 발급

### Session 2: 검색 클라이언트 + 5개 테스트 (1시간)
- [x] 완료
- 완료 일시: 2026-03-04
- 작업 내용:
  - [x] `pipeline/05_augment/__init__.py` 생성
  - [x] `pipeline/05_augment/search_clients.py` 구현 (Naver + HACCP + 캐시)
  - [x] `pipeline/05_augment/step1_price_allergen.py` 구현 (Gemini 파싱 + Supabase UPSERT + 체크포인트)
  - [x] `--test 5` 실행 성공: 5/5 처리, 0 실패
  - [x] `verify_schema.py` 실행: food_master 19개 컬럼 확인
- 완료 기준:
  - [x] `data/raw/search_cache/` 에 5개 JSON 파일 생성
  - [x] Supabase `food_master`에 5행 UPSERT (augmented_at 채워짐)
  - [x] `.checkpoint/step1_done.json` 에 5개 ID 기록
- **⚠️ 아키텍처 수정 사항 발견 (Session 3 시작 전 처리 필요)**:
  - 현재 Step 1 UPSERT는 price/allergens만 전송 → 새 행 INSERT 시 영양성분 컬럼 전부 NULL
  - **수정 방향**: Step 0(bulk copy)으로 영양성분 먼저 복사 → Step 1은 UPDATE로만 동작
- **⚠️ HACCP API 엔드포인트 수정 필요**:
  - 현재 코드: `https://apis.data.go.kr/B553748/CertImgListService/getCertImgList`
  - 정확한 URL: `https://apis.data.go.kr/B553748/CertImgListServiceV3` (V3 버전)
  - `pipeline/05_augment/search_clients.py` line 67 수정 필요
- 메모:
  - **Gemini SDK 변경**: `google.generativeai` (deprecated) → `google.genai` 패키지 사용
  - **사용 모델**: `gemini-2.5-flash` (gemini-1.5-flash는 v1beta에서 404, gemini-2.0-flash는 한도 0)
  - **HACCP API**: 500 Server Error 지속 발생 (서버 측 문제) → Gemini가 제품명만으로 추론 (fallback)
  - **네이버 API**: 정상 동작 확인 (비비고 왕교자 등 일반 제품). 테스트 5개가 특수 제품이라 결과 없음
  - **price/allergens 빈값**: 테스트 5개가 HACCP 미등록 + 네이버 미조회 특수 제품이라 발생
  - **requirements.txt**: `google-generativeai` → `google-genai>=1.0.0` 변경 필요
  - **체크포인트**: `.checkpoint/step1_done.json` — ID 5개 저장됨 (전체 실행 시 `--resume` 사용 가능)
  - **food_research_sample에 price 컬럼 없음**: 가격은 오직 네이버 API에서만 수집

### Session 3: Step 0 + Step 1 수정 + 전체 실행
- [ ] 완료 (진행 중 — Step 1이 789/2,522에서 중단, 내일 재개)
- 처리량: 789 / 2,522 (Step 0 완료 2,522행, Step 1 31%)
- 체크포인트 파일: `.checkpoint/step1_done.json` (789개 ID 저장됨)
- **워크트리**: `C:\Users\chanw\Desktop\diet_recommendation\.claude\worktrees\reverent-easley`
- **완료된 작업**:
  1. ✅ Step 0 전체 실행 (2,522행 복사, 원본 2,524에서 중복 2개 제거)
  2. ✅ Step 1 진행 중 (789/2,522 = 31%)
  3. ✅ gemini-2.5-flash-lite 모델 변경 + 유료 전환
  4. ✅ PostgREST 1,000행 limit 버그 수정 (pagination 추가)
- **다음 세션 시작 전 즉시 할 일 (코드 수정 먼저)**:
  1. `search_clients.py` — `_fallback_naver_search()` 추가 (product_name → standard_product_name 단계적 재시도)
  2. `step1_price_allergen.py` — food_group 로드 매핑 + fallback price 활용 + Gemini 프롬프트에 식품군(food_group) 추가
  3. `step1b_fix_null_prices.py` — 신규 생성 (Step 1 완료 후 기존 price=null 보정용)
  4. 수정 후 `--test 5 --table food_master_test` 검증
  5. 검증 성공 후 `python pipeline/05_augment/step1_price_allergen.py --resume`
  6. Step 1 완료 후 `python pipeline/05_augment/step1b_fix_null_prices.py`
- 완료 기준:
  - `food_master` 행수 ≈ 2,522
  - `augmented_at IS NOT NULL` 비율 ≥ 90%
  - `calories IS NOT NULL` 비율 = 100% (Step 0 완료)
  - `price IS NULL` 비율 ≤ 45% (fallback 적용 후 목표)
- 메모:
  - price NULL 64% 원인 분석 완료: 네이버 미등록 외국 브랜드·특수 제품 (코드 버그 아님)
  - food_master.food_group 값 확인: "과자류·빵류 또는 떡류" 형태로 의미있는 값 있음
  - 상세 계획: `C:\Users\chanw\.claude\plans\cheeky-hopping-llama.md` 참조

### Session 4: Step 2 식사 분류 (15분)
- [ ] 완료
- 분류 분포: MAIN:-, SIDE:-, DRINK:-, SNACK:-
- 완료 기준: `food_master.category_type` 전체 채워짐
- 메모:

### Session 5: 알고리즘 연동 (2시간)
- [ ] 완료
- 작업 내용:
  - [ ] `DailyDietOptimizer.from_supabase()` 메서드 추가
  - [ ] 알레르기 22종으로 확장 (기존 10종 → 22종)
  - [ ] 기존 CSV 방식 하위 호환 유지
- 완료 기준: `DailyDietOptimizer.from_supabase().recommend_daily_diet(...)` 정상 출력
- 메모:

---

## 다음 세션 시작 루틴
```
1. 이 파일(PIPELINE_PROGRESS.md) 읽기 → 현재 상태 파악
2. "Session 3 시작 전 즉시 할 일" 항목 순서대로 처리
3. 해당 세션 작업 수행
4. 세션 완료 후 이 파일 업데이트 (완료 체크박스, 메모, 처리량 등)
```

## 이슈 로그
| 세션 | 이슈 | 해결 방법 |
|------|------|---------|
| S1 | `food_master`에 allergens 컬럼 없음 | `001_add_allergens.sql` 마이그레이션으로 해결 |
| S1 | SQL 마이그레이션은 anon key로 직접 실행 불가 | Supabase Dashboard > SQL Editor에서 직접 실행 필요 |
| S2 | `google.generativeai` FutureWarning (deprecated) | `google.genai` 패키지로 교체, API 방식도 변경 |
| S2 | gemini-1.5-flash 404 / gemini-2.0-flash 한도 0 | `gemini-2.5-flash` 사용 (정상 동작) |
| S2 | `pipeline/05_augment/` 숫자 디렉토리 import 오류 | `sys.path.insert(0, str(Path(__file__).parent))`로 해결 |
| S2 | HACCP API 500 Error 지속 | Graceful fallback (빈 dict 반환, Gemini가 제품명으로 추론) |
| S2 | Supabase PGRST204 (allergens 컬럼 없음) | SQL 마이그레이션 재실행 후 해결 (verify_schema.py로 확인) |
| S2 | food_master에 영양성분이 NULL | Step 1 UPSERT에 영양성분 컬럼 누락 → Step 0 bulk copy 필요 |
| S2 | HACCP API 엔드포인트 버전 오류 | V3 URL로 수정: `CertImgListServiceV3` |
| S2 | food_research_sample에 price 컬럼 없음 | price는 네이버 API에서만 수집, food_master에 price 컬럼 있음 |
| S3 | PostgREST 기본 1,000행 limit → step0가 999행만 복사 | range() 기반 pagination 루프 추가 |
| S3 | ON CONFLICT 배치 내 중복 (product_name+brand_name) | step0에 deduplication 로직 추가, 2,522행 정상 저장 |
| S3 | price NULL 64% 발생 | 근본 원인: 네이버 미등록 외국/특수 제품. 수정: fallback 검색 로직 추가 예정 |
| S3 | allergens 추론 컨텍스트 부족 | food_master.food_group ("과자류·빵류 또는 떡류" 등) Gemini 프롬프트에 추가 예정 |

---

## 파일 구조 (완성 후)
```
diet_recommendation/
├── PIPELINE_PROGRESS.md          ← 이 파일
├── CLAUDE.md                     ← 프로젝트 규칙 (Session 2 완료 후 생성)
├── .env.example                  ← API 키 템플릿
├── .env                          ← 실제 API 키 (git 제외)
├── requirements.txt              ← supabase, google-genai, groq, tqdm 추가됨
├── verify_schema.py              ← Supabase food_master 스키마 검증 스크립트
├── data/raw/search_cache/        ← 검색 캐시 (재현성)
│   └── {food_research_sample.id}.json
├── .checkpoint/
│   └── step1_done.json           ← 처리 완료 ID 목록
├── db/                           ← Supabase 클라이언트 패키지 (supabase/ 아님 - pip 충돌 방지)
│   ├── __init__.py
│   └── client.py                 ← get_client() 싱글턴
├── supabase/
│   └── migrations/
│       └── 001_add_allergens.sql ← allergens 컬럼 추가 (SQL Editor에서 실행)
├── pipeline/05_augment/
│   ├── search_clients.py         ← 네이버 + HACCP 클라이언트
│   ├── step0_bulk_copy.py        ← [신규, Session 3] 영양성분 bulk copy
│   ├── step1_price_allergen.py   ← 검색 → Gemini 파싱 → UPDATE
│   └── step2_food_classifier.py  ← Groq + LLaMA 분류
└── algorithm/daily_diet_optimizer.py  ← [수정] Supabase 로더 + 22종
```
