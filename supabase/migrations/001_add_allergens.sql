-- ============================================================
-- Migration 001: food_master 테이블에 알레르기/증강 컬럼 추가
-- 실행 방법: Supabase Dashboard > SQL Editor 에서 직접 실행
-- ============================================================

-- 1. 알레르기 및 증강 관련 컬럼 추가
ALTER TABLE food_master
  ADD COLUMN IF NOT EXISTS allergens       JSONB        DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS raw_label_text  TEXT,           -- HACCP 원재료명 원문 저장 (연구 투명성)
  ADD COLUMN IF NOT EXISTS augmented_at    TIMESTAMPTZ,    -- Step 1 완료 시각
  ADD COLUMN IF NOT EXISTS classified_at   TIMESTAMPTZ;    -- Step 2 완료 시각

-- 2. UPSERT용 복합 유니크 키 추가 (product_name + brand_name)
ALTER TABLE food_master
  ADD CONSTRAINT IF NOT EXISTS uq_food_master_product_brand
  UNIQUE (product_name, brand_name);

-- 3. 검색 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_food_master_augmented_at
  ON food_master (augmented_at);

CREATE INDEX IF NOT EXISTS idx_food_master_category_type
  ON food_master (category_type);

CREATE INDEX IF NOT EXISTS idx_food_master_price
  ON food_master (price)
  WHERE price IS NOT NULL;

-- ============================================================
-- 알레르기 JSONB 구조 (식약처 기준 22종)
-- 예시:
-- {
--   "난류": false, "우유": false, "메밀": false, "땅콩": false,
--   "대두": false, "밀": false,  "고등어": false, "게": false,
--   "새우": false, "돼지고기": false, "복숭아": false, "토마토": false,
--   "아황산류": false, "호두": false, "닭고기": false, "쇠고기": false,
--   "오징어": false, "조개류": false, "잣": false, "아몬드": false,
--   "캐슈넛": false, "키위": false
-- }
-- ============================================================

-- 검증 쿼리 (실행 후 확인용)
SELECT
  column_name,
  data_type,
  column_default
FROM information_schema.columns
WHERE table_name = 'food_master'
  AND column_name IN ('allergens', 'raw_label_text', 'augmented_at', 'classified_at')
ORDER BY column_name;
