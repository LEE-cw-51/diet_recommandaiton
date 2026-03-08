# 파이프라인 진행 상황

## 현재 상태
- **다음 작업**: Session 5 — `step2_food_classifier.py` 작성 → `--test 5` → `--resume`
- 마지막 업데이트: 2026-03-08

## 단계별 완료 현황
| 단계 | 내용 | 상태 | 수치 |
|------|------|------|------|
| Step 0 | food_research_sample → food_master bulk copy | ✅ | 2,522행 |
| Step 1 | 네이버 가격 + HACCP 알레르기 UPDATE | ✅ | 2,520/2,522 (99.9%) |
| Step 1b | price NULL 보정 (fallback 검색) | ✅ | 127개 보정, 최종 1,761개 유가격 (69.8%) |
| Step 2 | Groq LLaMA → category_type 분류 | ⏳ | 0/2,522 |
| Step 3 | 알고리즘 연동 (from_supabase + 22종 알레르기) | ⏳ | — |

## Step 2 구현 계획 (Session 5 확정)
- 스크립트: `pipeline/05_augment/step2_food_classifier.py`
- API: Groq LLaMA 3.1 8B (`GROQ_API_KEY`), `model="llama-3.1-8b-instant"`, `client = Groq(max_retries=3)`
- 소스: `food_master WHERE category_type IS NULL` (pagination 1,000행씩)
- 입력 (프롬프트): `product_name + brand_name + food_group + calories + carbs + protein + fat`
- 시스템 프롬프트: 한국 식품공전(NFIS), 식품의약품안전처, HACCP 분류 기준 명시
- 출력: `{"category_type": "MAIN|SIDE|DRINK|SNACK"}`
- UPDATE: `category_type`, `classified_at = now()`
- 체크포인트: `.checkpoint/step2_done.json`
- Rate limit: `groq.RateLimitError` catch + sleep(60) 재시도 → 약 84분 소요
- DDL 불필요: `category_type` + `classified_at` 컬럼 이미 존재 (`001_add_allergens.sql`)

## 아키텍처
```
food_research_sample (2,524행)
  ↓ [Step 0] bulk copy
food_master (2,522행, 영양성분 채워진 상태)
  ↓ [Step 1] 네이버 가격 + HACCP 알레르기 → Gemini 파싱
food_master (price 69.8% 채워짐, allergens JSON)
  ↓ [Step 2] Groq LLaMA 3.1 8B
food_master (category_type: MAIN/SIDE/DRINK/SNACK)
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
| category_type | MAIN/SIDE/DRINK/SNACK | Step 2 |
| augmented_at / classified_at | 처리 시각 | Step 1/2 |

## Supabase
- URL: `https://ealcjovjcnbmxflpofzp.supabase.co`
- 키: `.env` 파일의 `SUPABASE_KEY` 참조
