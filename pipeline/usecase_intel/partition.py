"""Partition the exported dataset into week-sized files under `data/weekly/`.

Each record is assigned to the ISO week in which it was first collected and
keeps that assignment on later runs — the committed weekly files are the
ledger. New records are dated by their earliest successful fetch in
`data/fetch_manifest.jsonl`, falling back to the build time. Synthetic samples
have no collection date and land in `data/weekly/undated.json`.

Layout:

    data/weekly/index.json             newest-first list of weeks + counts
    data/weekly/2026/2026-W41.json     references (id, vendor, customer, URLs, dates,
                                       record path) for stories collected that week
    data/weekly/undated.json           samples / records without a date

The step also stamps `collected_at` / `collected_week` onto the generated
dashboard dataset so the site can publish one JSON shard per week and
lazy-load older weeks.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .settings import FETCH_MANIFEST_PATH, GENERATED_CASE_STUDIES_PATH, WEEKLY_ROOT
from .utils import load_json, load_jsonl, slugify, write_json

UNDATED = "undated"
INDEX_NAME = "index.json"


def _url_key(url: str) -> str:
    return url.strip().rstrip("/").lower()


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_week(moment: datetime) -> str:
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def week_bounds(week: str) -> tuple[str, str]:
    year, number = week.split("-W")
    start = date.fromisocalendar(int(year), int(number), 1)
    end = date.fromisocalendar(int(year), int(number), 7)
    return start.isoformat(), end.isoformat()


def week_path(root: Path, week: str) -> Path:
    if week == UNDATED:
        return root / f"{UNDATED}.json"
    return root / week.split("-W")[0] / f"{week}.json"


def first_fetches(manifest_path: Path) -> dict[str, datetime]:
    """Earliest successful fetch time per source URL."""
    earliest: dict[str, datetime] = {}
    for row in load_jsonl(manifest_path):
        if row.get("status") != 200 or not isinstance(row.get("url"), str):
            continue
        fetched = _parse_timestamp(row.get("fetched_at"))
        if fetched is None:
            continue
        key = _url_key(row["url"])
        if key not in earliest or fetched < earliest[key]:
            earliest[key] = fetched
    return earliest


def existing_assignments(root: Path) -> dict[str, str]:
    """Record id -> collected_at from the weekly files already on disk."""
    assignments: dict[str, str] = {}
    if not root.exists():
        return assignments
    for path in sorted(root.rglob("*.json")):
        if path.name == INDEX_NAME:
            continue
        payload = load_json(path, default={})
        records = payload.get("records") if isinstance(payload, dict) else None
        for record in records or []:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                continue
            if _parse_timestamp(record.get("collected_at")):
                assignments[record["id"]] = record["collected_at"]
    return assignments


def partition(
    records: list[dict[str, Any]],
    *,
    root: Path,
    manifest_path: Path,
    now: datetime,
) -> dict[str, list[dict[str, Any]]]:
    """Stamp `collected_at` / `collected_week` on each record and group by week."""
    assignments = existing_assignments(root)
    fetched = first_fetches(manifest_path)
    weeks: dict[str, list[dict[str, Any]]] = {}

    for record in records:
        collected_at: str | None = None
        if not record.get("is_sample"):
            collected_at = assignments.get(record["id"])
            if collected_at is None:
                moment = fetched.get(_url_key(str(record.get("source_url", "")))) or now
                collected_at = moment.isoformat(timespec="seconds")

        moment = _parse_timestamp(collected_at)
        week = iso_week(moment) if moment else UNDATED
        record["collected_at"] = collected_at
        record["collected_week"] = week
        for reference in record.get("source_references") or []:
            if (
                isinstance(reference, dict)
                and _url_key(str(reference.get("url", ""))) == _url_key(str(record.get("source_url", "")))
                and reference.get("retrieved_at") in (None, "", "unknown")
            ):
                reference["retrieved_at"] = collected_at or "unknown"
        weeks.setdefault(week, []).append(record)

    return weeks


def _reference(record: dict[str, Any]) -> dict[str, Any]:
    """Weekly files hold references, not full copies: data/records/ stays the single source."""
    return {
        "id": record["id"],
        "slug": record.get("slug"),
        "vendor": record.get("vendor"),
        "customer_name": record.get("customer_name"),
        "source_url": record.get("source_url"),
        "published_date": record.get("published_date"),
        "collected_at": record.get("collected_at"),
        "record": None if record.get("is_sample") else f"data/records/{slugify(str(record.get('vendor', '')))}/{record.get('slug')}.json",
    }


def _date_sort_key(record: dict[str, Any]) -> str:
    published = str(record.get("published_date") or "")
    if published != "unknown":
        return published
    for evidence in record.get("date_evidence") or []:
        if isinstance(evidence, dict) and isinstance(evidence.get("date"), str):
            return evidence["date"]
    return ""


def write_partitions(weeks: dict[str, list[dict[str, Any]]], root: Path) -> list[dict[str, Any]]:
    """Write one file per week plus index.json; remove week files that emptied out."""
    root.mkdir(parents=True, exist_ok=True)
    dated = sorted((week for week in weeks if week != UNDATED), reverse=True)
    ordered = dated + ([UNDATED] if UNDATED in weeks else [])
    index: list[dict[str, Any]] = []
    written: set[Path] = set()

    for week in ordered:
        records = sorted(
            weeks[week],
            key=lambda record: (
                record.get("collected_at") or "",
                _date_sort_key(record),
                record["id"],
            ),
            reverse=True,
        )
        start, end = week_bounds(week) if week != UNDATED else (None, None)
        path = week_path(root, week)
        entries = [_reference(record) for record in records]
        write_json(path, {"week": week, "start": start, "end": end, "count": len(entries), "records": entries})
        written.add(path)
        index.append(
            {
                "week": week,
                "start": start,
                "end": end,
                "count": len(records),
                "path": path.relative_to(root).as_posix(),
            }
        )

    for stale in sorted(root.rglob("*.json")):
        if stale.name != INDEX_NAME and stale not in written:
            stale.unlink()
            print(f"  removed empty partition {stale}")
    for directory in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()

    write_json(root / INDEX_NAME, {"total": sum(entry["count"] for entry in index), "weeks": index})
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Partition the generated dataset into weekly files.")
    parser.add_argument("--input", type=Path, default=GENERATED_CASE_STUDIES_PATH, help="Generated dataset JSON")
    parser.add_argument("--root", type=Path, default=WEEKLY_ROOT, help="Directory for weekly partitions")
    parser.add_argument("--manifest", type=Path, default=FETCH_MANIFEST_PATH, help="Fetch manifest JSONL")
    args = parser.parse_args()

    records = load_json(args.input, default=None)
    if not isinstance(records, list):
        raise SystemExit(f"{args.input}: expected a JSON array (run `npm run data:export` first)")

    weeks = partition(records, root=args.root, manifest_path=args.manifest, now=datetime.now(timezone.utc))
    index = write_partitions(weeks, args.root)

    # Re-write the dashboard dataset with the collection stamps so the site
    # shards by exactly the same weeks.
    args.input.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Partitioned {len(records)} records into {len(index)} weekly file(s) under {args.root}")


if __name__ == "__main__":
    main()
