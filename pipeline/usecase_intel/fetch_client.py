"""Fetch client built on stdlib with profile and fallback recovery.

Single-threaded and per-host rate limited. Designed for sitemap + case-study
page fetching where we want one Python pipeline path to try every configured
recovery strategy before giving up.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import BinaryIO, Optional
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .browser_fetch import BrowserFetcher
from .settings import HOST_STRATEGIES_PATH
from .utils import load_json

PROFILE_HEADERS: dict[str, dict[str, object]] = {
    "bingbot": {
        "user_agent": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
    "googlebot": {
        "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
    "desktop-chrome": {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        },
    },
    "desktop-firefox": {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
        },
    },
    "desktop-safari": {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
    "mobile-safari": {
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
}

PROFILE_ORDER = ["bingbot", "googlebot", "desktop-chrome", "desktop-firefox", "desktop-safari", "mobile-safari"]
BOT_CHALLENGE_STATUSES = {401, 403, 406, 429, 451, 503}
BOT_CHALLENGE_MARKERS = [
    "datadome",
    "please enable js",
    "cf-browser-verification",
    "just a moment...",
    "access denied",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "enable cookies",
    "bot detection",
    "captcha",
    "perimeterx",
    "px-captcha",
    "incapsula",
    "imperva",
]

MULTI_LEVEL_TLDS = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "plc.uk",
    "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp",
    "com.au", "org.au", "gov.au", "edu.au", "net.au",
    "co.in", "org.in", "gov.in", "ac.in", "net.in",
    "com.cn", "org.cn", "gov.cn", "edu.cn", "net.cn",
    "com.hk", "org.hk", "gov.hk",
    "com.sg", "org.sg",
    "com.br", "gov.br",
    "co.kr", "or.kr", "go.kr",
    "co.nz", "govt.nz", "org.nz",
}

_HOST_STRATEGIES_CACHE: Optional[dict[str, dict]] = None
DEFAULT_MAX_RESPONSE_BYTES = 20_000_000
READ_CHUNK_BYTES = 64 * 1024


def reader_url(url: str) -> str:
    return f"https://r.jina.ai/{url}"


def wayback_url(url: str) -> str:
    return f"https://web.archive.org/web/{time.gmtime().tm_year}id_/{url}"


def looks_blocked(result: "FetchResult") -> bool:
    if result.status in BOT_CHALLENGE_STATUSES:
        return True
    sample = result.body[:1_000_000].decode("utf-8", errors="ignore").lower()
    has_article_markers = (
        "<article" in sample
        or sample.count("<p") >= 3
        or "application/ld+json" in sample
        or 'property="og:title"' in sample
    )
    if not has_article_markers and any(marker in sample for marker in BOT_CHALLENGE_MARKERS):
        return True
    visible = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", sample, flags=re.DOTALL)
    visible = re.sub(r"<[^>]+>", " ", visible)
    visible = re.sub(r"&[a-z0-9#]+;", " ", visible)
    visible = re.sub(r"\s+", " ", visible).strip()
    has_article_body = "<article" in sample or sample.count("<p") >= 3
    return not has_article_body and sample.count("<script") >= 3 and len(visible) < 250


def _retry_after_seconds(value: Optional[str], *, now: Optional[datetime] = None) -> Optional[float]:
    if not value:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return max(0.0, (parsed - current).total_seconds())


def _read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(min(READ_CHUNK_BYTES, max_bytes - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"response exceeds max_response_bytes={max_bytes}")
        chunks.append(chunk)


def _decompress_gzip_limited(raw: bytes, max_bytes: int) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        return _read_limited(stream, max_bytes)


def _registrable_domain(host: str) -> Optional[str]:
    parts = [part for part in host.lower().split(".") if part]
    if len(parts) < 2:
        return None
    last2 = ".".join(parts[-2:])
    if len(parts) >= 3 and last2 in MULTI_LEVEL_TLDS:
        return ".".join(parts[-3:])
    return last2


def _load_host_strategies(path: Path = HOST_STRATEGIES_PATH) -> dict[str, dict]:
    global _HOST_STRATEGIES_CACHE
    if _HOST_STRATEGIES_CACHE is not None:
        return _HOST_STRATEGIES_CACHE
    value = load_json(path, {})
    _HOST_STRATEGIES_CACHE = value if isinstance(value, dict) else {}
    return _HOST_STRATEGIES_CACHE


def _lookup_host_strategy(url: str) -> Optional[dict]:
    parts = urlparse(url)
    host = parts.netloc.lower()
    if not host:
        return None
    strategies = _load_host_strategies()
    keys = [host]
    if host.startswith("www."):
        keys.append(host[4:])
    else:
        keys.append(f"www.{host}")
    registrable = _registrable_domain(host)
    if registrable and registrable not in keys:
        keys.append(registrable)
    for key in keys:
        if key in strategies:
            entry = dict(strategies[key])
            entry["_matched_key"] = key
            return entry
    return None


@dataclass
class FetchAttempt:
    url: str
    profile: str = "default"
    source: str = "origin"

    @property
    def strategy(self) -> str:
        return self.profile if self.source == "origin" else self.source


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    content_type: str
    sha256: str
    from_cache: bool
    final_url: str = ""
    retrieval_source: str = "origin"
    profile: str = "default"
    retry_after_seconds: Optional[float] = None


class FetchClient:
    def __init__(
        self,
        user_agent: str,
        per_host_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        cache_dir: Optional[Path] = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        rate_limit_retries: int = 2,
        max_retry_delay_seconds: float = 60.0,
        enable_browser: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.per_host_delay = per_host_delay_seconds
        self.timeout = timeout_seconds
        self.cache_dir = cache_dir
        self.max_response_bytes = max_response_bytes
        self.rate_limit_retries = rate_limit_retries
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self.enable_browser = enable_browser
        self._browser_fetcher: Optional[BrowserFetcher] = None
        self._last_request: dict[str, float] = {}
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _wait_for_host(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_request.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self.per_host_delay:
                time.sleep(self.per_host_delay - elapsed)
        self._last_request[host] = time.monotonic()

    def _cache_path(self, url: str) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.bin"

    def _profile_request_headers(self, profile: str) -> tuple[str, dict[str, str]]:
        if profile == "default":
            return self.user_agent, {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
                "Accept-Encoding": "gzip",
            }
        data = PROFILE_HEADERS.get(profile) or PROFILE_HEADERS["bingbot"]
        user_agent = str(data["user_agent"])
        headers = dict(data.get("headers", {}))
        headers["Accept-Encoding"] = "gzip"
        return user_agent, {str(key): str(value) for key, value in headers.items()}

    def _request_once(
        self,
        url: str,
        *,
        profile: str = "default",
        source: str = "origin",
        data: Optional[bytes] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> FetchResult:
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            raise ValueError(f"invalid url: {url}")

        user_agent, headers = self._profile_request_headers(profile)
        self._wait_for_host(parts.netloc)

        request_headers = {"User-Agent": user_agent, **headers, **(extra_headers or {})}
        request = Request(url, data=data, headers=request_headers)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                declared_length = response.headers.get("Content-Length")
                if declared_length:
                    try:
                        declared_bytes = int(declared_length)
                    except ValueError:
                        declared_bytes = 0
                    if declared_bytes > self.max_response_bytes:
                        raise ValueError(
                            f"response Content-Length={declared_length} exceeds "
                            f"max_response_bytes={self.max_response_bytes}"
                        )
                raw = _read_limited(response, self.max_response_bytes)
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                content_encoding = (response.headers.get("Content-Encoding") or "").lower()
                retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                final_url = response.geturl()
        except HTTPError as exc:
            raw = _read_limited(exc, self.max_response_bytes)
            status = exc.code
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            content_encoding = (exc.headers.get("Content-Encoding") or "").lower() if exc.headers else ""
            retry_after = _retry_after_seconds(exc.headers.get("Retry-After")) if exc.headers else None
            final_url = exc.geturl()

        if content_encoding == "gzip" or url.endswith(".gz"):
            try:
                raw = _decompress_gzip_limited(raw, self.max_response_bytes)
            except (EOFError, OSError):
                pass

        return FetchResult(
            url=url,
            status=status,
            body=raw,
            content_type=content_type,
            sha256=hashlib.sha256(raw).hexdigest(),
            from_cache=False,
            final_url=final_url,
            retrieval_source=source,
            profile=profile,
            retry_after_seconds=retry_after,
        )

    def fetch_once(self, attempt: FetchAttempt) -> FetchResult:
        url = attempt.url
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            raise ValueError(f"invalid url: {url}")

        if attempt.source == "browser":
            if not self.enable_browser:
                raise RuntimeError("headless browser fallback is disabled")
            if self._browser_fetcher is None:
                self._browser_fetcher = BrowserFetcher(
                    timeout_seconds=self.timeout,
                    max_response_bytes=self.max_response_bytes,
                )
            rendered = self._browser_fetcher.fetch(url)
            return FetchResult(
                url=url,
                status=rendered.status,
                body=rendered.body,
                content_type="text/html; charset=utf-8",
                sha256=hashlib.sha256(rendered.body).hexdigest(),
                from_cache=False,
                final_url=rendered.final_url,
                retrieval_source="browser",
                profile=attempt.profile,
            )

        return self._request_once(
            url,
            profile=attempt.profile,
            source=attempt.source,
        )

    def post_json(self, url: str, payload: object) -> FetchResult:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        result: Optional[FetchResult] = None
        for retry in range(self.rate_limit_retries + 1):
            result = self._request_once(
                url,
                data=body,
                extra_headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if result.status != 429 or retry >= self.rate_limit_retries:
                break
            delay = result.retry_after_seconds
            if delay is None:
                delay = min(self.max_retry_delay_seconds, 2.0**retry)
            time.sleep(min(self.max_retry_delay_seconds, delay))
        if result is None:  # pragma: no cover - loop always runs at least once
            raise RuntimeError(f"failed to POST JSON to {url}")
        if not 200 <= result.status < 400:
            raise HTTPError(url, result.status, f"HTTP status {result.status}", None, None)
        return result

    def _fallback_plan(self, url: str) -> list[FetchAttempt]:
        plan: list[FetchAttempt] = []
        entry = _lookup_host_strategy(url)
        if entry:
            kind = entry.get("kind")
            strategy = entry.get("strategy")
            if kind == "origin" and isinstance(strategy, str) and strategy in PROFILE_HEADERS:
                plan.append(FetchAttempt(url, strategy, "origin"))
            elif kind == "browser":
                plan.append(FetchAttempt(url, "desktop-chrome", "browser"))
            elif kind == "reader":
                plan.append(FetchAttempt(reader_url(url), "default", "reader"))
            elif kind == "wayback":
                plan.append(FetchAttempt(wayback_url(url), "default", "wayback"))

        if not plan:
            plan.append(FetchAttempt(url))

        for profile in PROFILE_ORDER:
            attempt = FetchAttempt(url, profile, "origin")
            if attempt not in plan:
                plan.append(attempt)
        browser_attempt = FetchAttempt(url, "desktop-chrome", "browser")
        if self.enable_browser and browser_attempt not in plan:
            plan.append(browser_attempt)
        for fallback_url, source in [(reader_url(url), "reader"), (wayback_url(url), "wayback")]:
            attempt = FetchAttempt(fallback_url, "default", source)
            if attempt not in plan:
                plan.append(attempt)

        return plan

    def fetch(self, url: str, *, use_cache: bool = True) -> FetchResult:
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            raise ValueError(f"invalid url: {url}")

        cache_path = self._cache_path(url) if use_cache else None
        if cache_path is not None and cache_path.exists():
            body = cache_path.read_bytes()
            return FetchResult(
                url=url,
                status=200,
                body=body,
                content_type="application/octet-stream",
                sha256=hashlib.sha256(body).hexdigest(),
                from_cache=True,
                final_url=url,
            )

        last_result: Optional[FetchResult] = None
        last_error: Optional[Exception] = None
        for attempt in self._fallback_plan(url):
            result: Optional[FetchResult] = None
            for retry in range(self.rate_limit_retries + 1):
                try:
                    result = self.fetch_once(attempt)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    result = None
                    break
                if result.status != 429 or retry >= self.rate_limit_retries:
                    break
                delay = result.retry_after_seconds
                if delay is None:
                    delay = min(self.max_retry_delay_seconds, 2.0**retry)
                time.sleep(min(self.max_retry_delay_seconds, delay))
            else:  # pragma: no cover - loop always exits through break
                continue

            if result is None:
                continue
            last_result = result
            if 200 <= result.status < 400 and not looks_blocked(result):
                if cache_path is not None and attempt.source == "origin":
                    cache_path.write_bytes(result.body)
                return result
            if result.status not in BOT_CHALLENGE_STATUSES and result.status >= 400:
                break

        if last_result is not None:
            if looks_blocked(last_result):
                raise PermissionError(f"blocked response while fetching {url} via {last_result.retrieval_source}/{last_result.profile}: status {last_result.status}")
            raise HTTPError(url, last_result.status, f"HTTP status {last_result.status}", None, None)

        if last_error is not None:
            raise last_error

        raise RuntimeError(f"failed to fetch {url}")

    def close(self) -> None:
        if self._browser_fetcher is not None:
            self._browser_fetcher.close()
            self._browser_fetcher = None


def probe_attempts(url: str) -> list[FetchAttempt]:
    return [
        *(FetchAttempt(url, profile, "origin") for profile in PROFILE_ORDER),
        FetchAttempt(url, "desktop-chrome", "browser"),
        FetchAttempt(reader_url(url), "default", "reader"),
        FetchAttempt(wayback_url(url), "default", "wayback"),
    ]
