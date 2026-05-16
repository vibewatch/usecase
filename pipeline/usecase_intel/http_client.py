"""Polite HTTP client built on stdlib.

Single-threaded, per-host rate limited, robots.txt aware, optional disk cache by content hash.
Designed for sitemap + case-study page fetching where politeness > throughput.
"""

from __future__ import annotations

import gzip
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    content_type: str
    sha256: str
    from_cache: bool


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        per_host_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        cache_dir: Optional[Path] = None,
        respect_robots: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.per_host_delay = per_host_delay_seconds
        self.timeout = timeout_seconds
        self.cache_dir = cache_dir
        self.respect_robots = respect_robots
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
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

    def _get_robots(self, scheme: str, host: str) -> RobotFileParser:
        if host in self._robots:
            return self._robots[host]
        rp = RobotFileParser()
        rp.set_url(f"{scheme}://{host}/robots.txt")
        try:
            rp.read()
        except (HTTPError, URLError, ValueError, TimeoutError):
            # Treat missing/unreachable robots.txt as permissive; log via raise upstream if you want strict mode.
            pass
        self._robots[host] = rp
        return rp

    def can_fetch(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            return False
        rp = self._get_robots(parts.scheme, parts.netloc)
        return rp.can_fetch(self.user_agent, url)

    def _cache_path(self, url: str) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.bin"

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
            )

        if self.respect_robots and not self.can_fetch(url):
            raise PermissionError(f"robots.txt forbids {url}")

        self._wait_for_host(parts.netloc)

        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
                "Accept-Encoding": "gzip",
            },
        )

        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()

        if content_encoding == "gzip" or url.endswith(".gz"):
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass

        if cache_path is not None:
            cache_path.write_bytes(raw)

        return FetchResult(
            url=url,
            status=status,
            body=raw,
            content_type=content_type,
            sha256=hashlib.sha256(raw).hexdigest(),
            from_cache=False,
        )
