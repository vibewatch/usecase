from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .models import load_records
from .scoring import compute_confidence_score, compute_maturity_score
from .settings import MERGED_CASE_STUDIES_PATH, SQLITE_PATH
from .storage import initialize_database, upsert_records


def enrich_scores(records: list[dict]) -> list[dict]:
    enriched = []
    for record in records:
        next_record = dict(record)
        if not next_record.get("maturity_score"):
            next_record["maturity_score"] = compute_maturity_score(next_record)
        if not next_record.get("confidence_score"):
            next_record["confidence_score"] = compute_confidence_score(next_record)
        enriched.append(next_record)
    return enriched


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

    print(f"Seeded {len(records)} records into {args.output}")


if __name__ == "__main__":
    main()