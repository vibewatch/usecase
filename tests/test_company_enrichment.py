from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.usecase_intel.company_enrichment import (
    append_profile,
    apply_company_enrichment,
    build_research_jobs,
    company_size_for_employees,
    load_company_enrichments,
    validate_profile,
)
from pipeline.usecase_intel.models import normalize_record
from tests.test_scoring import record_fixture


def profile_fixture() -> dict:
    return {
        "customer_name": "Example Co",
        "region": "United Kingdom",
        "employee_count": 249,
        "researched_at": "2026-10-13T14:40:18+00:00",
        "sources": [
            {
                "id": "company-registry",
                "title": "Example Co registry entry",
                "publisher": "Companies House",
                "url": "https://example.com/registry",
                "source_type": "Government registry",
                "authority": "Government",
                "retrieved_at": "2026-10-13T14:40:18+00:00",
                "supports": ["region"],
                "evidence": "Registered office in the United Kingdom.",
            },
            {
                "id": "company-profile",
                "title": "Example Co profile",
                "publisher": "Example Directory",
                "url": "https://example.com/profile",
                "source_type": "Structured company profile",
                "authority": "Independent secondary",
                "retrieved_at": "2026-10-13T14:40:18+00:00",
                "supports": ["company_size"],
                "evidence": "249 employees.",
            },
        ],
    }


class CompanyEnrichmentTests(unittest.TestCase):
    def test_employee_thresholds(self) -> None:
        self.assertEqual(company_size_for_employees(249), "SMB")
        self.assertEqual(company_size_for_employees(250), "Mid-market")
        self.assertEqual(company_size_for_employees(999), "Mid-market")
        self.assertEqual(company_size_for_employees(1_000), "Enterprise")

    def test_enrichment_only_replaces_unknown_values(self) -> None:
        profile = validate_profile(profile_fixture())
        record = record_fixture()
        record["region"] = "Unknown"
        record["company_size"] = "Unknown"

        applied = apply_company_enrichment(record, {"example-co": profile})

        self.assertEqual(applied, ["region", "company_size"])
        self.assertEqual(record["region"], "United Kingdom")
        self.assertEqual(record["company_size"], "SMB")

    def test_normalization_adds_enrichment_sources_and_field_links(self) -> None:
        profile = validate_profile(profile_fixture())
        record = record_fixture()
        record["region"] = "Unknown"
        record["company_size"] = "Unknown"
        apply_company_enrichment(record, {"example-co": profile})

        normalized = normalize_record(record, 0)

        self.assertEqual(len(normalized["source_references"]), 3)
        self.assertEqual(normalized["field_sources"]["region"], ["company-registry"])
        self.assertEqual(normalized["field_sources"]["company_size"], ["company-profile"])

    def test_known_values_are_not_overwritten(self) -> None:
        profile = validate_profile(profile_fixture())
        record = record_fixture()

        applied = apply_company_enrichment(record, {"example-co": profile})

        self.assertEqual(applied, [])
        self.assertNotIn("company_enrichment", record)

    def test_append_profile_validates_and_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "profile.json"
            ledger_path = root / "company-enrichment.jsonl"
            input_path.write_text(json.dumps(profile_fixture()), encoding="utf-8")

            append_profile(input_path, ledger_path)

            written = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(written["customer_key"], "example-co")
            self.assertEqual(written["company_size"], "SMB")

    def test_partial_profile_update_preserves_prior_sourced_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "company-enrichment.jsonl"
            original = profile_fixture()
            update = {
                "customer_key": "example-co",
                "customer_name": "Example Co",
                "region": "unknown",
                "company_size": "unknown",
                "researched_fields": ["company_size"],
                "researched_at": "2026-10-14T14:40:18+00:00",
                "sources": [],
            }
            path.write_text(
                json.dumps(original) + "\n" + json.dumps(update) + "\n",
                encoding="utf-8",
            )

            profile = load_company_enrichments(path)["example-co"]

            self.assertEqual(profile["region"], "United Kingdom")
            self.assertEqual(profile["company_size"], "SMB")
            self.assertEqual(profile["researched_fields"], ["company_size"])

    def test_researched_unknown_fields_are_not_requeued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = root / "records"
            records.mkdir()
            (records / "example.json").write_text(
                json.dumps(
                    {
                        "id": "example",
                        "customer_name": "Example Co",
                        "industry": "Technology",
                        "region": "Unknown",
                        "company_size": "Unknown",
                        "source_url": "https://example.com/story",
                    }
                ),
                encoding="utf-8",
            )
            ledger = root / "company-enrichment.jsonl"
            ledger.write_text(
                json.dumps(
                    {
                        "customer_name": "Example Co",
                        "region": "unknown",
                        "company_size": "unknown",
                        "researched_fields": ["region", "company_size"],
                        "researched_at": "2026-10-14T14:40:18+00:00",
                        "sources": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            counts = build_research_jobs(
                records_root=records,
                enrichment_path=ledger,
                output_root=root / "jobs",
            )

            self.assertEqual(counts["jobs"], 0)


if __name__ == "__main__":
    unittest.main()
