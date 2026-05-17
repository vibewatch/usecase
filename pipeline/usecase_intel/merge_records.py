"""Merge per-vendor extracted records into a single JSON array for seeding.

The agent-driven extraction workflow writes one normalized JSON record per page
under `data/records/{vendor_slug}/{slug}.json`. `seed.py` expects a single JSON
array. This module walks the records tree, optionally folds in a samples file,
deduplicates by `id`, and writes the combined array to a target path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .settings import MERGED_CASE_STUDIES_PATH, RECORDS_ROOT


def _load_record(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object, got {type(data).__name__}")
    return data


def _load_array(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array, got {type(data).__name__}")
    return [item for item in data if isinstance(item, dict)]


def merge_records(
    *,
    records_root: Path,
    output_path: Path,
    include_samples: Path | None = None,
) -> dict[str, int]:
    records_by_id: dict[str, dict[str, Any]] = {}
    sample_count = 0
    record_count = 0

    if include_samples and include_samples.exists():
        for sample in _load_array(include_samples):
            rid = sample.get("id")
            if not rid:
                continue
            records_by_id[rid] = sample
            sample_count += 1

    if records_root.exists():
        for path in sorted(records_root.rglob("*.json")):
            try:
                record = _load_record(path)
            except (json.JSONDecodeError, ValueError) as exc:
                print(f"  skip {path}: {exc}", file=sys.stderr)
                continue
            rid = record.get("id")
            if not rid:
                print(f"  skip {path}: record missing 'id'", file=sys.stderr)
                continue
            # Real extractions override sample placeholders with the same id.
            records_by_id[rid] = record
            record_count += 1

    merged = list(records_by_id.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "samples": sample_count,
        "extracted": record_count,
        "total": len(merged),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge extracted records into a single JSON array.")
    parser.add_argument(
        "--records-root",
        type=Path,
        default=RECORDS_ROOT,
        help="Directory containing per-vendor record JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MERGED_CASE_STUDIES_PATH,
        help="Path to write the merged JSON array",
    )
    parser.add_argument(
        "--include-samples",
        type=Path,
        default=None,
        help="Optional path to a samples JSON array to fold in (real records override on id collision)",
    )
    args = parser.parse_args()

    counts = merge_records(
        records_root=args.records_root,
        output_path=args.output,
        include_samples=args.include_samples,
    )
    print(
        f"Merged samples={counts['samples']} extracted={counts['extracted']} "
        f"total={counts['total']} -> {args.output}"
    )


if __name__ == "__main__":
    main()
