"""유저 스터디 응답 분석.

Supabase user_study_responses 테이블에서 응답을 불러오고,
meta.json을 참조해 A/B 라벨을 G2/G3로 blind decode한다.
식문화별로 각 기준의 G3 승률(%) 및 G3 선택률을 출력한다.

사용법:
  python -X utf8 -m experiment.tools.analyze_user_study
  python -X utf8 -m experiment.tools.analyze_user_study --cuisine 한식
  python -X utf8 -m experiment.tools.analyze_user_study --out_csv experiment/results/user_study/analysis_result.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from experiment import _PROJECT_ROOT

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "experiment" / "results" / "user_study"
CUISINES  = ["한식", "중식", "일식", "양식"]

# 비교 기준 컬럼 (Supabase: diversity_winner / nutrition_winner)
WINNER_COLS = ["diversity", "nutrition"]
WINNER_LABELS = {
    "diversity": "다양성",
    "nutrition": "영양균형",
}


# ── meta 캐시 ────────────────────────────────────────────────────────────────────

def _load_meta(cuisine: str, set_id: str) -> dict | None:
    path = _DATA_DIR / cuisine / f"{set_id}_meta.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Supabase 응답 로드 ────────────────────────────────────────────────────────────

def _load_responses(cuisine_filter: str | None = None) -> list[dict]:
    from db.client import get_client
    sb = get_client()

    query = sb.table("user_study_responses").select("*")
    if cuisine_filter:
        query = query.eq("cuisine", cuisine_filter)

    result = query.execute()
    return result.data or []


# ── decode: A/B → G2/G3 ──────────────────────────────────────────────────────────

def _decode_response(row: dict) -> dict | None:
    """응답 1개를 G2/G3 기준 승자 정보로 변환. meta 없으면 None."""
    meta = _load_meta(row["cuisine"], row["set_id"])
    if meta is None:
        return None

    a_is = meta["A_is"]  # "G2" or "G3"

    def _winner_algo(col: str) -> str | None:
        """diversity_winner / nutrition_winner (A or B) → G2/G3"""
        ab = row.get(f"{col}_winner")
        if not ab:
            return None
        if a_is == "G2":
            return "G2" if ab == "A" else "G3"
        else:
            return "G3" if ab == "A" else "G2"

    # chosen_overall → G2/G3
    chosen = row.get("chosen_overall", "A")
    if a_is == "G2":
        chosen_algo = "G2" if chosen == "A" else "G3"
    else:
        chosen_algo = "G3" if chosen == "A" else "G2"

    decoded: dict = {
        "cuisine":     row["cuisine"],
        "set_id":      row["set_id"],
        "chosen_algo": chosen_algo,
    }
    for col in WINNER_COLS:
        decoded[f"{col}_winner_algo"] = _winner_algo(col)

    return decoded


# ── 집계 ─────────────────────────────────────────────────────────────────────────

def _aggregate(decoded_rows: list[dict]) -> dict[str, dict]:
    """식문화별로 집계. {cuisine: {metric: value}}."""
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in decoded_rows:
        buckets[r["cuisine"]].append(r)

    result = {}
    for cuisine, rows in buckets.items():
        n = len(rows)
        entry: dict = {"n": n}

        for col in WINNER_COLS:
            valid = [r for r in rows if r.get(f"{col}_winner_algo") is not None]
            g3_wins = sum(1 for r in valid if r[f"{col}_winner_algo"] == "G3")
            entry[f"{col}_g3_win_rate"] = round(g3_wins / len(valid), 3) if valid else None

        g3_chosen = sum(1 for r in rows if r["chosen_algo"] == "G3")
        entry["g3_choice_rate"] = round(g3_chosen / n, 3) if n else None

        result[cuisine] = entry

    return result


# ── 출력 / 저장 ──────────────────────────────────────────────────────────────────

def _print_results(agg: dict[str, dict]) -> None:
    for cuisine, entry in agg.items():
        n = entry["n"]
        g3_rate = entry.get("g3_choice_rate")
        print(f"\n[{cuisine}] 총 응답: {n}명  |  G3(개인화) 선택률: {g3_rate:.1%}" if g3_rate is not None else f"\n[{cuisine}] 총 응답: {n}명")
        print(f"  {'기준':<14}  {'G3 승률':>10}  {'G2 승률':>10}")
        print("  " + "-" * 38)
        for col in WINNER_COLS:
            g3_wr = entry.get(f"{col}_g3_win_rate")
            if g3_wr is not None:
                g2_wr = 1.0 - g3_wr
                print(f"  {WINNER_LABELS[col]:<14}  {g3_wr:>9.1%}  {g2_wr:>9.1%}")
            else:
                print(f"  {WINNER_LABELS[col]:<14}  {'N/A':>10}  {'N/A':>10}")


def _save_csv(out_path: Path, agg: dict[str, dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["cuisine", "n", "g3_choice_rate"]
    for col in WINNER_COLS:
        fieldnames.append(f"{col}_g3_win_rate")

    rows = []
    for cuisine, entry in agg.items():
        row = {"cuisine": cuisine}
        row.update(entry)
        rows.append(row)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n결과 저장: {out_path}")


# ── main ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="유저 스터디 응답 분석")
    parser.add_argument("--cuisine", type=str, default=None,
                        help="특정 식문화만 분석 (default: 전체)")
    parser.add_argument("--out_csv", type=str,
                        default=str(_DATA_DIR / "analysis_result.csv"))
    args = parser.parse_args()

    print("Supabase에서 응답 로딩 중...")
    raw_rows = _load_responses(cuisine_filter=args.cuisine)
    print(f"  총 {len(raw_rows)}건 로드")

    if not raw_rows:
        print("응답 없음. 유저 스터디를 먼저 진행해주세요.")
        return

    decoded = [r for row in raw_rows if (r := _decode_response(row)) is not None]
    skipped = len(raw_rows) - len(decoded)
    if skipped:
        print(f"  meta.json 없어 건너뜀: {skipped}건")

    agg = _aggregate(decoded)
    _print_results(agg)
    _save_csv(Path(args.out_csv), agg)


if __name__ == "__main__":
    main()
