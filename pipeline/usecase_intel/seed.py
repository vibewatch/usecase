from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .models import load_records
from .scoring import score_record
from .settings import MERGED_CASE_STUDIES_PATH, SQLITE_PATH
from .storage import initialize_database, upsert_records


def enrich_scores(records: list[dict]) -> list[dict]:
    return [score_record(record) for record in records]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed normalized case studies into SQLite.")
    parser.add_argument("input", type=Path, nargs="?", default=MERGED_CASE_STUDIES_PATH, help="Path to normalized case study JSON")
    parser.add_argument("output", type=Path, nargs="?", default=SQLITE_PATH, help="Path to SQLite database")
    args = parser.parse_args()

    records = enrich_scores(load_records(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.output) as connection:
        connection.execute("pragma foreign_keys = on")
        initialize_database(connection)
        upsert_records(connection, records)
        # The merged file is the full set: drop rows for records since removed (e.g. pruned duplicates).
        connection.execute("create temp table current_ids (id text primary key)")
        connection.executemany("insert or ignore into current_ids values (?)", [(record["id"],) for record in records])
        connection.execute("delete from case_study_values where case_study_id not in (select id from current_ids)")
        removed = connection.execute("delete from case_studies where id not in (select id from current_ids)").rowcount
        connection.commit()

    print(f"Seeded {len(records)} records into {args.output}" + (f" (removed {removed} stale)" if removed else ""))


if __name__ == "__main__":
    main()