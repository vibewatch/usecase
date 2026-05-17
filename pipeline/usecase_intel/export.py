from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .settings import GENERATED_CASE_STUDIES_PATH, SQLITE_PATH
from .storage import MULTI_VALUE_FIELDS


def export_records(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute("select raw_json from case_studies order by vendor, customer_name").fetchall()
    records = [json.loads(row[0]) for row in rows]

    for record in records:
        values = connection.execute(
            "select kind, value from case_study_values where case_study_id = ? order by kind, value",
            (record["id"],),
        ).fetchall()
        by_kind: dict[str, list[str]] = {}
        for kind, value in values:
            by_kind.setdefault(kind, []).append(value)

        for field, kind in MULTI_VALUE_FIELDS.items():
            record[field] = by_kind.get(kind, [])

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Export case studies from SQLite to normalized JSON.")
    parser.add_argument("input", type=Path, nargs="?", default=SQLITE_PATH, help="Path to SQLite database")
    parser.add_argument("output", type=Path, nargs="?", default=GENERATED_CASE_STUDIES_PATH, help="Path to output JSON")
    args = parser.parse_args()

    with sqlite3.connect(args.input) as connection:
        records = export_records(connection)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()