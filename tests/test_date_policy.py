from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.usecase_intel.merge_records import _apply_date_policy
from pipeline.usecase_intel.triage import (
    detect_page_metadata_date,
    detect_published_date_info,
    enrich_metadata_dates,
)


def record_fixture() -> dict:
    return {
        "vendor": "OpenAI",
        "customer_name": "Example Co",
        "source_url": "https://example.com/story",
        "published_date": "2026-10-10",
    }


class DatePolicyTests(unittest.TestCase):
    def test_page_date_is_authoritative(self) -> None:
        record = record_fixture()
        _apply_date_policy(record, ("2025-03-06", "page"))

        self.assertEqual(record["published_date"], "2025-03-06")
        self.assertEqual(record["published_date_source"], "page")
        self.assertEqual(record["date_evidence"][0]["type"], "Published on source page")

    def test_page_metadata_date_is_authoritative(self) -> None:
        record = record_fixture()
        _apply_date_policy(record, ("2025-03-06", "page metadata"))

        self.assertEqual(record["published_date"], "2025-03-06")
        self.assertEqual(record["published_date_source"], "page metadata")
        self.assertEqual(record["date_evidence"][0]["type"], "Published on source page")

    def test_archive_capture_is_not_a_publication_date(self) -> None:
        record = record_fixture()
        _apply_date_policy(record, ("2026-01-12", "wayback_first_capture"))

        self.assertEqual(record["published_date"], "unknown")
        self.assertEqual(record["published_date_source"], "unknown")
        self.assertEqual(record["date_evidence"][0]["type"], "First archived")
        self.assertEqual(record["date_evidence"][0]["date"], "2026-01-12")

    def test_unverified_legacy_date_is_quarantined(self) -> None:
        record = record_fixture()
        _apply_date_policy(record, None)

        self.assertEqual(record["published_date"], "unknown")
        self.assertEqual(record["date_evidence"][0]["type"], "Unverified extracted date")

    def test_publisher_catalog_date_can_remain_published(self) -> None:
        record = record_fixture()
        _apply_date_policy(record, ("2025-04-15", "vendor metadata"))

        self.assertEqual(record["published_date"], "2025-04-15")
        self.assertEqual(record["published_date_source"], "vendor metadata")

    def test_sitemap_lastmod_is_modification_evidence_only(self) -> None:
        record = record_fixture()
        record["published_date"] = "unknown"

        _apply_date_policy(record, None, "2025-08-09")

        self.assertEqual(record["published_date"], "unknown")
        self.assertEqual(record["published_date_source"], "unknown")
        self.assertEqual(record["date_evidence"][0]["type"], "Sitemap last modified")

    def test_researched_date_preserves_explicit_source_metadata(self) -> None:
        record = record_fixture()

        _apply_date_policy(
            record,
            (
                "2025-04-15",
                "api",
                "https://example.com/catalog",
                "Example Publisher",
                "First-party",
            ),
        )

        evidence = record["date_evidence"][0]
        self.assertEqual(evidence["url"], "https://example.com/catalog")
        self.assertEqual(evidence["publisher"], "Example Publisher")
        self.assertEqual(evidence["authority"], "First-party")

    def test_html_meta_date_is_detected_regardless_of_attribute_order(self) -> None:
        html = '<meta content="2025-03-06T09:30:00Z" property="article:published_time">'

        self.assertEqual(detect_page_metadata_date(html), "2025-03-06")
        self.assertEqual(detect_published_date_info(html, ""), ("2025-03-06", "page metadata"))

    def test_json_ld_date_is_detected(self) -> None:
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Article","dateModified":"2026-01-01","datePublished":"2024-11-08"}'
            "</script>"
        )

        self.assertEqual(detect_page_metadata_date(html), "2024-11-08")

    def test_modified_and_generic_time_dates_are_ignored(self) -> None:
        html = (
            '<meta property="article:modified_time" content="2026-01-01">'
            '<time datetime="2025-02-02">February 2, 2025</time>'
        )

        self.assertIsNone(detect_page_metadata_date(html))

    def test_metadata_stage_backfills_cached_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_path = root / "story.html"
            manifest_path = root / "fetch.jsonl"
            triage_path = root / "triage.jsonl"
            raw_path.write_text(
                '<meta property="article:published_time" content="2025-06-12">',
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "url": "https://example.com/story",
                        "vendor": "Example",
                        "status": 200,
                        "raw_path": str(raw_path),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            triage_path.write_text(
                json.dumps(
                    {
                        "url": "https://example.com/story",
                        "vendor": "Example",
                        "stage": "post",
                        "decision": "keep",
                        "reasons": [],
                        "published_date": None,
                        "published_source": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            counts = enrich_metadata_dates(manifest_path=manifest_path, output_path=triage_path)
            rows = [json.loads(line) for line in triage_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(counts["updated"], 1)
        self.assertEqual(rows[-1]["published_date"], "2025-06-12")
        self.assertEqual(rows[-1]["published_source"], "page metadata")


if __name__ == "__main__":
    unittest.main()
