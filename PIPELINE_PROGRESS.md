# 파이프라인 진행 상황

## 현재 상태
- **다음 작업**: Step 2c 실행 (Phase 1 SQL → Phase 2 스크립트 → Phase 3 브라우저)
- 마지막 업데이트: 2026-03-10 (Session 7, step2c 스크립트 작성 완료)

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
| Step 2c | price 이상치 처리 (IQR 1.5× + Naver 재검색) | ⏳ | LOW 16개 / HIGH 126개 탐지 |
| Step 3 | 알고리즘 연동 (from_supabase + 22종 알레르기) | ⏳ | — |

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
