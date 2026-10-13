"""Merge per-vendor extracted records into a single JSON array for seeding.

The agent-driven extraction workflow writes one normalized JSON record per page
under `data/records/{vendor_slug}/{slug}.json`. `seed.py` expects a single JSON
array. This module walks the records tree, optionally folds in a samples file,
deduplicates by `id` and by story (`source_url`), and writes the combined array
to a target path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .settings import MERGED_CASE_STUDIES_PATH, RECORDS_ROOT, TRIAGE_PATH
from .utils import load_jsonl


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


def _richness(record: dict[str, Any]) -> int:
    """How much substance an extraction carries; the richer duplicate is kept."""
    return (
        100 * len(record.get("solution_components") or [])
        + 50 * len(record.get("metrics") or [])
        + 30 * len(record.get("evidence_quotes") or [])
        + 20 * len(record.get("integration_points") or [])
        + len(record.get("solution_summary") or "")
        + len(record.get("data_flow") or "")
    )


def _story_key(record: dict[str, Any]) -> str:
    return str(record.get("source_url") or "").strip().rstrip("/").lower()

def _date_provenance(path: Path | None) -> dict[str, tuple[str, str]]:
    if path is None:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        url = row.get("url")
        if isinstance(url, str) and url:
            latest[url.strip().rstrip("/").lower()] = row

    provenance: dict[str, tuple[str, str]] = {}
    source_labels = {
        "page": "page",
        "discovery": "vendor metadata",
        "wayback_first_capture": "wayback_first_capture",
    }
    for url, row in latest.items():
        published_date = row.get("published_date")
        source = source_labels.get(str(row.get("published_source") or ""))
        if isinstance(published_date, str) and published_date and source:
            provenance[url] = (published_date, source)
    return provenance


def _date_evidence(date: str, kind: str, publisher: str, url: str, authority: str) -> dict[str, str]:
    return {
        "date": date,
        "type": kind,
        "publisher": publisher,
        "url": url,
        "authority": authority,
    }


def _apply_date_policy(record: dict[str, Any], evidence: tuple[str, str] | None) -> None:
    authored_date = str(record.get("published_date") or "unknown")
    source_url = str(record.get("source_url") or "")
    publisher = record["customer_name"] if record.get("source_type") == "company" else record["vendor"]

    if evidence and evidence[1] in {"page", "vendor metadata"}:
        published_date, source = evidence
        record["published_date"] = published_date
        record["published_date_source"] = source
        record["date_evidence"] = [
            _date_evidence(
                published_date,
                "Published on source page" if source == "page" else "Publisher catalog date",
                publisher,
                source_url,
                "First-party",
            )
        ]
        return

    if evidence and evidence[1] == "wayback_first_capture":
        first_seen = evidence[0]
        record["published_date"] = "unknown"
        record["published_date_source"] = "unknown"
        record["date_evidence"] = [
            _date_evidence(
                first_seen,
                "First archived",
                "Internet Archive",
                f"https://web.archive.org/web/*/{source_url}",
                "Independent",
            )
        ]
        if authored_date not in {"", "unknown", first_seen}:
            record["date_evidence"].append(
                _date_evidence(authored_date, "Unverified extracted date", publisher, source_url, "Unknown")
            )
        return

    if record.get("published_date_source") in {"page", "page metadata", "vendor metadata", "api"}:
        record["date_evidence"] = [
            _date_evidence(authored_date, "Published on source page", publisher, source_url, "First-party")
        ]
        return

    record["published_date"] = "unknown"
    record["published_date_source"] = "unknown"
    record["date_evidence"] = (
        [_date_evidence(authored_date, "Unverified extracted date", publisher, source_url, "Unknown")]
        if authored_date not in {"", "unknown"}
        else []
    )


def merge_records(
    *,
    records_root: Path,
    output_path: Path,
    include_samples: Path | None = None,
    prune_duplicates: bool = False,
    triage_path: Path | None = None,
) -> dict[str, int]:
    records_by_id: dict[str, dict[str, Any]] = {}
    sample_count = 0
    record_count = 0
    pruned = 0
    date_provenance = _date_provenance(triage_path)

    if include_samples and include_samples.exists():
        for sample in _load_array(include_samples):
            rid = sample.get("id")
            if not rid:
                continue
            records_by_id[rid] = sample
            sample_count += 1

    if records_root.exists():
        loaded: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(records_root.rglob("*.json")):
            try:
                record = _load_record(path)
            except (json.JSONDecodeError, ValueError) as exc:
                print(f"  skip {path}: {exc}", file=sys.stderr)
                continue
            if not record.get("id"):
                print(f"  skip {path}: record missing 'id'", file=sys.stderr)
                continue
            _apply_date_policy(record, date_provenance.get(_story_key(record)))
            loaded.append((path, record))

        # One record per story: parallel runs can extract the same page twice under
        # different slugs. Keep the richest extraction (path breaks ties, so the
        # choice is stable) and, with prune_duplicates, delete the other files.
        by_story: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
        for path, record in loaded:
            key = _story_key(record) or f"id:{record['id']}"
            by_story.setdefault(key, []).append((path, record))
        for key, group in by_story.items():
            group.sort(key=lambda item: (-_richness(item[1]), str(item[0])))
            path, record = group[0]
            for duplicate_path, _duplicate in group[1:]:
                print(f"  duplicate of {path.name}: {duplicate_path}", file=sys.stderr)
                if prune_duplicates:
                    duplicate_path.unlink()
                pruned += 1
            # Real extractions override sample placeholders with the same id.
            records_by_id[record["id"]] = record
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
        "duplicates": pruned,
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
    parser.add_argument(
        "--prune-duplicates",
        action="store_true",
        help="Delete record files that duplicate a richer record for the same source_url",
    )
    args = parser.parse_args()

    counts = merge_records(
        records_root=args.records_root,
        output_path=args.output,
        include_samples=args.include_samples,
        prune_duplicates=args.prune_duplicates,
        triage_path=TRIAGE_PATH,
    )
    print(
        f"Merged samples={counts['samples']} extracted={counts['extracted']} "
        f"duplicates={counts['duplicates']}{' (pruned)' if args.prune_duplicates else ''} "
        f"total={counts['total']} -> {args.output}"
    )


if __name__ == "__main__":
    main()
