"""Build bounded web-research jobs for records without confirmed publication dates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .settings import DATE_ENRICHMENT_JOBS_ROOT, GENERATED_CASE_STUDIES_PATH, TRIAGE_PATH
from .triage import load_decisions
from .utils import write_json


def build_date_research_jobs(
    *,
    records_path: Path = GENERATED_CASE_STUDIES_PATH,
    output_root: Path = DATE_ENRICHMENT_JOBS_ROOT,
    triage_path: Path = TRIAGE_PATH,
    limit: int | None = None,
    retry_researched: bool = False,
    write_jobs: bool = True,
) -> dict[str, int]:
    values = json.loads(records_path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError(f"{records_path} must contain a JSON array")
    undated = [record for record in values if isinstance(record, dict) and record.get("published_date") == "unknown"]
    researched_urls = {
        url
        for url, decision in load_decisions(triage_path).items()
        if decision.get("stage") == "date-research" and decision.get("date_checked") is True
    }
    pending = [
        record
        for record in undated
        if retry_researched or str(record.get("source_url") or "") not in researched_urls
    ]
    pending.sort(
        key=lambda record: (
            bool(record.get("date_evidence")),
            str(record.get("vendor") or ""),
            str(record.get("customer_name") or ""),
        )
    )
    if limit is not None:
        pending = pending[:limit]

    if write_jobs:
        output_root.mkdir(parents=True, exist_ok=True)
        for stale in output_root.glob("*.json"):
            stale.unlink()
    for record in pending:
        job: dict[str, Any] = {
            "record_id": record["id"],
            "vendor": record["vendor"],
            "customer_name": record["customer_name"],
            "source_url": record["source_url"],
            "current_date_evidence": record.get("date_evidence") or [],
            "policy": {
                "confirmed_publication_sources": [
                    "visible date on the original story",
                    "publication-specific HTML or JSON-LD metadata",
                    "official publisher catalog, API, RSS, or newsroom listing",
                ],
                "not_publication_dates": [
                    "sitemap lastmod",
                    "HTTP Last-Modified",
                    "Internet Archive capture",
                    "search result snippet without publisher confirmation",
                ],
                "required_action": (
                    "If a confirmed date is found, append it with triage --stage confirm-date and cite the exact "
                    "publisher-controlled evidence URL. Otherwise leave published_date unknown."
                ),
            },
        }
        if write_jobs:
            write_json(output_root / f"{record['id']}.json", job)
    return {"undated": len(undated), "unresearched": len(undated) - len(researched_urls & {str(record.get("source_url") or "") for record in undated}), "jobs": len(pending)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build publication-date research jobs.")
    parser.add_argument("command", choices=["queue", "status"])
    parser.add_argument("--records", type=Path, default=GENERATED_CASE_STUDIES_PATH)
    parser.add_argument("--output-root", type=Path, default=DATE_ENRICHMENT_JOBS_ROOT)
    parser.add_argument("--triage", type=Path, default=TRIAGE_PATH)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retry-researched", action="store_true")
    args = parser.parse_args()
    counts = build_date_research_jobs(
        records_path=args.records,
        output_root=args.output_root,
        triage_path=args.triage,
        limit=args.limit,
        retry_researched=args.retry_researched,
        write_jobs=args.command == "queue",
    )
    print(" ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
