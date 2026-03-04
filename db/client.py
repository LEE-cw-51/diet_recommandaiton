"""
Supabase 클라이언트 싱글턴

주의: 로컬 패키지 이름을 'supabase'로 하면 pip supabase 패키지와 충돌하므로
      'db' 패키지로 분리하였음.

사용법:
    from db.client import get_client
    sb = get_client()
    rows = sb.table("food_master").select("*").execute().data
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from supabase import create_client, Client   # pip: supabase>=2.0.0

# .env 파일 로드 (이미 로드됐어도 무해)
load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Supabase 클라이언트 싱글턴 반환.

    환경 변수:
        SUPABASE_URL  : Supabase 프로젝트 URL
        SUPABASE_KEY  : anon 키 (또는 service_role 키)

    Returns:
        supabase.Client 인스턴스

    Raises:
        EnvironmentError: 환경 변수 미설정 시
    """
    global _client

    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url:
            raise EnvironmentError(
                "SUPABASE_URL 환경 변수가 설정되지 않았습니다. "
                ".env 파일을 확인하세요."
            )
        if not key:
            raise EnvironmentError(
                "SUPABASE_KEY 환경 변수가 설정되지 않았습니다. "
                ".env 파일을 확인하세요."
            )

        _client = create_client(url, key)

    return _client


if __name__ == "__main__":
    # 연결 테스트: python -m db.client
    sb = get_client()
    result = sb.table("food_master").select("id").limit(1).execute()
    print("Supabase connection: OK")
    print(f"  food_master sample: {result.data}")

    result2 = sb.table("food_research_sample").select("id", count="exact").execute()
    print(f"  food_research_sample row count: {result2.count}")
