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

OPTIONAL_STRING_FIELDS = {
    "data_flow",
}

OPTIONAL_LIST_FIELDS = {
    "integration_points",
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

    for field in OPTIONAL_STRING_FIELDS:
        if field in record and record[field] is not None and not isinstance(record[field], str):
            raise ValueError(f"record {index} optional field must be a string when present: {field}")

    for field in OPTIONAL_LIST_FIELDS:
        items = record.get(field)
        if items is None:
            continue
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise ValueError(f"record {index} optional field must be a list of strings when present: {field}")

    components = record.get("solution_components")
    if components is not None:
        if not isinstance(components, list):
            raise ValueError(f"record {index} solution_components must be a list when present")
        for position, component in enumerate(components):
            if not isinstance(component, dict):
                raise ValueError(f"record {index} solution_components[{position}] must be an object")
            name = component.get("name")
            role = component.get("role")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"record {index} solution_components[{position}].name must be a non-empty string")
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"record {index} solution_components[{position}].role must be a non-empty string")
            layer = component.get("layer")
            if layer is not None and (not isinstance(layer, str) or not layer.strip()):
                raise ValueError(f"record {index} solution_components[{position}].layer must be a non-empty string when present")

    record["confidence_score"] = float(record.get("confidence_score", 0))
    record["maturity_score"] = int(record.get("maturity_score", 0))
    record["is_sample"] = bool(record.get("is_sample", False))
    return record