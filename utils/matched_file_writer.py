from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

Record = Mapping[str, object]
MatchFn = Callable[[Record], bool]


def collect_matched_records(records: Iterable[Record], matcher: MatchFn) -> list[Record]:
    """Return only those records that satisfy the matcher predicate."""
    return [record for record in records if matcher(record)]


def write_matched_view(
    records: Iterable[Record],
    matcher: MatchFn,
    output_path: str | Path,
    *,
    file_format: str = "csv",
) -> Sequence[Record]:
    """Persist matched records so the output file exposes only the matches."""
    matched = collect_matched_records(records, matcher)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if file_format == "csv":
        if not matched:
            path.write_text("", encoding="utf-8")
            return matched
        fieldnames = list(matched[0].keys())
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matched)
    elif file_format == "json":
        path.write_text(
            json.dumps(matched, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        raise ValueError(f"Unsupported file_format '{file_format}'. Use 'csv' or 'json'.")

    return matched
