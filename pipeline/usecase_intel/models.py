from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_STRING_FIELDS = {
    "id",
    "slug",
    "vendor",
    "customer_name",
    "industry",
    "region",
    "company_size",
    "business_problem",
    "solution_summary",
    "business_outcome",
    "source_url",
    "published_date",
}

REQUIRED_LIST_FIELDS = {
    "products_used",
    "technical_area",
    "use_case_category",
    "outcome_category",
    "metrics",
    "architecture_clues",
    "evidence_quotes",
}


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as record_file:
        data = json.load(record_file)

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array of case study records")

    return [normalize_record(item, index) for index, item in enumerate(data)]


def normalize_record(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"record {index} must be a JSON object")

    record = dict(value)
    for field in REQUIRED_STRING_FIELDS:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"record {index} missing non-empty string field: {field}")

    for field in REQUIRED_LIST_FIELDS:
        items = record.get(field)
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise ValueError(f"record {index} field must be a list of strings: {field}")

    record["confidence_score"] = float(record.get("confidence_score", 0))
    record["maturity_score"] = int(record.get("maturity_score", 0))
    record["is_sample"] = bool(record.get("is_sample", False))
    return record