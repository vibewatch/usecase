from __future__ import annotations

from typing import Any


def compute_maturity_score(record: dict[str, Any]) -> int:
    checks = [
        bool(record.get("customer_name")),
        bool(record.get("business_problem")),
        bool(record.get("products_used")),
        bool(record.get("architecture_clues")),
        bool(record.get("metrics")),
        bool(record.get("business_outcome")),
    ]
    return sum(1 for check in checks if check)


def compute_confidence_score(record: dict[str, Any]) -> float:
    fields = [
        "customer_name",
        "industry",
        "business_problem",
        "solution_summary",
        "products_used",
        "technical_area",
        "use_case_category",
        "business_outcome",
        "metrics",
        "architecture_clues",
        "source_url",
        "published_date",
    ]
    completed = sum(1 for field in fields if record.get(field))
    return round(completed / len(fields), 2)