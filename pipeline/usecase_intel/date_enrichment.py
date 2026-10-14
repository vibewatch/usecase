"""Build bounded web-research jobs for records without confirmed publication dates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .browser_fetch import BrowserFetcher
from .clean import content_to_text
from .settings import DATE_ENRICHMENT_JOBS_ROOT, GENERATED_CASE_STUDIES_PATH, TRIAGE_PATH
from .triage import detect_published_date_info, load_decisions
from .utils import write_json


def inspect_rendered_publication_date(
    url: str,
    *,
    output_path: Path | None = None,
    timeout_seconds: float = 45.0,
    fetcher: BrowserFetcher | None = None,
) -> dict[str, Any]:
    owns_fetcher = fetcher is None
    browser = fetcher or BrowserFetcher(timeout_seconds=timeout_seconds, max_response_bytes=8_000_000)
    try:
        result = browser.fetch(url)
    finally:
        if owns_fetcher:
            browser.close()

    if not 200 <= result.status < 400:
        raise RuntimeError(f"rendered page returned HTTP {result.status}")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(result.body)

    raw_html = result.body.decode("utf-8", errors="replace")
    title, text, extraction_method = content_to_text(
        result.body,
        content_type="text/html; charset=utf-8",
        max_chars=200_000,
    )
    published_date, published_source = detect_published_date_info(raw_html, text)
    return {
        "url": url,
        "final_url": result.final_url,
        "status": result.status,
        "title": title,
        "published_date": published_date,
        "published_source": published_source,
        "rendered_output": str(output_path) if output_path is not None else None,
        "extraction_method": extraction_method,
    }


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
    parser.add_argument("command", choices=["queue", "status", "inspect-url"])
    parser.add_argument("--records", type=Path, default=GENERATED_CASE_STUDIES_PATH)
    parser.add_argument("--output-root", type=Path, default=DATE_ENRICHMENT_JOBS_ROOT)
    parser.add_argument("--triage", type=Path, default=TRIAGE_PATH)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retry-researched", action="store_true")
    parser.add_argument("--url", type=str, default=None)
    parser.add_argument("--rendered-output", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    if args.command == "inspect-url":
        if not args.url:
            raise SystemExit("inspect-url requires --url")
        result = inspect_rendered_publication_date(
            args.url,
            output_path=args.rendered_output,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

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
