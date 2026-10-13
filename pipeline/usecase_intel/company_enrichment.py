"""Customer-level region and company-size enrichment with source provenance."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .settings import COMPANY_ENRICHMENT_JOBS_ROOT, COMPANY_ENRICHMENT_PATH, RECORDS_ROOT
from .utils import load_jsonl, slugify, write_json

UNKNOWN_VALUES = {"", "unknown", "not documented", "not stated", "n/a"}
COMPANY_SIZES = {"SMB", "Mid-market", "Enterprise", "Public sector"}
ENRICHABLE_FIELDS = {"region", "company_size"}


def is_unknown(value: object) -> bool:
    return str(value or "").strip().lower() in UNKNOWN_VALUES


def customer_key(value: str) -> str:
    return slugify(value)


def company_size_for_employees(employee_count: int) -> str:
    if employee_count < 0:
        raise ValueError("employee_count must be non-negative")
    if employee_count < 250:
        return "SMB"
    if employee_count < 1_000:
        return "Mid-market"
    return "Enterprise"


def _validate_source(source: object, position: int) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError(f"sources[{position}] must be an object")
    normalized = dict(source)
    for field in ("id", "title", "publisher", "url", "source_type", "authority", "retrieved_at", "evidence"):
        value = normalized.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"sources[{position}].{field} must be a non-empty string")
    supports = normalized.get("supports")
    if not isinstance(supports, list) or not supports or any(item not in ENRICHABLE_FIELDS for item in supports):
        raise ValueError(f"sources[{position}].supports must contain region and/or company_size")
    normalized["supports"] = list(dict.fromkeys(supports))
    normalized["published_date"] = str(normalized.get("published_date") or "unknown")
    normalized["published_date_source"] = str(normalized.get("published_date_source") or "unknown")
    return normalized


def validate_profile(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("company enrichment profile must be an object")
    profile = dict(value)
    customer_name = profile.get("customer_name")
    researched_at = profile.get("researched_at")
    if not isinstance(customer_name, str) or not customer_name.strip():
        raise ValueError("customer_name must be a non-empty string")
    if not isinstance(researched_at, str) or not researched_at.strip():
        raise ValueError("researched_at must be a non-empty ISO timestamp")

    profile["customer_key"] = str(profile.get("customer_key") or customer_key(customer_name))
    region = str(profile.get("region") or "unknown").strip()
    profile["region"] = region or "unknown"

    employee_count = profile.get("employee_count")
    if employee_count is not None and (not isinstance(employee_count, int) or employee_count < 0):
        raise ValueError("employee_count must be a non-negative integer when present")
    derived_size = company_size_for_employees(employee_count) if isinstance(employee_count, int) else None
    size = str(profile.get("company_size") or derived_size or "unknown").strip()
    if not is_unknown(size) and size not in COMPANY_SIZES:
        raise ValueError(f"company_size must be one of {sorted(COMPANY_SIZES)} or unknown")
    if derived_size and not is_unknown(size) and size != derived_size:
        raise ValueError(f"company_size {size!r} conflicts with employee_count-derived {derived_size!r}")
    profile["company_size"] = size or "unknown"

    researched_fields = profile.get("researched_fields", [])
    if not isinstance(researched_fields, list) or any(field not in ENRICHABLE_FIELDS for field in researched_fields):
        raise ValueError("researched_fields must contain region and/or company_size")
    profile["researched_fields"] = list(dict.fromkeys(researched_fields))

    sources = profile.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    profile["sources"] = [_validate_source(source, index) for index, source in enumerate(sources)]
    source_ids = [source["id"] for source in profile["sources"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source ids must be unique within a profile")

    for field in ENRICHABLE_FIELDS:
        if is_unknown(profile[field]):
            continue
        if not any(field in source["supports"] for source in profile["sources"]):
            raise ValueError(f"{field} has no supporting source")

    aliases = profile.get("aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
        raise ValueError("aliases must be a list of non-empty strings")
    profile["aliases"] = aliases
    profile["source_policy"] = str(profile.get("source_policy") or "balanced")
    return profile


def _merge_profiles(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    if incoming["researched_at"] >= current["researched_at"]:
        merged["customer_name"] = incoming["customer_name"]
        merged["source_policy"] = incoming["source_policy"]
    merged["researched_at"] = max(current["researched_at"], incoming["researched_at"])
    merged["aliases"] = list(dict.fromkeys([*current["aliases"], *incoming["aliases"]]))
    merged["researched_fields"] = list(
        dict.fromkeys([*current.get("researched_fields", []), *incoming.get("researched_fields", [])])
    )
    sources = {source["id"]: source for source in current["sources"]}
    sources.update({source["id"]: source for source in incoming["sources"]})
    merged["sources"] = list(sources.values())

    for field in ("region", "company_size"):
        if not is_unknown(incoming[field]):
            merged[field] = incoming[field]
    if incoming.get("employee_count") is not None:
        merged["employee_count"] = incoming["employee_count"]
        merged["employee_count_as_of"] = incoming.get("employee_count_as_of")
    return validate_profile(merged)


def load_company_enrichments(path: Path = COMPANY_ENRICHMENT_PATH) -> dict[str, dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for raw in load_jsonl(path):
        profile = validate_profile(raw)
        key = profile["customer_key"]
        canonical[key] = _merge_profiles(canonical[key], profile) if key in canonical else profile

    latest: dict[str, dict[str, Any]] = dict(canonical)
    for profile in canonical.values():
        keys = [customer_key(alias) for alias in profile["aliases"]]
        for key in keys:
            prior = latest.get(key)
            if prior is None or profile["researched_at"] >= prior["researched_at"]:
                latest[key] = profile
    return latest


def apply_company_enrichment(record: dict[str, Any], profiles: dict[str, dict[str, Any]]) -> list[str]:
    profile = profiles.get(customer_key(str(record.get("customer_name") or "")))
    if not profile:
        return []

    applied: list[str] = []
    for field in ("region", "company_size"):
        if is_unknown(record.get(field)) and not is_unknown(profile.get(field)):
            record[field] = profile[field]
            applied.append(field)
    if not applied:
        return []

    sources: list[dict[str, Any]] = []
    for source in profile["sources"]:
        supports = [field for field in source["supports"] if field in applied]
        if supports:
            sources.append({**source, "supports": supports})
    record["company_enrichment"] = {
        "customer_key": profile["customer_key"],
        "researched_at": profile["researched_at"],
        "source_policy": profile["source_policy"],
        "applied_fields": applied,
        "employee_count": profile.get("employee_count"),
        "employee_count_as_of": profile.get("employee_count_as_of"),
        "sources": sources,
    }
    return applied


def _record_files(records_root: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in sorted(records_root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            yield path, value


def build_research_jobs(
    *,
    records_root: Path = RECORDS_ROOT,
    enrichment_path: Path = COMPANY_ENRICHMENT_PATH,
    output_root: Path = COMPANY_ENRICHMENT_JOBS_ROOT,
    limit: int | None = None,
    write_jobs: bool = True,
    retry_researched: bool = False,
) -> dict[str, int]:
    profiles = load_company_enrichments(enrichment_path)
    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path, record in _record_files(records_root):
        key = customer_key(str(record.get("customer_name") or ""))
        grouped[key].append((path, record))

    jobs: list[tuple[str, dict[str, Any]]] = []
    for key, items in grouped.items():
        profile = profiles.get(key, {})
        needed = sorted(
            {
                field
                for _path, record in items
                for field in ENRICHABLE_FIELDS
                if is_unknown(record.get(field))
                and is_unknown(profile.get(field))
                and (retry_researched or field not in profile.get("researched_fields", []))
            }
        )
        if not needed:
            continue
        customer_name = str(items[0][1].get("customer_name") or key)
        jobs.append(
            (
                key,
                {
                    "customer_key": key,
                    "customer_name": customer_name,
                    "needed_fields": needed,
                    "record_ids": [str(record.get("id") or path.stem) for path, record in items],
                    "industries": sorted({str(record.get("industry") or "") for _path, record in items}),
                    "story_urls": sorted({str(record.get("source_url") or "") for _path, record in items}),
                    "policy": {
                        "source_priority": [
                            "official company website",
                            "government or regulatory registry",
                            "reputable structured company profile",
                        ],
                        "search_snippets_are_not_evidence": True,
                        "company_size_mapping": {
                            "SMB": "0-249 employees",
                            "Mid-market": "250-999 employees",
                            "Enterprise": "1000+ employees",
                            "Public sector": "government or public-sector organization",
                        },
                    },
                },
            )
        )
    jobs.sort(key=lambda item: (-len(item[1]["record_ids"]), item[0]))
    if limit is not None:
        jobs = jobs[:limit]
    if write_jobs:
        output_root.mkdir(parents=True, exist_ok=True)
        for stale in output_root.glob("*.json"):
            stale.unlink()
        for key, job in jobs:
            write_json(output_root / f"{key}.json", job)
    return {"customers": len(grouped), "jobs": len(jobs)}


def append_profile(input_path: Path, enrichment_path: Path = COMPANY_ENRICHMENT_PATH) -> None:
    profile = validate_profile(json.loads(input_path.read_text(encoding="utf-8")))
    enrichment_path.parent.mkdir(parents=True, exist_ok=True)
    with enrichment_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(profile, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate customer enrichment research.")
    parser.add_argument("command", choices=["queue", "validate", "status", "append"])
    parser.add_argument("--records-root", type=Path, default=RECORDS_ROOT)
    parser.add_argument("--enrichment", type=Path, default=COMPANY_ENRICHMENT_PATH)
    parser.add_argument("--output-root", type=Path, default=COMPANY_ENRICHMENT_JOBS_ROOT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retry-researched", action="store_true")
    parser.add_argument("--input", type=Path, default=None, help="Profile JSON to validate and append")
    args = parser.parse_args()

    if args.command == "append":
        if args.input is None:
            raise SystemExit("append requires --input")
        append_profile(args.input, args.enrichment)
        print(f"Appended validated company profile from {args.input}")
        return
    if args.command == "validate":
        profiles = load_company_enrichments(args.enrichment)
        print(f"Validated {len({profile['customer_key'] for profile in profiles.values()})} company profile(s)")
        return
    counts = build_research_jobs(
        records_root=args.records_root,
        enrichment_path=args.enrichment,
        output_root=args.output_root,
        limit=args.limit,
        write_jobs=args.command == "queue",
        retry_researched=args.retry_researched,
    )
    print(f"customers={counts['customers']} unresolved_jobs={counts['jobs']}")


if __name__ == "__main__":
    main()
