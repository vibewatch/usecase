from __future__ import annotations

import json
import re
import unittest

from pipeline.usecase_intel.discover import _filter_urls, _walk_huawei_datahub
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


if __name__ == "__main__":
    unittest.main()
