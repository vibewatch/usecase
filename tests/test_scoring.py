from __future__ import annotations

import unittest

from pipeline.usecase_intel.models import normalize_record
from pipeline.usecase_intel.scoring import score_record


def record_fixture() -> dict:
    return {
        "id": "vendor-customer-use-case",
        "slug": "vendor-customer-use-case",
        "vendor": "AWS",
        "customer_name": "Example Co",
        "industry": "Retail",
        "region": "Global",
        "company_size": "Enterprise",
        "business_problem": "Example Co needed to reduce slow manual review work across its global customer operations.",
        "solution_summary": "The company deployed a production workflow with named AI services and connected it to operational systems.",
        "products_used": ["Example AI"],
        "solution_components": [{"name": "Example AI", "role": "Classifies incoming requests.", "layer": "Compute"}],
        "data_flow": "Requests enter the model and approved results return to the operating system.",
        "integration_points": ["Operating system"],
        "technical_area": ["AI and Machine Learning"],
        "use_case_category": ["Document Processing"],
        "business_outcome": "The deployed workflow reduced review time by 40% and improved service speed.",
        "outcome_category": ["Productivity Improvement"],
        "metrics": ["40% reduction in review time"],
        "architecture_clues": ["Production deployment across global operations"],
        "source_url": "https://example.com/story",
        "published_date": "2025-03-06",
        "published_date_source": "page",
        "confidence_score": 0,
        "maturity_score": 0,
        "evidence_quotes": ["We reduced review time by 40%.", "The workflow is live globally."],
    }


class ScoringTests(unittest.TestCase):
    def test_single_source_record_earns_source_transparency(self) -> None:
        record = normalize_record(record_fixture(), 0)
        scored = score_record(record)

        self.assertGreater(scored["confidence_score"], 0.5)
        self.assertLess(scored["confidence_score"], 1.0)
        transparency = next(
            item for item in scored["confidence_breakdown"] if item["criterion"] == "Source transparency"
        )
        self.assertGreaterEqual(transparency["score"], 8)

    def test_missing_metrics_lowers_value_and_maturity(self) -> None:
        strong = score_record(normalize_record(record_fixture(), 0))
        weak_record = record_fixture()
        weak_record["metrics"] = []
        weak_record["business_outcome"] = "The company reported improved efficiency."
        weak = score_record(normalize_record(weak_record, 0))

        self.assertLess(weak["value_score"], strong["value_score"])
        self.assertLess(weak["maturity_score"], strong["maturity_score"])

    def test_second_source_is_not_required_for_confidence(self) -> None:
        record = normalize_record(record_fixture(), 0)
        single_source = score_record(record)
        record["source_references"].append(
            {
                "id": "customer-release",
                "title": "Example Co deployment release",
                "publisher": "Example Co",
                "url": "https://example.co/news/deployment",
                "source_type": "Customer press release",
                "authority": "First-party",
                "published_date": "2025-03-06",
                "published_date_source": "page",
                "retrieved_at": "2026-10-13T00:00:00+00:00",
                "supports": ["business_outcome", "metrics"],
            }
        )
        scored = score_record(record)
        transparency = next(
            item for item in scored["confidence_breakdown"] if item["criterion"] == "Source transparency"
        )

        self.assertGreaterEqual(transparency["score"], 8)
        self.assertGreaterEqual(scored["confidence_score"], single_source["confidence_score"])
        self.assertEqual(scored["maturity_score"], 6)


if __name__ == "__main__":
    unittest.main()
