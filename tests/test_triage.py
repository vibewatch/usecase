from __future__ import annotations

import unittest

from pipeline.usecase_intel.settings import TRIAGE_CONFIG_PATH
from pipeline.usecase_intel.triage import Criteria, evaluate_text


def qualifying_text(words: int) -> str:
    sentence = "The customer deployed artificial intelligence and machine learning in production with an integrated workflow. "
    return (sentence * ((words // 14) + 1)).strip()


class TriageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = Criteria.load(TRIAGE_CONFIG_PATH)

    def test_vendor_min_words_override_keeps_short_official_story(self) -> None:
        result = evaluate_text(
            title="Customer AI deployment",
            text=qualifying_text(200),
            raw_html="",
            lastmod=None,
            criteria=self.criteria,
            story_cues=None,
            vendor_options={"min_words": 180},
        )

        self.assertEqual(result["decision"], "keep")
        self.assertFalse(any(reason.startswith("thin_") for reason in result["reasons"]))

    def test_wayback_capture_does_not_trigger_publication_cutoff(self) -> None:
        result = evaluate_text(
            title="Customer AI deployment",
            text=qualifying_text(400),
            raw_html="",
            lastmod=None,
            criteria=self.criteria,
            story_cues=None,
            date_fallback=lambda: "2022-01-01",
        )

        self.assertEqual(result["decision"], "keep")
        self.assertEqual(result["published_source"], "wayback_first_capture")
        self.assertNotIn("published_before_2023-01-01", result["reasons"])


if __name__ == "__main__":
    unittest.main()
