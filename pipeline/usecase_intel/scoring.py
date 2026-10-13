from __future__ import annotations

import re
from typing import Any

TRACEABLE_FIELDS = [
    "customer_name",
    "business_problem",
    "solution_summary",
    "products_used",
    "solution_components",
    "data_flow",
    "integration_points",
    "business_outcome",
    "metrics",
    "architecture_clues",
    "region",
    "company_size",
]

IMPACT_RE = re.compile(
    r"(?:%|\b\d+(?:\.\d+)?x\b|reduc|sav(?:e|ing)|increase|improv|faster|accuracy|"
    r"latency|productiv|revenue|cost|time to|hours?|minutes?|seconds?|days?|weeks?)",
    re.IGNORECASE,
)
DEPLOYMENT_RE = re.compile(
    r"\b(?:production|deployed|deployment|rolled out|launched|live|scale|global|"
    r"employees|users|customers|transactions|requests|countries|regions|sites|stores)\b",
    re.IGNORECASE,
)


def _criterion(criterion: str, score: int, max_score: int, explanation: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "score": score,
        "max_score": max_score,
        "explanation": explanation,
    }


def _source_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    references = record.get("source_references")
    return [reference for reference in references or [] if isinstance(reference, dict)]


def _quantified_impact_metrics(record: dict[str, Any]) -> list[str]:
    outcome = str(record.get("business_outcome") or "")
    candidates = [str(metric) for metric in record.get("metrics") or []]
    return [
        metric
        for metric in candidates
        if re.search(r"\d", metric) and (IMPACT_RE.search(metric) or metric.lower() in outcome.lower())
    ]


def _source_transparency_score(references: list[dict[str, Any]]) -> tuple[int, str]:
    if not references:
        return 0, "No structured source reference is available."

    scores: list[int] = []
    for reference in references:
        score = 0
        if reference.get("title") and reference.get("publisher"):
            score += 2
        if reference.get("url") and reference.get("source_type"):
            score += 2
        if str(reference.get("authority") or "").lower() not in {"", "unknown"}:
            score += 2
        if str(reference.get("retrieved_at") or "").lower() not in {"", "unknown"}:
            score += 2
        if reference.get("supports"):
            score += 2
        scores.append(score)

    result = round(sum(scores) / len(scores))
    return result, (
        f"{len(references)} source reference{'s' if len(references) != 1 else ''} document "
        "publisher, URL, authority, retrieval, and supported fields."
    )


def compute_confidence_breakdown(record: dict[str, Any]) -> list[dict[str, Any]]:
    references = _source_references(record)
    source_types = " ".join(str(reference.get("source_type") or "") for reference in references).lower()
    authorities = " ".join(str(reference.get("authority") or "") for reference in references).lower()
    if "customer-published" in source_types or "government" in authorities:
        authority_score = 25
        authority_text = "The deployment is described by the adopting organization or a government source."
    elif "first-party" in authorities or "vendor-published" in source_types:
        authority_score = 20
        authority_text = "The main evidence is an official vendor-published customer story."
    elif references:
        authority_score = 10
        authority_text = "Sources are present but are not identified as first-party."
    else:
        authority_score = 0
        authority_text = "No structured source reference is available."

    field_sources = record.get("field_sources") or {}
    traced = sum(1 for field in TRACEABLE_FIELDS if field_sources.get(field))
    traceability_score = round(25 * traced / len(TRACEABLE_FIELDS))

    quote_count = len(record.get("evidence_quotes") or [])
    evidence_score = min(20, quote_count * 5)

    date_source = str(record.get("published_date_source") or "unknown").lower()
    if date_source in {"page", "page metadata", "article", "customer", "publisher"}:
        date_score = 10
        date_text = "The publication date comes from the source page or publisher."
    elif date_source in {"vendor metadata", "api"}:
        date_score = 8
        date_text = "The publication date comes from publisher-controlled metadata."
    elif date_source in {"wayback_first_capture", "internet archive", "sitemap", "lastmod"}:
        date_score = 3
        date_text = "The date is an archive or modification proxy, not a confirmed publication date."
    else:
        date_score = 0
        date_text = "The publication date has no documented provenance."

    transparency_score, transparency_text = _source_transparency_score(references)

    specificity_score = 0
    if record.get("solution_components"):
        specificity_score += 4
    if record.get("data_flow"):
        specificity_score += 2
    if _quantified_impact_metrics(record):
        specificity_score += 2
    if len(str(record.get("business_outcome") or "")) >= 80:
        specificity_score += 2

    return [
        _criterion("Source authority", authority_score, 25, authority_text),
        _criterion(
            "Claim traceability",
            traceability_score,
            25,
            f"{traced} of {len(TRACEABLE_FIELDS)} key fields link to a named source.",
        ),
        _criterion(
            "Direct evidence",
            evidence_score,
            20,
            f"{quote_count} direct source quote{'s' if quote_count != 1 else ''} retained.",
        ),
        _criterion("Date provenance", date_score, 10, date_text),
        _criterion("Source transparency", transparency_score, 10, transparency_text),
        _criterion(
            "Implementation specificity",
            specificity_score,
            10,
            "Rewards source-backed components, data flow, quantified impact, and a specific outcome.",
        ),
    ]


