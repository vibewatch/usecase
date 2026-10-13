"""Optional headless-Chrome renderer for JavaScript-dependent source pages."""

from __future__ import annotations

import atexit
import ipaddress
import os
import shutil
import socket
import time
from dataclasses import dataclass
from typing import Any, Optional

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
CHALLENGE_MARKERS = ("just a moment", "cf-mitigated", "checking your browser")
MAX_CHALLENGE_WAIT_SECONDS = 15.0
POLL_INTERVAL_MILLISECONDS = 500
POST_LOAD_WAIT_MILLISECONDS = 10_000
DESKTOP_CHROME_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class BrowserFetchResult:
    status: int
    body: bytes
    final_url: str


def _chrome_executable() -> Optional[str]:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if configured:
        return configured
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _looks_challenged(html: str) -> bool:
    lower = html.lower()
    return any(marker in lower for marker in CHALLENGE_MARKERS)


def _is_public_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


class BrowserFetcher:
    """Lazily launch one browser and create an isolated context per URL."""

    def __init__(self, *, timeout_seconds: float, max_response_bytes: int) -> None:
        self.timeout_milliseconds = max(1, int(timeout_seconds * 1000))
        self.max_response_bytes = max_response_bytes
        self._playwright: Any = None
        self._browser: Any = None
        self._safe_hosts: set[str] = set()

    def _route_is_safe(self, raw_url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in self._safe_hosts:
            return True
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            }
        except OSError:
            return False
        if not addresses or not all(_is_public_address(address) for address in addresses):
            return False
        self._safe_hosts.add(host)
        return True

    def _ensure_browser(self) -> Any:
        if self._browser is not None:
            return self._browser
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "headless browser fallback requires the playwright Python package"
            ) from exc

        self._playwright = sync_playwright().start()
        executable_path = _chrome_executable()
        launch_options: dict[str, Any] = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        if executable_path:
            launch_options["executable_path"] = executable_path
        try:
            self._browser = self._playwright.chromium.launch(**launch_options)
        except Exception:
            self.close()
            raise
        atexit.register(self.close)
        return self._browser

    def fetch(self, url: str) -> BrowserFetchResult:
        browser = self._ensure_browser()
        context = browser.new_context(
            user_agent=DESKTOP_CHROME_USER_AGENT,
            locale="en-US",
            viewport={"width": 1365, "height": 900},
        )

        def route_request(route: Any) -> None:
            if (
                route.request.resource_type in BLOCKED_RESOURCE_TYPES
                or not self._route_is_safe(route.request.url)
            ):
                route.abort()
            else:
                route.continue_()

        try:
            context.route("**/*", route_request)
            page = context.new_page()
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_milliseconds,
            )
            status = response.status if response is not None else 0
            page.wait_for_timeout(POST_LOAD_WAIT_MILLISECONDS)
            html = page.content()
            deadline = time.monotonic() + min(
                self.timeout_milliseconds / 1000,
                MAX_CHALLENGE_WAIT_SECONDS,
            )
            while _looks_challenged(html) and time.monotonic() < deadline:
                page.wait_for_timeout(POLL_INTERVAL_MILLISECONDS)
                html = page.content()

            body = html.encode("utf-8")
            if len(body) > self.max_response_bytes:
                raise ValueError(
                    f"rendered response exceeds max_response_bytes={self.max_response_bytes}"
                )
            return BrowserFetchResult(status=status, body=body, final_url=page.url)
        finally:
            context.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
