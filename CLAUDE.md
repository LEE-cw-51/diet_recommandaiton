# 프로젝트 규칙 — Diet Recommendation Pipeline

이 파일은 Claude Code가 이 프로젝트에서 작업할 때 따라야 할 규칙을 정의합니다.

---

## 1. Git 커밋 규칙

**워크트리에서 직접 git commit 금지.**

- 현재 작업 위치는 `.claude/worktrees/distracted-boyd/` (worktree)
- 워크트리에서는 파일 수정만 하고, 커밋은 메인 레포(`diet_recommendation/`)에서 수행
- `git commit`, `git push`, `git merge` 명령어는 워크트리에서 실행하지 않음
- 작업 완료 후 사용자에게 메인 레포에서 직접 커밋할 것을 안내

```bash
# ❌ 금지 (워크트리에서)
git commit -m "..."

# ✅ 허용 (메인 레포에서 사용자가 직접)
cd C:\Users\chanw\Desktop\diet_recommendation
git add ...
git commit -m "..."
```

---

## 2. 코드 실행 전 검증 규칙

**항상 소량 테스트 먼저, 전체 실행 나중.**

1. 새 스크립트 작성 후 반드시 `--test 5` (또는 소량) 먼저 실행
2. 테스트 성공 확인 후 전체 실행 (`python script.py --resume`)
3. 전체 실행은 사용자 확인 후 진행

```bash
# ✅ 올바른 순서
python pipeline/05_augment/step1_price_allergen.py --test 5   # 먼저 소량 테스트
# → 성공 확인 후
python pipeline/05_augment/step1_price_allergen.py --resume    # 전체 실행
```

---

## 3. 체크포인트 파일 규칙

**`.checkpoint/` 디렉토리의 파일을 절대 삭제하지 않음.**

- `.checkpoint/step1_done.json` — 처리 완료된 ID 목록
- 전체 실행 재시작 시 반드시 `--resume` 플래그 사용
- 처음부터 다시 실행이 필요한 경우 사용자에게 먼저 확인

```bash
# ✅ 중단 후 재개
python pipeline/05_augment/step1_price_allergen.py --resume

# ❌ 금지 — 체크포인트 무시하고 처음부터 (사용자 확인 없이)
python pipeline/05_augment/step1_price_allergen.py
```

---

## 4. API 키 및 환경 변수 규칙

- API 키는 `.env` 파일에만 저장 (git에 추가하지 않음)
- `.env.example`만 git 추적 (실제 키 없이 키 이름만 포함)
- 코드에 API 키 하드코딩 금지
- `.env` 파일이 없으면 사용자에게 `.env.example`을 복사해 입력하도록 안내

```python
# ✅ 올바른 방식
import os
api_key = os.environ["GOOGLE_API_KEY"]

# ❌ 금지
api_key = "AIzaSy..."
```

---

## 5. Supabase 스키마 변경 규칙

**스키마 변경은 반드시 Supabase Dashboard > SQL Editor에서 직접 실행.**

- Python 코드에서 `ALTER TABLE`, `CREATE TABLE` 등 DDL 직접 실행 금지
- 스키마 변경 SQL은 `supabase/migrations/` 디렉토리에 파일로 저장
- 변경 후 `verify_schema.py`로 반드시 검증

```bash
# 스키마 변경 후 검증
python verify_schema.py
```

---

## 6. 세션 시작/종료 루틴

**매 세션 시작 시:**
1. `PIPELINE_PROGRESS.md` 읽기 → 현재 상태 파악
2. 이슈 로그 확인 → 기존 문제 인지
3. 해당 세션 작업 수행

**매 세션 종료 시:**
1. `PIPELINE_PROGRESS.md` 업데이트
   - 완료 체크박스 업데이트
   - 메모 추가 (발견한 이슈, 해결 방법)
   - 처리량 업데이트
   - 다음 작업 항목 업데이트
2. 이슈 로그 추가 (새로 발견한 이슈)

---

## 7. 캐시 우선 정책

**`data/raw/search_cache/{id}.json`이 있으면 API 재호출 금지.**

- 캐시 파일 삭제 금지 (재현성 손상)
- 프롬프트 수정 후 재파싱이 필요하면 캐시를 활용해 API 비용 없이 재실행 가능
- 네이버/HACCP API 호출 결과는 항상 캐시에 저장

---

## 8. 에러 처리 규칙

- 개별 식품 처리 실패 시 스크립트를 중단하지 않고 로그만 출력 후 계속 진행
- 실패한 ID는 체크포인트에 저장하지 않아 `--resume` 시 재시도됨
- API Rate Limit 에러 발생 시 sleep 후 재시도

---

## 9. 주요 API 현황

| API | 엔드포인트 | 키 위치 | 제한 |
|-----|-----------|---------|------|
| Naver Shopping | `openapi.naver.com/v1/search/shop.json` | NAVER_CLIENT_ID/SECRET | 1,000/일 |
| HACCP | `apis.data.go.kr/B553748/CertImgListServiceV3` | HACCP_API_KEY | 무제한 |
| Gemini | `google.genai` SDK | GOOGLE_API_KEY | 1,500 RPD |
| Groq LLaMA | `groq` SDK | GROQ_API_KEY | 6,000 RPD |
| Supabase | `supabase` SDK | SUPABASE_URL/KEY | - |

---

## 10. requirements.txt 패키지 주의사항

```
# ✅ 사용하는 패키지 (현재 기준)
google-genai>=1.0.0        # google.generativeai (deprecated) 대신 사용
groq>=0.9.0
supabase>=2.0.0
tqdm>=4.0.0

# ❌ 사용하지 않음 (deprecated)
# google-generativeai      # google.genai로 대체됨
```

---

## 11. 로컬 패키지 경로 주의사항

- `supabase/` 디렉토리 이름이 pip `supabase` 패키지와 충돌
- Supabase 클라이언트는 `db/client.py`에서 관리 (`from db.client import get_client`)
- `pipeline/05_augment/` 내부 스크립트는 `sys.path.insert(0, ...)` 필요
