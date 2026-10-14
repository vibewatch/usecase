from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.usecase_intel.browser_fetch import BrowserFetchResult
from pipeline.usecase_intel.date_enrichment import build_date_research_jobs, inspect_rendered_publication_date
from pipeline.usecase_intel.triage import confirm_date, load_decisions, mark_date_unresolved


class DateEnrichmentTests(unittest.TestCase):
    def test_rendered_inspection_detects_publication_metadata(self) -> None:
        class FakeFetcher:
            def fetch(self, url: str) -> BrowserFetchResult:
                return BrowserFetchResult(
                    status=200,
                    final_url=url,
                    body=(
                        b'<html><head><title>Example story</title>'
                        b'<meta property="article:published_time" content="2025-06-12T09:30:00Z">'
                        b"</head><body><main>Customer story</main></body></html>"
                    ),
                )

        result = inspect_rendered_publication_date(
            "https://example.com/story",
            fetcher=FakeFetcher(),
        )

        self.assertEqual(result["published_date"], "2025-06-12")
        self.assertEqual(result["published_source"], "page metadata")
        self.assertEqual(result["title"], "Example story")

    def test_confirm_date_preserves_decision_and_records_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "triage.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "url": "https://example.com/story",
                        "vendor": "Example",
                        "stage": "post",
                        "decision": "keep",
                        "published_date": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            confirm_date(
                url="https://example.com/story",
                published_date="2025-04-03",
                published_source="vendor metadata",
                evidence_url="https://example.com/customer-catalog",
                evidence_publisher="Example",
                evidence_authority="First-party",
                output_path=path,
            )

            latest = load_decisions(path)["https://example.com/story"]
            self.assertEqual(latest["decision"], "keep")
            self.assertEqual(latest["published_date"], "2025-04-03")
            self.assertEqual(latest["published_evidence_url"], "https://example.com/customer-catalog")

    def test_confirm_date_rejects_invalid_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "real YYYY-MM-DD"):
                confirm_date(
                    url="https://example.com/story",
                    published_date="2025-02-30",
                    published_source="page",
                    evidence_url="https://example.com/story",
                    evidence_publisher="Example",
                    evidence_authority="First-party",
                    output_path=Path(temporary) / "triage.jsonl",
                )

    def test_unresolved_attempt_is_not_requeued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records_path = root / "records.json"
            triage_path = root / "triage.jsonl"
            records_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "example",
                            "vendor": "Example",
                            "customer_name": "Example Co",
                            "source_url": "https://example.com/story",
                            "published_date": "unknown",
                            "date_evidence": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            mark_date_unresolved(
                url="https://example.com/story",
                notes="Original page and official catalog checked.",
                output_path=triage_path,
            )

            counts = build_date_research_jobs(
                records_path=records_path,
                output_root=root / "jobs",
                triage_path=triage_path,
            )

            self.assertEqual(counts["undated"], 1)
            self.assertEqual(counts["unresearched"], 0)
            self.assertEqual(counts["jobs"], 0)


if __name__ == "__main__":
    unittest.main()
