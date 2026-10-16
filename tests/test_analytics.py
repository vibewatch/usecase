from __future__ import annotations

import unittest

from pipeline.usecase_intel.analytics import build_analytics


class AnalyticsTests(unittest.TestCase):
    def test_build_analytics_produces_granular_dimensions(self) -> None:
        sample_records = [
            {
                "id": "msft-contoso",
                "slug": "msft-contoso",
                "vendor": "Microsoft",
                "customer_name": "Contoso Bank",
                "industry": "Financial Services",
                "region": "United States",
                "company_size": "Enterprise",
                "products_used": ["Azure OpenAI Service", "Azure AI Search", "Power BI"],
                "solution_components": [
                    {"name": "Azure OpenAI Service", "role": "LLM inference", "layer": "Compute"},
                    {"name": "Azure AI Search", "role": "Vector index", "layer": "Storage"},
                    {"name": "Power BI", "role": "Executive reporting", "layer": "Serving"},
                ],
                "data_flow": "Ingest -> Azure AI Search -> Azure OpenAI Service -> Power BI",
                "integration_points": ["Salesforce CRM", "SharePoint"],
                "technical_area": ["Generative AI"],
                "use_case_category": ["Knowledge Management", "Chatbot and Virtual Assistant"],
                "outcome_category": ["Productivity Improvement", "Cost Reduction"],
                "metrics": [
                    "Reduced cycle time by 65% across 10,000 analysts",
                    "3x faster resolution of complex compliance queries",
                ],
                "value_score": 92,
                "confidence_score": 0.91,
            },
            {
                "id": "msft-fabrikam",
                "slug": "msft-fabrikam",
                "vendor": "Microsoft",
                "customer_name": "Fabrikam Health",
                "industry": "Healthcare and Life Sciences",
                "region": "Germany",
                "company_size": "Enterprise",
                "products_used": ["Azure OpenAI Service", "Azure AI Search"],
                "solution_components": [
                    {"name": "Azure OpenAI Service", "role": "Clinical summarization", "layer": "Compute"},
                    {"name": "Azure AI Search", "role": "Clinical document retrieval", "layer": "Storage"},
                ],
                "data_flow": "EHR -> Azure AI Search -> Azure OpenAI Service",
                "integration_points": ["Epic EHR"],
                "technical_area": ["Generative AI"],
                "use_case_category": ["Knowledge Management"],
                "outcome_category": ["Cost Reduction"],
                "metrics": ["Saved 45% in documentation costs"],
                "value_score": 88,
                "confidence_score": 0.89,
            },
        ]
        taxonomy = {
            "component_layers": ["Ingest", "Compute", "Storage", "Serving", "Orchestration", "Governance"]
        }

        payload = build_analytics(sample_records, taxonomy, sync_logos=False)
        self.assertEqual(payload["summary"]["total_records"], 2)
        self.assertEqual(payload["summary"]["total_unique_products"], 3)
        self.assertEqual(payload["summary"]["total_solution_components"], 5)

        layers = {item["layer"]: item for item in payload["architecture_layers"]}
        self.assertEqual(layers["Compute"]["component_count"], 2)
        self.assertEqual(layers["Storage"]["component_count"], 2)
        self.assertEqual(layers["Serving"]["component_count"], 1)

        pairs = payload["product_ecosystem"]["co_occurring_pairs"]
        self.assertTrue(any(p["pair"] == "Azure AI Search + Azure OpenAI Service" and p["count"] == 2 for p in pairs))

        msft_dossier = payload["vendor_dossiers"]["Microsoft"]
        self.assertEqual(msft_dossier["count"], 2)
        self.assertEqual(msft_dossier["top_products"][0]["label"], "Azure AI Search")


if __name__ == "__main__":
    unittest.main()
