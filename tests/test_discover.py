from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pipeline.usecase_intel.discover import (
    _filter_urls,
    _walk_aws_directory,
    _walk_huawei_datahub,
    _walk_sitemap,
    compact_discovery_state,
    discover,
    load_discovery_state,
)
from pipeline.usecase_intel.fetch_client import FetchResult


class _HuaweiClient:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def post_json(self, url: str, payload: object) -> FetchResult:
        self.payloads.append(dict(payload))
        page = int(dict(payload)["pageNumber"])
        records = [
            {
                "extendMap": {
                    "url": f"https://www.huaweicloud.com/cases/customer-{page}.html",
                    "companyName": f"Customer {page}",
                    "contentTime": "2025-11-12 00:00:00",
                }
            }
        ]
        body = json.dumps(
            {
                "status": "SUCCESS",
                "data": {
                    "totalRecords": 2,
                    "totalPages": 2,
                    "currentPage": page,
                    "pageSize": 1,
                    "records": records,
                },
            }
        ).encode()
        return FetchResult(
            url=url,
            status=200,
            body=body,
            content_type="application/json",
            sha256="hash",
            from_cache=False,
        )


class DiscoverTests(unittest.TestCase):
    def test_filter_urls_strips_tracking_query_and_fragment(self) -> None:
        urls = _filter_urls(
            ["https://example.com/customers/42?lang=en&pg=#cases"],
            include_patterns=[re.compile(r"^https://example\.com/customers/\d+$")],
            exclude_patterns=[re.compile(r"\?"), re.compile(r"#")],
        )

        self.assertEqual(urls, ["https://example.com/customers/42"])

    def test_huawei_datahub_walks_pages_and_extracts_story_metadata(self) -> None:
        client = _HuaweiClient()
        api = {
            "url": "https://portal.huaweicloud.com/api",
            "pid": "catalog-id",
            "page_size": 1,
        }

        stories = _walk_huawei_datahub(
            client,
            api,
            include_patterns=[re.compile(r"^https://www\.huaweicloud\.com/cases/.+\.html$")],
            exclude_patterns=[],
        )

        self.assertEqual(
            stories,
            [
                ("https://www.huaweicloud.com/cases/customer-1.html", None, "Customer 1"),
                ("https://www.huaweicloud.com/cases/customer-2.html", None, "Customer 2"),
            ],
        )
        self.assertEqual([payload["pageNumber"] for payload in client.payloads], [1, 2])
        self.assertEqual(client.payloads[0]["filters"][0]["fieldValue"], "china")
        self.assertEqual(client.payloads[0]["filters"][1]["fieldValue"], "zh-cn")

    def test_sitemap_walk_counts_only_unseen_urls_and_prunes_stale_children(self) -> None:
        responses = {
            "https://example.com/sitemap_index.xml": (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                b"<sitemap><loc>https://example.com/stale.xml</loc><lastmod>2021-05-01</lastmod></sitemap>"
                b"<sitemap><loc>https://example.com/older.xml</loc><lastmod>2025-01-10</lastmod></sitemap>"
                b"<sitemap><loc>https://example.com/newest.xml</loc><lastmod>2026-11-10</lastmod></sitemap>"
                b"</sitemapindex>"
            ),
            "https://example.com/newest.xml": (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                b"<url><loc>https://example.com/customers/known-1</loc><lastmod>2026-11-10</lastmod></url>"
                b"<url><loc>https://example.com/customers/known-2</loc><lastmod>2026-11-09</lastmod></url>"
                b"<url><loc>https://example.com/customers/new-1</loc><lastmod>2026-11-08</lastmod></url>"
                b"</urlset>"
            ),
            "https://example.com/older.xml": (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                b"<url><loc>https://example.com/customers/old-2022</loc><lastmod>2022-12-01</lastmod></url>"
                b"<url><loc>https://example.com/customers/new-2</loc><lastmod>2025-01-10</lastmod></url>"
                b"</urlset>"
            ),
        }
        fetched_urls: list[str] = []

        class _SitemapClient:
            def fetch(self, url: str, **_kwargs: object) -> FetchResult:
                fetched_urls.append(url)
                body = responses[url]
                return FetchResult(
                    url=url,
                    status=200,
                    body=body,
                    content_type="application/xml",
                    sha256=hashlib.sha256(body).hexdigest(),
                    from_cache=False,
                )

        matched = _walk_sitemap(
            _SitemapClient(),  # type: ignore[arg-type]
            "https://example.com/sitemap_index.xml",
            include_patterns=[re.compile(r"^https://example\.com/customers/[^/]+$")],
            exclude_patterns=[],
            enough=2,
            existing={
                "https://example.com/customers/known-1",
                "https://example.com/customers/known-2",
            },
            since="2023-01-01",
        )

        self.assertNotIn("https://example.com/stale.xml", fetched_urls)
        self.assertEqual(
            fetched_urls,
            [
                "https://example.com/sitemap_index.xml",
                "https://example.com/newest.xml",
                "https://example.com/older.xml",
            ],
        )
        self.assertEqual(
            matched,
            [
                ("https://example.com/customers/new-1", "2026-11-08"),
                ("https://example.com/customers/new-2", "2025-01-10"),
            ],
        )

    def test_onboarding_backoff_304_short_circuit_and_wakeup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources_path = root / "sources.json"
            output_path = root / "discovered.jsonl"
            state_path = root / "discovery_state.jsonl"
            sitemap_url = "https://acme.example/sitemap.xml"

            sources_path.write_text(
                json.dumps(
                    {
                        "default_delay_seconds": 0.0,
                        "sources": [
                            {
                                "vendor": "AcmeAI",
                                "priority": "normal",
                                "backfill_limit": 2,
                                "sitemaps": [sitemap_url],
                                "index_pages": [],
                                "url_patterns": [r"^https://acme\.example/stories/[^/]+$"],
                                "exclude_patterns": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            v1_xml = (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                b"<url><loc>https://acme.example/stories/s1</loc><lastmod>2026-11-01</lastmod></url>"
                b"<url><loc>https://acme.example/stories/s2</loc><lastmod>2026-11-02</lastmod></url>"
                b"<url><loc>https://acme.example/stories/s3</loc><lastmod>2026-11-03</lastmod></url>"
                b"</urlset>"
            )
            v2_xml = v1_xml.replace(
                b"</urlset>",
                b"<url><loc>https://acme.example/stories/s4</loc><lastmod>2026-11-15</lastmod></url></urlset>",
            )

            def make_200(body: bytes, etag: str) -> FetchResult:
                return FetchResult(
                    url=sitemap_url,
                    status=200,
                    body=body,
                    content_type="application/xml",
                    sha256=hashlib.sha256(body).hexdigest(),
                    from_cache=False,
                    etag=etag,
                )

            t0 = datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)

            # Pass 1: new vendor enters onboarding (backfill_limit=2), truncates at 2 of 3 URLs.
            with patch("pipeline.usecase_intel.discover.FetchClient.fetch", return_value=make_200(v1_xml, '"e1"')):
                c1 = discover(
                    sources_path,
                    output_path,
                    limit_per_vendor=1,
                    state_path=state_path,
                    now=t0,
                )
            self.assertEqual(c1, {"AcmeAI": 2})
            vstates, epstates = load_discovery_state(state_path)
            self.assertFalse(vstates["AcmeAI"].backfill_complete)
            self.assertNotIn(("AcmeAI", sitemap_url), epstates)

            # Pass 2 (+1h): finishes remaining 1 URL (< backfill_limit), marks backfill_complete=True & saves ETag.
            t1 = t0 + timedelta(hours=1)
            with patch("pipeline.usecase_intel.discover.FetchClient.fetch", return_value=make_200(v1_xml, '"e1"')):
                c2 = discover(
                    sources_path,
                    output_path,
                    limit_per_vendor=1,
                    state_path=state_path,
                    now=t1,
                )
            self.assertEqual(c2, {"AcmeAI": 1})
            vstates, epstates = load_discovery_state(state_path)
            self.assertTrue(vstates["AcmeAI"].backfill_complete)
            self.assertEqual(epstates[("AcmeAI", sitemap_url)].etag, '"e1"')

            # Pass 3 (+12h): still on 1-day cooldown -> skipped without HTTP calls.
            with patch("pipeline.usecase_intel.discover.FetchClient.fetch") as mock_fetch:
                c3 = discover(sources_path, output_path, state_path=state_path, now=t1 + timedelta(hours=12))
            self.assertEqual(c3, {})
            mock_fetch.assert_not_called()

            # Pass 4 (+1d): due, server responds 304 Not Modified -> backs off to 2 days.
            t2 = t1 + timedelta(days=1, minutes=1)
            not_mod = FetchResult(
                url=sitemap_url,
                status=304,
                body=b"",
                content_type="",
                sha256="empty",
                from_cache=False,
                etag='"e1"',
            )
            with patch("pipeline.usecase_intel.discover.FetchClient.fetch", return_value=not_mod) as mock_fetch:
                c4 = discover(sources_path, output_path, state_path=state_path, now=t2)
            self.assertEqual(c4, {"AcmeAI": 0})
            self.assertEqual(mock_fetch.call_args.kwargs["if_none_match"], '"e1"')
            vstates, _ = load_discovery_state(state_path)
            self.assertEqual(vstates["AcmeAI"].consecutive_empty_runs, 1)
            self.assertEqual(
                vstates["AcmeAI"].next_check_at,
                (t2 + timedelta(days=2)).isoformat(timespec="seconds"),
            )

            # Pass 5 (+2d): new story published -> resets consecutive_empty_runs=0 and interval back to 1 day.
            t3 = t2 + timedelta(days=2, minutes=1)
            with patch("pipeline.usecase_intel.discover.FetchClient.fetch", return_value=make_200(v2_xml, '"e2"')):
                c5 = discover(sources_path, output_path, state_path=state_path, now=t3)
            self.assertEqual(c5, {"AcmeAI": 1})
            vstates, _ = load_discovery_state(state_path)
            self.assertEqual(vstates["AcmeAI"].consecutive_empty_runs, 0)
            self.assertEqual(
                vstates["AcmeAI"].next_check_at,
                (t3 + timedelta(days=1)).isoformat(timespec="seconds"),
            )

    def test_priority_queue_max_vendors_and_state_compaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources_path = root / "sources.json"
            output_path = root / "discovered.jsonl"
            state_path = root / "discovery_state.jsonl"
            now = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)

            sources_path.write_text(
                json.dumps(
                    {
                        "default_delay_seconds": 0.0,
                        "sources": [
                            {"vendor": "LowVendor", "priority": "low", "sitemaps": [], "index_pages": [], "url_patterns": []},
                            {"vendor": "DisabledVendor", "enabled": False, "priority": "high", "sitemaps": [], "index_pages": [], "url_patterns": []},
                            {"vendor": "HighVendor", "priority": "high", "sitemaps": [], "index_pages": [], "url_patterns": []},
                            {"vendor": "NewOnboardVendor", "priority": "low", "sitemaps": [], "index_pages": [], "url_patterns": []},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            due_ts = (now - timedelta(hours=2)).isoformat(timespec="seconds")
            state_path.write_text(
                "\n".join(
                    [
                        json.dumps({"kind": "vendor", "vendor": "LowVendor", "checked_at": "2026-11-01T00:00:00+00:00", "next_check_at": due_ts, "backfill_complete": True}),
                        json.dumps({"kind": "vendor", "vendor": "HighVendor", "checked_at": "2026-11-10T00:00:00+00:00", "next_check_at": due_ts, "backfill_complete": True}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            checked = list(
                discover(
                    sources_path,
                    output_path,
                    state_path=state_path,
                    max_vendors=2,
                    now=now,
                ).keys()
            )
            self.assertEqual(checked, ["NewOnboardVendor", "HighVendor"])

            compacted = compact_discovery_state(state_path)
            self.assertEqual(compacted, 3)

    def test_aws_directory_stops_on_consecutive_known_urls(self) -> None:
        pages = [
            {
                "items": [
                    {"item": {"additionalFields": {"headlineUrl": "https://aws.amazon.com/solutions/case-studies/known-1", "sortDate": "2026-11-10"}}},
                    {"item": {"additionalFields": {"headlineUrl": "https://aws.amazon.com/solutions/case-studies/known-2", "sortDate": "2026-11-09"}}},
                ]
            },
            {
                "items": [
                    {"item": {"additionalFields": {"headlineUrl": "https://aws.amazon.com/solutions/case-studies/should-not-fetch", "sortDate": "2026-11-08"}}},
                ]
            },
        ]
        calls = 0

        class _AwsClient:
            def fetch(self, url: str, **_kwargs: object) -> FetchResult:
                nonlocal calls
                body = json.dumps(pages[calls]).encode()
                calls += 1
                return FetchResult(url=url, status=200, body=body, content_type="application/json", sha256="h", from_cache=False)

        matched, truncated = _walk_aws_directory(
            _AwsClient(),  # type: ignore[arg-type]
            {"url": "https://aws.amazon.com/api/dirs/items/search", "directory_id": "customer-references", "page_size": 2},
            include_patterns=[re.compile(r"^https://aws\.amazon\.com/solutions/case-studies/[^/]+$")],
            exclude_patterns=[],
            existing={
                "https://aws.amazon.com/solutions/case-studies/known-1",
                "https://aws.amazon.com/solutions/case-studies/known-2",
            },
            stop_after_known=2,
        )

        self.assertEqual(matched, [])
        self.assertFalse(truncated)
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
