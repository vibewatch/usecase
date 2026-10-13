from __future__ import annotations

import gzip
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from pipeline.usecase_intel.browser_fetch import BrowserFetchResult, _is_public_address
from pipeline.usecase_intel.fetch_client import (
    FetchAttempt,
    FetchClient,
    FetchResult,
    _decompress_gzip_limited,
    _read_limited,
    _retry_after_seconds,
    looks_blocked,
    probe_attempts,
    reader_url,
    wayback_url,
)


class _Stream:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.body)
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def result(status: int, body: bytes = b"", retry_after: float | None = None) -> FetchResult:
    return FetchResult(
        url="https://example.com/story",
        status=status,
        body=body,
        content_type="text/html",
        sha256="hash",
        from_cache=False,
        retry_after_seconds=retry_after,
    )


class FetchClientTests(unittest.TestCase):
    def test_reader_and_wayback_urls_use_valid_raw_targets(self) -> None:
        source = "https://example.com/story"

        self.assertEqual(reader_url(source), "https://r.jina.ai/https://example.com/story")
        self.assertRegex(wayback_url(source), r"^https://web\.archive\.org/web/\d{4}id_/https://example\.com/story$")

    def test_browser_render_is_between_header_profiles_and_external_fallbacks(self) -> None:
        attempts = probe_attempts("https://example.com/story")
        sources = [attempt.source for attempt in attempts]

        self.assertEqual(sources[:6], ["origin"] * 6)
        self.assertEqual(sources[6:], ["browser", "reader", "wayback"])

    def test_browser_fetch_preserves_retrieval_provenance(self) -> None:
        client = FetchClient(user_agent="test", per_host_delay_seconds=0)
        rendered = BrowserFetchResult(
            status=200,
            body=b"<article>Rendered</article>",
            final_url="https://example.com/rendered",
        )

        with patch(
            "pipeline.usecase_intel.fetch_client.BrowserFetcher.fetch",
            return_value=rendered,
        ):
            fetched = client.fetch_once(
                FetchAttempt("https://example.com/story", "desktop-chrome", "browser")
            )

        self.assertEqual(fetched.retrieval_source, "browser")
        self.assertEqual(fetched.final_url, rendered.final_url)
        self.assertEqual(fetched.body, rendered.body)

    def test_browser_route_rejects_private_addresses(self) -> None:
        self.assertFalse(_is_public_address("127.0.0.1"))
        self.assertFalse(_is_public_address("169.254.169.254"))
        self.assertTrue(_is_public_address("93.184.216.34"))

    def test_real_article_is_not_rejected_for_challenge_words(self) -> None:
        page = result(200, b"<article><p>This guide explains why access denied errors occur.</p></article>")

        self.assertFalse(looks_blocked(page))
        self.assertTrue(looks_blocked(result(200, b"<html><title>Access denied</title></html>")))
        self.assertTrue(looks_blocked(result(406, b"")))

    def test_client_rendered_shell_escalates_to_browser(self) -> None:
        shell = (
            b"<html><body><div id='root'>Loading</div>"
            b"<script src='runtime.js'></script>"
            b"<script src='vendor.js'></script>"
            b"<script src='app.js'></script></body></html>"
        )

        self.assertTrue(looks_blocked(result(200, shell)))

    def test_response_reader_enforces_byte_limit(self) -> None:
        self.assertEqual(_read_limited(_Stream(b"1234"), 4), b"1234")

        with self.assertRaisesRegex(ValueError, "max_response_bytes=4"):
            _read_limited(_Stream(b"12345"), 4)

    def test_gzip_reader_enforces_decompressed_limit(self) -> None:
        compressed = gzip.compress(b"x" * 20)

        with self.assertRaisesRegex(ValueError, "max_response_bytes=10"):
            _decompress_gzip_limited(compressed, 10)

    def test_retry_after_supports_seconds_and_http_dates(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)

        self.assertEqual(_retry_after_seconds("2.5", now=now), 2.5)
        self.assertEqual(_retry_after_seconds("Wed, 01 Jan 2025 00:00:10 GMT", now=now), 10.0)
        self.assertIsNone(_retry_after_seconds("not-a-date", now=now))

    def test_rate_limit_retries_same_strategy_before_fallback(self) -> None:
        client = FetchClient(
            user_agent="test",
            per_host_delay_seconds=0,
            rate_limit_retries=1,
            max_retry_delay_seconds=5,
        )
        attempt = FetchAttempt("https://example.com/story")
        responses = [result(429, retry_after=0.25), result(200, body=b"<article>ok</article>")]

        with (
            patch.object(client, "_fallback_plan", return_value=[attempt]),
            patch.object(client, "fetch_once", side_effect=responses) as fetch_once,
            patch("pipeline.usecase_intel.fetch_client.time.sleep") as sleep,
        ):
            fetched = client.fetch(attempt.url, use_cache=False)

        self.assertEqual(fetched.status, 200)
        self.assertEqual(fetch_once.call_count, 2)
        sleep.assert_called_once_with(0.25)


if __name__ == "__main__":
    unittest.main()
