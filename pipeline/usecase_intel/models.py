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
    "source_language",  # ISO 639-1 code of a non-English source; the record itself is in English
    "source_type",  # "company" when published on the adopting company's own website (else a vendor story)
    "published_date_source",
}

OPTIONAL_LIST_FIELDS = {
    "integration_points",
}

PRIMARY_SOURCE_FIELDS = [
    "customer_name",
    "business_problem",
    "solution_summary",
    "products_used",
    "solution_components",
    "data_flow",
    "integration_points",
    "technical_area",
    "use_case_category",
    "business_outcome",
    "outcome_category",
    "metrics",
    "architecture_clues",
    "evidence_quotes",
]


def _normalize_sources(record: dict[str, Any], index: int) -> None:
    date_evidence = record.get("date_evidence", [])
    if not isinstance(date_evidence, list):
        raise ValueError(f"record {index} date_evidence must be a list when present")
    for position, item in enumerate(date_evidence):
        if not isinstance(item, dict):
            raise ValueError(f"record {index} date_evidence[{position}] must be an object")
        for field in ("date", "type", "publisher", "url", "authority"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"record {index} date_evidence[{position}].{field} must be a non-empty string")

    references = record.get("source_references")
    if references is None:
        source_id = "primary-story"
        supports = list(PRIMARY_SOURCE_FIELDS)
        if record.get("published_date") != "unknown":
            supports.append("published_date")
        references = [
            {
                "id": source_id,
                "title": f"{record['customer_name']} customer story",
                "publisher": record["customer_name"] if record.get("source_type") == "company" else record["vendor"],
                "url": record["source_url"],
                "source_type": (
                    "Customer-published story"
                    if record.get("source_type") == "company"
                    else "Vendor-published customer story"
                ),
                "authority": "First-party",
                "published_date": record["published_date"],
                "published_date_source": record.get("published_date_source", "unknown"),
                "retrieved_at": record.get("collected_at") or "unknown",
                "supports": supports,
            }
        ]
    elif not isinstance(references, list):
        raise ValueError(f"record {index} source_references must be a list when present")
    else:
        references = list(references)

    enrichment = record.get("company_enrichment")
    enrichment_references: list[dict[str, Any]] = []
    if enrichment is not None:
        if not isinstance(enrichment, dict):
            raise ValueError(f"record {index} company_enrichment must be an object when present")
        raw_sources = enrichment.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError(f"record {index} company_enrichment.sources must be a list")
        enrichment_references = [dict(source) for source in raw_sources if isinstance(source, dict)]
        references.extend(enrichment_references)
    if not isinstance(references, list) or not references:
        raise ValueError(f"record {index} source_references must be a non-empty list when present")

    source_ids: set[str] = set()
    for position, reference in enumerate(references):
        if not isinstance(reference, dict):
            raise ValueError(f"record {index} source_references[{position}] must be an object")
        for field in ("id", "title", "publisher", "url", "source_type", "authority"):
            value = reference.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"record {index} source_references[{position}].{field} must be a non-empty string"
                )
        source_id = reference["id"]
        if source_id in source_ids:
            raise ValueError(f"record {index} source reference id must be unique: {source_id}")
        source_ids.add(source_id)
        for field in ("published_date", "published_date_source", "retrieved_at"):
            value = reference.get(field, "unknown")
            if not isinstance(value, str):
                raise ValueError(f"record {index} source_references[{position}].{field} must be a string")
            reference[field] = value or "unknown"
        supports = reference.get("supports", [])
        if not isinstance(supports, list) or any(not isinstance(item, str) for item in supports):
            raise ValueError(f"record {index} source_references[{position}].supports must be a list of strings")

    field_sources = record.get("field_sources")
    if field_sources is not None and not isinstance(field_sources, dict):
        raise ValueError(f"record {index} field_sources must be an object when present")
    if field_sources is None:
        field_sources = {}
        for reference in references:
            for field in reference.get("supports", []):
                field_sources.setdefault(field, []).append(reference["id"])
    else:
        for reference in enrichment_references:
            for field in reference.get("supports", []):
                ids = field_sources.setdefault(field, [])
                if reference["id"] not in ids:
                    ids.append(reference["id"])
    for field, ids in field_sources.items():
        if not isinstance(field, str) or not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            raise ValueError(f"record {index} field_sources values must be lists of source ids")
        unknown = set(ids) - source_ids
        if unknown:
            raise ValueError(f"record {index} field_sources[{field}] contains unknown source ids: {sorted(unknown)}")

    record["source_references"] = references
    record["field_sources"] = field_sources
    record["published_date_source"] = record.get("published_date_source", "unknown") or "unknown"


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

    _normalize_sources(record, index)
    record["confidence_score"] = float(record.get("confidence_score", 0))
    record["maturity_score"] = int(record.get("maturity_score", 0))
    record["value_score"] = int(record.get("value_score", 0))
    record["is_sample"] = bool(record.get("is_sample", False))
    return record