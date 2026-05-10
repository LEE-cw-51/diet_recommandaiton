# 프로젝트 규칙 — Diet Recommendation Pipeline

## 1. Git 규칙
**워크트리에서 `git commit / push / merge` 금지.** 파일 수정만 하고, 커밋은 메인 레포에서 사용자가 직접 수행.

## 2. 코드 실행 순서
`--test 5` 먼저 → 성공 확인 → 사용자 확인 후 `--resume` 전체 실행.

## 3. 체크포인트
`.checkpoint/` 파일 삭제 금지. 재개 시 항상 `--resume`. 처음부터 재실행은 사용자 확인 필수.

## 4. API 키
`.env`에만 저장. 코드 하드코딩 금지. `os.environ["KEY_NAME"]` 사용.

## 5. Supabase 스키마 변경
DDL은 Python 코드에서 직접 실행 금지 → Supabase Dashboard > SQL Editor에서 실행 후 `python qa/verify_schema.py` 검증.

## 6. 세션 루틴
- **시작**: `PIPELINE_PROGRESS.md` 읽어 현재 상태 파악
- **종료**: `PIPELINE_PROGRESS.md` 업데이트 (완료 체크, 처리량, 다음 작업, 이슈 로그)

## 7. 캐시 우선
`data/raw/search_cache/{id}.json` 존재 시 API 재호출 금지. 캐시 파일 삭제 금지.

## 8. 에러 처리
개별 항목 실패 시 중단 없이 로그 출력 후 계속. 실패 ID는 체크포인트 미저장 → `--resume` 시 자동 재시도. Rate Limit 시 sleep 후 재시도.

## 9. 주요 API

| API | 엔드포인트 | 키 | 한도 |
|-----|-----------|-----|------|
| Naver Shopping | `openapi.naver.com/v1/search/shop.json` | NAVER_CLIENT_ID/SECRET | 25,000/일 |
| HACCP | `apis.data.go.kr/B553748/CertImgListServiceV3` | HACCP_API_KEY | 무제한 |
| Gemini | `google.genai` SDK | GOOGLE_API_KEY | 1,500 RPD |
| Groq LLaMA | `groq` SDK | GROQ_API_KEY | 6,000 RPD |
| Supabase | `supabase` SDK | SUPABASE_URL/KEY | — |

## 10. 패키지 / 경로 주의
- `google-genai>=1.0.0` 사용 (`google-generativeai` deprecated)
- `supabase/` 디렉토리가 pip `supabase` 패키지와 충돌 → Supabase 클라이언트는 `from db.client import get_client`
- `pipeline/05_augment/` 스크립트는 `sys.path.insert(0, str(Path(__file__).parent))` 필요
