"""Fetch client built on stdlib with profile and fallback recovery.

Single-threaded and per-host rate limited. Designed for sitemap + case-study
page fetching where we want one Python pipeline path to try every configured
recovery strategy before giving up.
"""

from __future__ import annotations

import gzip
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
BOT_CHALLENGE_STATUSES = {401, 403, 429, 451, 503}
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


def reader_url(url: str) -> str:
    return f"https://r.jina.ai/http://{url}"


def wayback_url(url: str) -> str:
    return f"https://web.archive.org/web/{time.gmtime().tm_year}/{url}"


def looks_blocked(result: "FetchResult") -> bool:
    if result.status in BOT_CHALLENGE_STATUSES:
        return True
    head = result.body[:4000].decode("utf-8", errors="ignore").lower()
    return any(marker in head for marker in BOT_CHALLENGE_MARKERS)


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


class FetchClient:
    def __init__(
        self,
        user_agent: str,
        per_host_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.user_agent = user_agent
        self.per_host_delay = per_host_delay_seconds
        self.timeout = timeout_seconds
        self.cache_dir = cache_dir
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

    def fetch_once(self, attempt: FetchAttempt) -> FetchResult:
        url = attempt.url
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            raise ValueError(f"invalid url: {url}")

        user_agent, headers = self._profile_request_headers(attempt.profile)

        self._wait_for_host(parts.netloc)

        request_headers = {"User-Agent": user_agent, **headers}
        request = Request(url, headers=request_headers)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                content_encoding = (response.headers.get("Content-Encoding") or "").lower()
                final_url = response.geturl()
        except HTTPError as exc:
            raw = exc.read()
            status = exc.code
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            content_encoding = (exc.headers.get("Content-Encoding") or "").lower() if exc.headers else ""
            final_url = exc.geturl()

        if content_encoding == "gzip" or url.endswith(".gz"):
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass

        return FetchResult(
            url=url,
            status=status,
            body=raw,
            content_type=content_type,
            sha256=hashlib.sha256(raw).hexdigest(),
            from_cache=False,
            final_url=final_url,
            retrieval_source=attempt.source,
            profile=attempt.profile,
        )

    def _fallback_plan(self, url: str) -> list[FetchAttempt]:
        plan: list[FetchAttempt] = []
        entry = _lookup_host_strategy(url)
        if entry:
            kind = entry.get("kind")
            strategy = entry.get("strategy")
            if kind == "origin" and isinstance(strategy, str) and strategy in PROFILE_HEADERS:
                plan.append(FetchAttempt(url, strategy, "origin"))
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
            try:
                result = self.fetch_once(attempt)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
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


def probe_attempts(url: str) -> list[FetchAttempt]:
    return [
        *(FetchAttempt(url, profile, "origin") for profile in PROFILE_ORDER),
        FetchAttempt(reader_url(url), "default", "reader"),
        FetchAttempt(wayback_url(url), "default", "wayback"),
    ]