def compute_value_breakdown(record: dict[str, Any]) -> list[dict[str, Any]]:
    problem_length = len(str(record.get("business_problem") or "").strip())
    problem_score = 20 if problem_length >= 100 else 12 if problem_length >= 50 else 5 if problem_length else 0

    implementation_score = 0
    if record.get("solution_components"):
        implementation_score += 10
    if record.get("data_flow"):
        implementation_score += 5
    if record.get("integration_points"):
        implementation_score += 5
    if record.get("architecture_clues"):
        implementation_score += 5

    outcome = str(record.get("business_outcome") or "").strip()
    outcome_score = 0
    if len(outcome) >= 100:
        outcome_score += 12
    elif len(outcome) >= 50:
        outcome_score += 8
    elif outcome:
        outcome_score += 4
    if record.get("outcome_category"):
        outcome_score += 4
    if IMPACT_RE.search(outcome):
        outcome_score += 4

    impact_metrics = _quantified_impact_metrics(record)
    impact_score = 25 if len(impact_metrics) >= 2 else 15 if impact_metrics else 0

    deployment_text = " ".join(
        [
            str(record.get("solution_summary") or ""),
            outcome,
            *[str(item) for item in record.get("architecture_clues") or []],
        ]
    )
    deployment_score = 0
    if DEPLOYMENT_RE.search(deployment_text):
        deployment_score += 5
    if record.get("integration_points") or len(record.get("solution_components") or []) >= 3:
        deployment_score += 5

    return [
        _criterion(
            "Problem clarity",
            problem_score,
            20,
            "Measures whether the customer's operational problem is specific enough to compare.",
        ),
        _criterion(
            "Implementation depth",
            implementation_score,
            25,
            "Rewards named components, data flow, integrations, and architecture detail.",
        ),
        _criterion(
            "Outcome specificity",
            outcome_score,
            20,
            "Measures whether the reported benefit is concrete rather than a generic claim.",
        ),
        _criterion(
            "Quantified impact",
            impact_score,
            25,
            f"{len(impact_metrics)} metric{'s' if len(impact_metrics) != 1 else ''} describe measurable impact.",
        ),
        _criterion(
            "Deployment scale",
            deployment_score,
            10,
            "Rewards evidence of a live or scaled deployment and meaningful integration scope.",
        ),
    ]


def compute_maturity_score(record: dict[str, Any]) -> int:
    date_source = str(record.get("published_date_source") or "unknown").lower()
    checks = [
        len(str(record.get("business_problem") or "")) >= 50,
        bool(record.get("products_used")),
        bool(record.get("solution_components") or record.get("data_flow") or record.get("architecture_clues")),
        len(str(record.get("business_outcome") or "")) >= 50,
        bool(_quantified_impact_metrics(record)),
        date_source in {"page", "page metadata", "vendor metadata", "api"},
    ]
    return sum(1 for check in checks if check)


def compute_confidence_score(record: dict[str, Any]) -> float:
    breakdown = compute_confidence_breakdown(record)
    return round(sum(item["score"] for item in breakdown) / 100, 2)


def compute_value_score(record: dict[str, Any]) -> int:
    return sum(item["score"] for item in compute_value_breakdown(record))


def score_record(record: dict[str, Any]) -> dict[str, Any]:
    scored = dict(record)
    scored["confidence_breakdown"] = compute_confidence_breakdown(scored)
    scored["confidence_score"] = compute_confidence_score(scored)
    scored["value_breakdown"] = compute_value_breakdown(scored)
    scored["value_score"] = compute_value_score(scored)
    scored["maturity_score"] = compute_maturity_score(scored)
    return scored