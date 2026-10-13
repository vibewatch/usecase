from __future__ import annotations

import unittest

from pipeline.usecase_intel.merge_records import _apply_date_policy


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


if __name__ == "__main__":
    unittest.main()
