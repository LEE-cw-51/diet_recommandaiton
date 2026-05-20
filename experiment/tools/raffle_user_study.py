"""유저 스터디 경품 추첨 스크립트.

조건:
  - phone_number 입력 O
  - response_time_seconds >= min_time (기본 30초)

사용법:
  python -X utf8 -m experiment.tools.raffle_user_study
  python -X utf8 -m experiment.tools.raffle_user_study --n_winners 5 --min_time 30
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "experiment" / "results" / "user_study"


def _load_responses() -> list[dict]:
    from db.client import get_client
    sb = get_client()
    result = sb.table("user_study_responses").select("*").execute()
    return result.data or []


def main() -> None:
    parser = argparse.ArgumentParser(description="유저 스터디 경품 추첨")
    parser.add_argument("--n_winners", type=int, default=5,
                        help="추첨 인원 (default: 5)")
    parser.add_argument("--min_time",  type=int, default=30,
                        help="최소 응답 시간(초), 미만이면 제외 (default: 30)")
    parser.add_argument("--seed",      type=int, default=None,
                        help="추첨 재현용 시드 (default: None)")
    parser.add_argument("--out_csv",   type=str,
                        default=str(_DATA_DIR / "raffle_winners.csv"))
    args = parser.parse_args()

    print("Supabase에서 응답 로딩 중...")
    rows = _load_responses()
    print(f"  전체 응답: {len(rows)}건")

    # 필터링: 전화번호 있음 + 응답 시간 충족
    eligible = [
        r for r in rows
        if r.get("phone_number")
        and (r.get("response_time_seconds") or 0) >= args.min_time
    ]
    print(f"  유효 응답 (전화번호 O + {args.min_time}초 이상): {len(eligible)}명")

    if len(eligible) == 0:
        print("추첨 대상이 없습니다.")
        return

    if len(eligible) < args.n_winners:
        print(f"⚠️  유효 응답({len(eligible)}명)이 추첨 인원({args.n_winners}명)보다 적습니다.")
        print("   전원 당첨으로 처리합니다.")
        winners = eligible
    else:
        if args.seed is not None:
            random.seed(args.seed)
        winners = random.sample(eligible, args.n_winners)

    print(f"\n[추첨 결과] 당첨자 {len(winners)}명")
    print("-" * 40)
    for i, w in enumerate(winners, 1):
        print(f"  {i}. {w['phone_number']}  ({w.get('cuisine', '')} / {w.get('set_id', '')})")

    # CSV 저장
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["rank", "phone_number", "cuisine", "set_id", "created_at"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for i, w in enumerate(winners, 1):
            writer.writerow({"rank": i, **w})

    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
