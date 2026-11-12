"""URL discovery from vendor sitemaps, APIs, and listing pages.

Reads `data/sources.json`, schedules due vendors by priority and historical yield,
walks sitemaps/APIs/index pages incrementally, and appends net-new URLs to
`data/discovered_urls.jsonl` while recording check & validator state in
`data/discovery_state.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from .fetch_client import FetchClient, FetchResult
from .settings import (
    DISCOVERED_URLS_PATH,
    DISCOVERY_STATE_PATH,
    HTTP_CACHE_DIR,
    SOURCES_PATH,
    TRIAGE_PATH,
    fetch_options,
)
from .utils import load_json, load_jsonl

# Characters left as-is when percent-encoding discovered links ("Fortal Studio" -> "Fortal%20Studio").
URL_SAFE = ":/?#[]@!$&'()*+,;=%~"

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# priority -> (min_interval_days, max_interval_days, queue_weight, steady_cap_ceiling)
PRIORITY_BOUNDS: dict[str, tuple[float, float, float, Optional[int]]] = {
    "high": (1.0, 3.0, 3.0, None),
    "normal": (1.0, 14.0, 2.0, None),
    "low": (3.0, 30.0, 1.0, 15),
}
DEFAULT_BACKFILL_LIMIT = 100
DEFAULT_MAX_VENDORS = 40
FULL_SWEEP_INTERVAL_DAYS = 30.0
API_CONSECUTIVE_KNOWN_STOP = 50
DISCOVERY_CACHE_MAX_AGE_SECONDS = 3600.0
NOISY_DECIDED_MIN = 50
NOISY_KEEP_RATE_MAX = 0.02


@dataclass
class VendorState:
    vendor: str
    checked_at: Optional[str] = None
    next_check_at: Optional[str] = None
    last_full_sweep_at: Optional[str] = None
    backfill_complete: bool = False
    consecutive_empty_runs: int = 0
    last_new_urls: int = 0

    def to_row(self) -> dict[str, Any]:
        return {
            "kind": "vendor",
            "vendor": self.vendor,
            "checked_at": self.checked_at,
            "next_check_at": self.next_check_at,
            "last_full_sweep_at": self.last_full_sweep_at,
            "backfill_complete": self.backfill_complete,
            "consecutive_empty_runs": self.consecutive_empty_runs,
            "last_new_urls": self.last_new_urls,
        }


@dataclass
class EndpointState:
    vendor: str
    url: str
    checked_at: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    sha256: Optional[str] = None
    sitemap_lastmod: Optional[str] = None

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "kind": "endpoint",
            "vendor": self.vendor,
            "url": self.url,
            "checked_at": self.checked_at,
        }
        if self.etag:
            row["etag"] = self.etag
        if self.last_modified:
            row["last_modified"] = self.last_modified
        if self.sha256:
            row["sha256"] = self.sha256
        if self.sitemap_lastmod:
            row["sitemap_lastmod"] = self.sitemap_lastmod
        return row


@dataclass
class VendorYield:
    discovered: int = 0
    decided: int = 0
    kept: int = 0
    last_batch_all_dropped: bool = False

    @property
    def keep_rate(self) -> float:
        if self.decided == 0:
            return 0.5
        return self.kept / self.decided

    @property
    def is_noisy(self) -> bool:
        return self.decided >= NOISY_DECIDED_MIN and (self.kept / self.decided) < NOISY_KEEP_RATE_MAX


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_discovery_state(
    path: Optional[Path],
) -> tuple[dict[str, VendorState], dict[tuple[str, str], EndpointState]]:
    vendors: dict[str, VendorState] = {}
    endpoints: dict[tuple[str, str], EndpointState] = {}
    if path is None or not path.exists():
        return vendors, endpoints

    for row in load_jsonl(path):
        kind = row.get("kind")
        vendor = row.get("vendor")
        checked_at = str(row.get("checked_at") or "")
        if not isinstance(vendor, str) or not vendor:
            continue
        if kind == "vendor":
            prev = vendors.get(vendor)
            if prev and (prev.checked_at or "") > checked_at:
                continue
            vendors[vendor] = VendorState(
                vendor=vendor,
                checked_at=checked_at or None,
                next_check_at=row.get("next_check_at") or None,
                last_full_sweep_at=row.get("last_full_sweep_at") or None,
                backfill_complete=bool(row.get("backfill_complete", False)),
                consecutive_empty_runs=int(row.get("consecutive_empty_runs") or 0),
                last_new_urls=int(row.get("last_new_urls") or 0),
            )
        elif kind == "endpoint":
            url = row.get("url")
            if not isinstance(url, str) or not url or not checked_at:
                continue
            key = (vendor, url)
            prev_ep = endpoints.get(key)
            if prev_ep and prev_ep.checked_at > checked_at:
                continue
            endpoints[key] = EndpointState(
                vendor=vendor,
                url=url,
                checked_at=checked_at,
                etag=row.get("etag") or None,
                last_modified=row.get("last_modified") or None,
                sha256=row.get("sha256") or None,
                sitemap_lastmod=row.get("sitemap_lastmod") or None,
            )
    return vendors, endpoints


def compact_discovery_state(path: Path) -> int:
    if not path.exists():
        return 0
    vendors, endpoints = load_discovery_state(path)
    rows: list[dict[str, Any]] = [
        vendors[name].to_row() for name in sorted(vendors)
    ] + [
        endpoints[key].to_row() for key in sorted(endpoints)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return len(rows)


def _compute_vendor_yields(
    discovered_rows: list[dict[str, Any]],
    triage_path: Optional[Path],
) -> dict[str, VendorYield]:
    triage_decisions: dict[str, str] = {}
    if triage_path is not None and triage_path.exists():
        for row in load_jsonl(triage_path):
            url = row.get("url")
            decision = row.get("decision")
            if isinstance(url, str) and isinstance(decision, str):
                triage_decisions[url] = decision

    stats: dict[str, VendorYield] = defaultdict(VendorYield)
    latest_ts_by_vendor: dict[str, str] = {}
    urls_by_vendor_ts: dict[tuple[str, str], list[str]] = defaultdict(list)

    for row in discovered_rows:
        vendor = row.get("vendor")
        url = row.get("url")
        if not isinstance(vendor, str) or not isinstance(url, str):
            continue
        info = stats[vendor]
        info.discovered += 1
        decision = triage_decisions.get(url)
        if decision in {"keep", "drop", "reject"}:
            info.decided += 1
            if decision == "keep":
                info.kept += 1
        disc_at = str(row.get("discovered_at") or "")
        if disc_at:
            if disc_at >= latest_ts_by_vendor.get(vendor, ""):
                latest_ts_by_vendor[vendor] = disc_at
            urls_by_vendor_ts[(vendor, disc_at)].append(url)

    for vendor, last_ts in latest_ts_by_vendor.items():
        batch_urls = urls_by_vendor_ts.get((vendor, last_ts)) or []
        if batch_urls:
            decisions = [triage_decisions.get(u) for u in batch_urls]
            if all(d in {"drop", "reject"} for d in decisions):
                stats[vendor].last_batch_all_dropped = True

    return stats


class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(urljoin(self.base_url, value))
                return


def _parse_sitemap_detailed(
    body: bytes,
) -> tuple[list[tuple[str, Optional[str]]], list[tuple[str, Optional[str]]]]:
    """Return ([(child_sitemap_url, lastmod | None), ...], [(page_url, lastmod | None), ...])."""
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return [], []

    tag = root.tag.lower()
    nested: list[tuple[str, Optional[str]]] = []
    pages: list[tuple[str, Optional[str]]] = []

    if tag.endswith("sitemapindex"):
        for sitemap_el in root.findall("sm:sitemap", SITEMAP_NS):
            loc_el = sitemap_el.find("sm:loc", SITEMAP_NS)
            if loc_el is None or not loc_el.text:
                continue
            lastmod_el = sitemap_el.find("sm:lastmod", SITEMAP_NS)
            lastmod: Optional[str] = None
            if lastmod_el is not None and lastmod_el.text:
                raw = lastmod_el.text.strip()
                lastmod = raw[:10] if len(raw) >= 10 else raw
            nested.append((loc_el.text.strip(), lastmod))
    elif tag.endswith("urlset"):
        for url_el in root.findall("sm:url", SITEMAP_NS):
            loc_el = url_el.find("sm:loc", SITEMAP_NS)
            if loc_el is None or not loc_el.text:
                continue
            lastmod_el = url_el.find("sm:lastmod", SITEMAP_NS)
            lastmod = None
            if lastmod_el is not None and lastmod_el.text:
                raw = lastmod_el.text.strip()
                lastmod = raw[:10] if len(raw) >= 10 else raw
            pages.append((loc_el.text.strip(), lastmod))
    return nested, pages


def _parse_sitemap(body: bytes) -> tuple[list[str], list[tuple[str, Optional[str]]]]:
    """Return (nested_sitemap_urls, [(page_url, lastmod_yyyy_mm_dd | None), ...]).

    Handles sitemap index + urlset. `lastmod` is normalized to YYYY-MM-DD (the
    first 10 chars of the ISO 8601 value) so it sorts lexicographically.
    """
    nested, pages = _parse_sitemap_detailed(body)
    return [loc for loc, _ in nested], pages


def _fetch_discovery_endpoint(
    client: FetchClient,
    url: str,
    prev_ep: Optional[EndpointState],
    *,
    use_validators: bool = True,
) -> tuple[FetchResult, bool]:
    """Fetch a sitemap or index URL, returning (result, is_unchanged)."""
    use_cond = use_validators and prev_ep is not None
    result = client.fetch(
        url,
        if_none_match=prev_ep.etag if use_cond and prev_ep else None,
        if_modified_since=prev_ep.last_modified if use_cond and prev_ep else None,
        max_cache_age_seconds=DISCOVERY_CACHE_MAX_AGE_SECONDS,
    )
    if result.status == 304:
        return result, True
    if use_cond and prev_ep and prev_ep.sha256 and result.sha256 == prev_ep.sha256:
        return result, True
    return result, False


def _walk_sitemap_incremental(
    client: FetchClient,
    root_url: str,
    *,
    vendor: str,
    checked_at: str,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
    max_sitemaps: int = 20,
    enough: Optional[int] = None,
    existing: Optional[set[str]] = None,
    since: Optional[str] = None,
    endpoint_states: Optional[dict[tuple[str, str], EndpointState]] = None,
    use_validators: bool = True,
) -> tuple[list[tuple[str, Optional[str]]], list[EndpointState], bool, int]:
    """Walk sitemap (index -> child sitemaps -> urls) incrementally.

    Counts `enough` only against unseen, post-`since` matching URLs. Records
    EndpointState validators only for sitemaps walked completely without truncation.
    Returns `(matched, completed_endpoint_states, truncated, unchanged_hits)`.
    """
    pending: list[tuple[str, Optional[str]]] = [(root_url, None)]
    visited: set[str] = set()
    matched: list[tuple[str, Optional[str]]] = []
    matched_seen: set[str] = set()
    completed_endpoints: dict[str, EndpointState] = {}
    root_candidate: Optional[EndpointState] = None
    fetched = 0
    unchanged_hits = 0
    had_error = False

    while pending and fetched < max_sitemaps:
        url, declared_lastmod = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)

        if since and declared_lastmod and declared_lastmod < since:
            continue

        prev_ep = endpoint_states.get((vendor, url)) if endpoint_states else None
        if (
            use_validators
            and prev_ep is not None
            and declared_lastmod
            and prev_ep.sitemap_lastmod == declared_lastmod
        ):
            unchanged_hits += 1
            completed_endpoints[url] = EndpointState(
                vendor=vendor,
                url=url,
                checked_at=checked_at,
                etag=prev_ep.etag,
                last_modified=prev_ep.last_modified,
                sha256=prev_ep.sha256,
                sitemap_lastmod=declared_lastmod,
            )
            continue

        print(f"  sitemap[{fetched + 1}/{max_sitemaps}] {url}", file=sys.stderr, flush=True)
        try:
            result, is_unchanged = _fetch_discovery_endpoint(
                client,
                url,
                prev_ep,
                use_validators=use_validators,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  sitemap fetch failed: {url} -> {exc}", file=sys.stderr, flush=True)
            had_error = True
            continue
        fetched += 1

        if is_unchanged and prev_ep is not None:
            unchanged_hits += 1
            print(f"  sitemap unchanged ({result.status}): {url}", file=sys.stderr, flush=True)
            completed_endpoints[url] = EndpointState(
                vendor=vendor,
                url=url,
                checked_at=checked_at,
                etag=result.etag or prev_ep.etag,
                last_modified=result.last_modified or prev_ep.last_modified,
                sha256=prev_ep.sha256,
                sitemap_lastmod=declared_lastmod or prev_ep.sitemap_lastmod,
            )
            continue

        nested, found = _parse_sitemap_detailed(result.body)
        found.sort(key=lambda item: (item[1] is not None, item[1] or ""), reverse=True)
        for page, lastmod in found:
            if page in matched_seen or (existing is not None and page in existing):
                continue
            if since and lastmod and lastmod < since:
                continue
            if include_patterns and not any(p.search(page) for p in include_patterns):
                continue
            if any(p.search(page) for p in exclude_patterns):
                continue
            matched.append((page, lastmod))
            matched_seen.add(page)
            if enough is not None and len(matched) >= enough:
                print(f"  sitemap walk: reached unseen limit {enough}, stopping early", file=sys.stderr, flush=True)
                return matched, list(completed_endpoints.values()), True, unchanged_hits

        ep_state = EndpointState(
            vendor=vendor,
            url=url,
            checked_at=checked_at,
            etag=result.etag,
            last_modified=result.last_modified,
            sha256=result.sha256,
            sitemap_lastmod=declared_lastmod,
        )
        if not nested:
            completed_endpoints[url] = ep_state
        elif url == root_url:
            root_candidate = ep_state

        eligible_children = [
            (child_url, child_lastmod)
            for child_url, child_lastmod in nested
            if child_url not in visited and not (since and child_lastmod and child_lastmod < since)
        ]
        eligible_children.sort(key=lambda item: (item[1] is not None, item[1] or ""), reverse=True)
        pending.extend(eligible_children)

    truncated_by_max = bool(pending)
    if root_candidate is not None and not truncated_by_max and not had_error:
        completed_endpoints[root_url] = root_candidate

    print(
        f"  sitemap walk done: {fetched} sitemaps fetched, {unchanged_hits} unchanged, {len(matched)} unseen matches",
        file=sys.stderr,
        flush=True,
    )
    return matched, list(completed_endpoints.values()), truncated_by_max, unchanged_hits


def _walk_sitemap(
    client: FetchClient,
    root_url: str,
    *,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
    max_sitemaps: int = 20,
    enough: Optional[int] = None,
    existing: Optional[set[str]] = None,
    since: Optional[str] = None,
) -> list[tuple[str, Optional[str]]]:
    matched, _, _, _ = _walk_sitemap_incremental(
        client,
        root_url,
        vendor="",
        checked_at="",
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_sitemaps=max_sitemaps,
        enough=enough,
        existing=existing,
        since=since,
        endpoint_states=None,
        use_validators=False,
    )
    return matched


def _walk_aws_directory(
    client: FetchClient,
    api: dict,
    *,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
    since: Optional[str] = None,
    enough: Optional[int] = None,
    existing: Optional[set[str]] = None,
    stop_after_known: Optional[int] = None,
) -> tuple[list[tuple[str, Optional[str], Optional[str]]], bool]:
    """Page through an aws.amazon.com directory API (newest first).

    Returns `([(url, sort_date_yyyy_mm_dd | None, headline | None), ...], hit_enough)`.
    Counts `enough` only against unseen URLs and optionally stops after
    `stop_after_known` consecutive already-known URLs.
    """
    size = int(api.get("page_size", 50))
    matched: list[tuple[str, Optional[str], Optional[str]]] = []
    seen: set[str] = set()
    consecutive_known = 0
    page = 0
    while True:
        params = {
            "item.directoryId": api["directory_id"],
            "sort_by": "item.additionalFields.sortDate",
            "sort_order": "desc",
            "size": size,
            "page": page,
        }
        if api.get("locale"):
            params["item.locale"] = api["locale"]
        url = f"{api['url']}?{urlencode(params)}"
        print(f"  api page {page} {url}", file=sys.stderr, flush=True)
        try:
            payload = json.loads(client.fetch(url, use_cache=False).body)
        except Exception as exc:  # noqa: BLE001
            print(f"  api fetch failed: {url} -> {exc}", file=sys.stderr, flush=True)
            break
        items = payload.get("items") or []
        if not items:
            break
        for entry in items:
            fields = (entry.get("item") or {}).get("additionalFields") or {}
            link = str(fields.get("headlineUrl") or "").split("?")[0].split("#")[0]
            sort_date = str(fields.get("sortDate") or "")[:10] or None
            if since and sort_date and sort_date < since:
                print(f"  api walk: reached {sort_date} < {since}, stopping", file=sys.stderr, flush=True)
                return matched, False
            if not link or link in seen:
                continue
            seen.add(link)
            if include_patterns and not any(p.search(link) for p in include_patterns):
                continue
            if any(p.search(link) for p in exclude_patterns):
                continue
            if existing is not None and link in existing:
                consecutive_known += 1
                if stop_after_known is not None and consecutive_known >= stop_after_known:
                    print(
                        f"  api walk: reached {consecutive_known} consecutive known urls, stopping",
                        file=sys.stderr,
                        flush=True,
                    )
                    return matched, False
                continue
            consecutive_known = 0
            matched.append((link, sort_date, fields.get("headline")))
            if enough is not None and len(matched) >= enough:
                return matched, True
        page += 1
    print(f"  api walk done: {page} page(s), {len(matched)} unseen matches", file=sys.stderr, flush=True)
    return matched, False


def _walk_huawei_datahub(
    client: FetchClient,
    api: dict,
    *,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
    enough: Optional[int] = None,
    existing: Optional[set[str]] = None,
    stop_after_known: Optional[int] = None,
) -> list[tuple[str, Optional[str], Optional[str]]]:
    page_size = int(api.get("page_size", 100))
    page = 1
    matched: list[tuple[str, Optional[str], Optional[str]]] = []
    seen: set[str] = set()
    consecutive_known = 0
    total_pages: Optional[int] = None

    while total_pages is None or page <= total_pages:
        payload = {
            "pid": api["pid"],
            "type": api.get("entity_type", "customer-detail-case"),
            "releaseStage": api.get("release_stage", "PROD"),
            "filters": [
                {"fieldName": "site", "operation": "EQ", "fieldValue": api.get("site", "china")},
                {"fieldName": "lang", "operation": "EQ", "fieldValue": api.get("language", "zh-cn")},
            ],
            "summaryFilters": [],
            "orders": [{"fieldName": "contentTime", "direction": "DESC"}],
            "pageSize": page_size,
            "pageNumber": page,
            "aggregators": [],
        }
        print(f"  huawei datahub page {page}", file=sys.stderr, flush=True)
        try:
            response = json.loads(client.post_json(api["url"], payload).body)
        except Exception as exc:  # noqa: BLE001
            print(f"  huawei datahub failed on page {page}: {exc}", file=sys.stderr, flush=True)
            break
        data = response.get("data") or {}
        records = data.get("records") or []
        total_pages = int(data.get("totalPages") or page)
        for record in records:
            fields = record.get("extendMap") or {}
            url = str(fields.get("url") or "").split("?")[0].split("#")[0]
            if not url or url in seen:
                continue
            seen.add(url)
            if include_patterns and not any(pattern.search(url) for pattern in include_patterns):
                continue
            if any(pattern.search(url) for pattern in exclude_patterns):
                continue
            if existing is not None and url in existing:
                consecutive_known += 1
                if stop_after_known is not None and consecutive_known >= stop_after_known:
                    print(
                        f"  huawei datahub: reached {consecutive_known} consecutive known urls, stopping",
                        file=sys.stderr,
                        flush=True,
                    )
                    return matched
                continue
            consecutive_known = 0
            title = str(fields.get("companyName") or "").strip() or None
            matched.append((url, None, title))
            if enough is not None and len(matched) >= enough:
                return matched
        if not records:
            break
        page += 1
    print(f"  huawei datahub done: {page - 1} page(s), {len(matched)} matches", file=sys.stderr, flush=True)
    return matched


def _extract_index_links_incremental(
    client: FetchClient,
    index_url: str,
    *,
    vendor: str,
    checked_at: str,
    prev_ep: Optional[EndpointState] = None,
    use_validators: bool = True,
) -> tuple[list[str], Optional[EndpointState], bool]:
    print(f"  index {index_url}", file=sys.stderr, flush=True)
    try:
        result, is_unchanged = _fetch_discovery_endpoint(
            client,
            index_url,
            prev_ep,
            use_validators=use_validators,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  index fetch failed: {index_url} -> {exc}", file=sys.stderr, flush=True)
        return [], None, False

    if is_unchanged and prev_ep is not None:
        print(f"  index unchanged ({result.status}): {index_url}", file=sys.stderr, flush=True)
        return (
            [],
            EndpointState(
                vendor=vendor,
                url=index_url,
                checked_at=checked_at,
                etag=result.etag or prev_ep.etag,
                last_modified=result.last_modified or prev_ep.last_modified,
                sha256=prev_ep.sha256,
            ),
            True,
        )

    parser = _LinkExtractor(index_url)
    html = result.body.decode("utf-8", errors="replace")
    try:
        parser.feed(html)
    except Exception as exc:  # noqa: BLE001
        print(f"  index parse failed: {index_url} -> {exc}", file=sys.stderr, flush=True)
        return [], None, False
    # Client-rendered catalogs (e.g. Tencent Cloud China) keep story links in embedded
    # JSON rather than <a href>; the source's url_patterns weed out non-story paths.
    unescaped = html.replace("\\u002F", "/").replace("\\/", "/")
    embedded = [
        urljoin(index_url, path)
        for path in re.findall(r"""["'](https?://[^"'\s<>]+|/[^"'\s<>/][^"'\s<>]*)["']""", unescaped)
    ]
    links = list(dict.fromkeys(quote(link, safe=URL_SAFE) for link in parser.links + embedded))
    print(f"  index links: {len(links)}", file=sys.stderr, flush=True)
    return (
        links,
        EndpointState(
            vendor=vendor,
            url=index_url,
            checked_at=checked_at,
            etag=result.etag,
            last_modified=result.last_modified,
            sha256=result.sha256,
        ),
        False,
    )


def _extract_index_links(client: FetchClient, index_url: str) -> list[str]:
    links, _, _ = _extract_index_links_incremental(
        client,
        index_url,
        vendor="",
        checked_at="",
        prev_ep=None,
        use_validators=False,
    )
    return links


def _filter_urls(
    candidates: Iterable[str],
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        parts = urlsplit(url)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        if url in seen:
            continue
        seen.add(url)
        if include_patterns and not any(p.search(url) for p in include_patterns):
            continue
        if any(p.search(url) for p in exclude_patterns):
            continue
        matched.append(url)
    return matched


def _load_existing(path: Path) -> set[str]:
    urls: set[str] = set()
    for row in load_jsonl(path):
        url = row.get("url")
        if isinstance(url, str):
            urls.add(url)
    return urls


def _select_due_sources(
    sources: list[dict[str, Any]],
    vendor_states: dict[str, VendorState],
    vendor_yields: dict[str, VendorYield],
    *,
    current_time: datetime,
    vendor_filter: Optional[str] = None,
    max_vendors: Optional[int] = None,
    force_all: bool = False,
) -> tuple[list[tuple[dict[str, Any], VendorState]], int, int, int]:
    """Return `(selected_sources_with_state, skipped_disabled, skipped_cooldown, deferred_budget)`."""
    candidates: list[tuple[tuple[int, float, float, int], dict[str, Any], VendorState]] = []
    skipped_disabled = 0
    skipped_cooldown = 0

    for idx, source in enumerate(sources):
        vendor = source["vendor"]
        priority = str(source.get("priority") or "normal").lower()
        if priority not in PRIORITY_BOUNDS:
            raise ValueError(f"invalid priority {priority!r} for vendor {vendor}; expected one of {sorted(PRIORITY_BOUNDS)}")

        if vendor_filter:
            if vendor.lower() != vendor_filter.lower():
                continue
        elif not bool(source.get("enabled", True)):
            skipped_disabled += 1
            continue

        yield_info = vendor_yields.get(vendor, VendorYield())
        if vendor in vendor_states:
            vstate = vendor_states[vendor]
        elif yield_info.discovered > 0:
            vstate = VendorState(vendor=vendor, backfill_complete=True)
        else:
            vstate = VendorState(vendor=vendor, backfill_complete=False)

        is_onboarding = not vstate.backfill_complete
        next_dt = _parse_iso(vstate.next_check_at)

        if not vendor_filter and not force_all and not is_onboarding:
            if next_dt is not None and current_time < next_dt:
                skipped_cooldown += 1
                continue

        _, _, weight, _ = PRIORITY_BOUNDS[priority]
        overdue_days = (
            max(0.0, (current_time - next_dt).total_seconds() / 86400.0)
            if next_dt is not None
            else 1.0
        )
        urgency = weight * (1.0 + overdue_days)
        sort_key = (
            1 if is_onboarding else 0,
            urgency,
            yield_info.keep_rate,
            -idx,
        )
        candidates.append((sort_key, source, vstate))

    candidates.sort(key=lambda item: item[0], reverse=True)
    deferred_budget = 0
    if max_vendors is not None and max_vendors > 0 and not vendor_filter and not force_all:
        if len(candidates) > max_vendors:
            deferred_budget = len(candidates) - max_vendors
            candidates = candidates[:max_vendors]

    return [(src, st) for _, src, st in candidates], skipped_disabled, skipped_cooldown, deferred_budget


def print_discovery_status(
    sources_path: Path = SOURCES_PATH,
    discovered_path: Path = DISCOVERED_URLS_PATH,
    state_path: Path = DISCOVERY_STATE_PATH,
    triage_path: Path = TRIAGE_PATH,
    *,
    now: Optional[datetime] = None,
) -> None:
    current_time = now or datetime.now(timezone.utc)
    config = load_json(sources_path, {})
    discovered_rows = load_jsonl(discovered_path)
    vendor_states, _ = load_discovery_state(state_path)
    vendor_yields = _compute_vendor_yields(discovered_rows, triage_path)

    header = f"{'Vendor':<18} {'Prio':<6} {'State':<10} {'Disc':>5} {'Kept':>5} {'Yield':>6} {'Empty':>5} {'Due':<5} {'Next Check (UTC)'}"
    print(header)
    print("-" * len(header))
    for source in config.get("sources", []):
        vendor = source["vendor"]
        enabled = bool(source.get("enabled", True))
        priority = str(source.get("priority") or "normal").lower()
        y = vendor_yields.get(vendor, VendorYield())
        if vendor in vendor_states:
            st = vendor_states[vendor]
        elif y.discovered > 0:
            st = VendorState(vendor=vendor, backfill_complete=True)
        else:
            st = VendorState(vendor=vendor, backfill_complete=False)

        mode = "disabled" if not enabled else ("onboard" if not st.backfill_complete else "steady")
        next_dt = _parse_iso(st.next_check_at)
        is_due = enabled and (not st.backfill_complete or next_dt is None or current_time >= next_dt)
        yield_pct = f"{(y.kept / y.decided * 100):.0f}%" if y.decided else "n/a"
        next_str = st.next_check_at[:16].replace("T", " ") if st.next_check_at else "now"
        print(
            f"{vendor:<18} {priority:<6} {mode:<10} {y.discovered:>5} {y.kept:>5} "
            f"{yield_pct:>6} {st.consecutive_empty_runs:>5} {'yes' if is_due else 'no':<5} {next_str}"
        )


def discover(
    sources_path: Path,
    output_path: Path,
    *,
    vendor_filter: Optional[str] = None,
    limit_per_vendor: Optional[int] = None,
    cache_dir: Optional[Path] = None,
    use_sitemaps: bool = True,
    use_index_pages: bool = True,
    max_sitemaps: int = 20,
    since: Optional[str] = None,
    state_path: Optional[Path] = None,
    triage_path: Optional[Path] = None,
    max_vendors: Optional[int] = None,
    backfill_limit: Optional[int] = DEFAULT_BACKFILL_LIMIT,
    force_all: bool = False,
    full_sweep: bool = False,
    now: Optional[datetime] = None,
) -> dict[str, int]:
    config = load_json(sources_path, {})
    if not isinstance(config, dict):
        raise ValueError(f"invalid source config: {sources_path}")
    user_agent, delay = fetch_options(config)
    client = FetchClient(
        user_agent=user_agent,
        per_host_delay_seconds=delay,
        cache_dir=cache_dir,
        enable_wayback=False,
    )

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_iso = current_time.isoformat(timespec="seconds")

    discovered_rows = load_jsonl(output_path)
    existing: set[str] = {
        row["url"] for row in discovered_rows if isinstance(row.get("url"), str)
    }
    vendor_states, endpoint_states = load_discovery_state(state_path)
    vendor_yields = _compute_vendor_yields(discovered_rows, triage_path)

    selected, skipped_disabled, skipped_cooldown, deferred_budget = _select_due_sources(
        config.get("sources", []),
        vendor_states,
        vendor_yields,
        current_time=current_time,
        vendor_filter=vendor_filter,
        max_vendors=max_vendors,
        force_all=force_all,
    )

    counts: dict[str, int] = {}
    state_updates: list[dict[str, Any]] = []
    onboarding_checked = 0
    total_unchanged_hits = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("a", encoding="utf-8") as out:
            for source, vstate in selected:
                vendor = source["vendor"]
                priority = str(source.get("priority") or "normal").lower()
                min_days, max_days, _, steady_ceiling = PRIORITY_BOUNDS[priority]
                yield_info = vendor_yields.get(vendor, VendorYield())
                is_onboarding = not vstate.backfill_complete
                if is_onboarding:
                    onboarding_checked += 1

                if is_onboarding:
                    configured_bf = source.get("backfill_limit")
                    bf_cap = int(configured_bf) if configured_bf is not None else backfill_limit
                    if limit_per_vendor is not None and bf_cap is not None:
                        effective_limit: Optional[int] = max(limit_per_vendor, bf_cap)
                    elif configured_bf is not None:
                        effective_limit = int(configured_bf)
                    else:
                        effective_limit = limit_per_vendor
                else:
                    effective_limit = limit_per_vendor
                    if steady_ceiling is not None and effective_limit is not None:
                        effective_limit = min(effective_limit, steady_ceiling)

                last_sweep_dt = _parse_iso(vstate.last_full_sweep_at)
                needs_full_sweep = full_sweep or (
                    vstate.backfill_complete
                    and (
                        last_sweep_dt is None
                        or (current_time - last_sweep_dt) >= timedelta(days=FULL_SWEEP_INTERVAL_DAYS)
                    )
                )
                api_stop_after = None if (is_onboarding or needs_full_sweep) else API_CONSECUTIVE_KNOWN_STOP
                use_validators = not full_sweep

                mode_label = "onboarding" if is_onboarding else f"priority={priority}"
                print(
                    f"vendor: {vendor} ({mode_label}, cap={effective_limit or 'unlimited'}"
                    f"{', full-sweep' if needs_full_sweep else ''})",
                    file=sys.stderr,
                    flush=True,
                )

                include = [re.compile(p) for p in source.get("url_patterns", [])]
                exclude = [re.compile(p) for p in source.get("exclude_patterns", [])]

                filtered_sitemap: list[tuple[str, Optional[str]]] = []
                titles: dict[str, str] = {}
                pending_ep_states: list[EndpointState] = []
                unchanged_ep_states: list[EndpointState] = []
                was_truncated = False

                for api in source.get("apis", []):
                    remaining = (
                        max(0, effective_limit - len(filtered_sitemap))
                        if effective_limit is not None
                        else None
                    )
                    if remaining == 0:
                        was_truncated = True
                        break
                    api_type = api.get("type")
                    if api_type == "aws-directory":
                        found, api_truncated = _walk_aws_directory(
                            client,
                            api,
                            include_patterns=include,
                            exclude_patterns=exclude,
                            since=since,
                            enough=remaining,
                            existing=existing,
                            stop_after_known=api_stop_after,
                        )
                        was_truncated = was_truncated or api_truncated
                    elif api_type == "huawei-datahub":
                        found = _walk_huawei_datahub(
                            client,
                            api,
                            include_patterns=include,
                            exclude_patterns=exclude,
                            enough=remaining,
                            existing=existing,
                            stop_after_known=api_stop_after,
                        )
                        if remaining is not None and len(found) >= remaining:
                            was_truncated = True
                    else:
                        print(f"  unknown api type: {api_type}", file=sys.stderr, flush=True)
                        continue
                    for url, lastmod, title in found:
                        filtered_sitemap.append((url, lastmod))
                        if title:
                            titles[url] = title

                if use_sitemaps:
                    for sitemap in source.get("sitemaps", []):
                        remaining = (
                            max(0, effective_limit - len(filtered_sitemap))
                            if effective_limit is not None
                            else None
                        )
                        if remaining == 0:
                            was_truncated = True
                            break
                        sm_matched, sm_eps, sm_truncated, sm_unchanged = _walk_sitemap_incremental(
                            client,
                            sitemap,
                            vendor=vendor,
                            checked_at=now_iso,
                            include_patterns=include,
                            exclude_patterns=exclude,
                            max_sitemaps=max_sitemaps,
                            enough=remaining,
                            existing=existing,
                            since=since,
                            endpoint_states=endpoint_states,
                            use_validators=use_validators,
                        )
                        filtered_sitemap.extend(sm_matched)
                        pending_ep_states.extend(sm_eps)
                        was_truncated = was_truncated or sm_truncated
                        total_unchanged_hits += sm_unchanged

                filtered_index: list[str] = []
                filtered_index.extend(_filter_urls(source.get("seed_urls", []), include, exclude))
                if use_index_pages:
                    for index in source.get("index_pages", []):
                        prev_ep = endpoint_states.get((vendor, index))
                        raw_links, idx_ep, idx_unchanged = _extract_index_links_incremental(
                            client,
                            index,
                            vendor=vendor,
                            checked_at=now_iso,
                            prev_ep=prev_ep,
                            use_validators=use_validators,
                        )
                        if idx_unchanged:
                            total_unchanged_hits += 1
                            if idx_ep is not None:
                                unchanged_ep_states.append(idx_ep)
                        elif idx_ep is not None:
                            pending_ep_states.append(idx_ep)
                        filtered_index.extend(_filter_urls(raw_links, include, exclude))

                combined: list[tuple[str, str, Optional[str]]] = []
                seen: set[str] = set()
                for url, lastmod in filtered_sitemap:
                    if url not in seen and url not in existing:
                        combined.append((url, "sitemap", lastmod))
                        seen.add(url)
                for url in filtered_index:
                    if url not in seen and url not in existing:
                        combined.append((url, "index", None))
                        seen.add(url)

                # Newest first so a --limit cap keeps recent URLs over stale ones.
                combined.sort(key=lambda item: (item[2] is not None, item[2] or ""), reverse=True)

                if since:
                    # Known-stale URLs never enter the queue; unknown dates are judged after fetch.
                    combined = [item for item in combined if not item[2] or item[2] >= since]

                sliced_by_cap = False
                if effective_limit is not None and len(combined) > effective_limit:
                    combined = combined[:effective_limit]
                    sliced_by_cap = True
                    was_truncated = True

                for url, source_kind, lastmod in combined:
                    out.write(
                        json.dumps(
                            {
                                "vendor": vendor,
                                "url": url,
                                "discovered_at": now_iso,
                                "source": source_kind,
                                "lastmod": lastmod,
                                **({"title": titles[url]} if url in titles else {}),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    existing.add(url)

                counts[vendor] = len(combined)

                if is_onboarding:
                    new_backfill_complete = not was_truncated or (
                        effective_limit is not None and len(combined) < effective_limit
                    )
                else:
                    new_backfill_complete = True

                effective_min_days = (
                    max(min_days, 3.0) if (yield_info.is_noisy and priority != "high") else min_days
                )
                if not new_backfill_complete:
                    new_empty_runs = 0
                    next_check_dt = current_time
                elif len(combined) > 0:
                    new_empty_runs = 0
                    next_check_dt = current_time + timedelta(days=effective_min_days)
                else:
                    step = 2 if (vstate.last_new_urls > 0 and yield_info.last_batch_all_dropped) else 1
                    new_empty_runs = vstate.consecutive_empty_runs + step
                    interval_days = min(max_days, effective_min_days * (2 ** new_empty_runs))
                    next_check_dt = current_time + timedelta(days=interval_days)

                updated_vstate = VendorState(
                    vendor=vendor,
                    checked_at=now_iso,
                    next_check_at=next_check_dt.isoformat(timespec="seconds"),
                    last_full_sweep_at=now_iso if (needs_full_sweep or is_onboarding) else vstate.last_full_sweep_at,
                    backfill_complete=new_backfill_complete,
                    consecutive_empty_runs=new_empty_runs,
                    last_new_urls=len(combined),
                )
                state_updates.append(updated_vstate.to_row())

                eps_to_save = unchanged_ep_states + ([] if sliced_by_cap else pending_ep_states)
                seen_ep_urls: set[str] = set()
                for ep in eps_to_save:
                    if ep.url in seen_ep_urls:
                        continue
                    seen_ep_urls.add(ep.url)
                    endpoint_states[(vendor, ep.url)] = ep
                    state_updates.append(ep.to_row())

                print(
                    f"  {vendor}: +{len(combined)} new urls "
                    f"(sitemap={len(filtered_sitemap)}, index={len(filtered_index)}, "
                    f"next={updated_vstate.next_check_at[:10] if updated_vstate.next_check_at else 'now'})",
                    flush=True,
                )
    finally:
        client.close()

    if state_path is not None and state_updates:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("a", encoding="utf-8") as state_out:
            for row in state_updates:
                state_out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        f"Summary: checked={len(counts)} onboarding={onboarding_checked} "
        f"skipped_cooldown={skipped_cooldown} deferred_budget={deferred_budget} "
        f"skipped_disabled={skipped_disabled} unchanged_endpoints={total_unchanged_hits} "
        f"new_urls={sum(counts.values())}",
        flush=True,
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover vendor case study URLs incrementally.")
    parser.add_argument("--sources", type=Path, default=SOURCES_PATH)
    parser.add_argument("--output", type=Path, default=DISCOVERED_URLS_PATH)
    parser.add_argument("--state", type=Path, default=DISCOVERY_STATE_PATH)
    parser.add_argument("--triage", type=Path, default=TRIAGE_PATH)
    parser.add_argument("--vendor", type=str, default=None, help="Restrict to one vendor name (bypasses cooldown)")
    parser.add_argument("--limit-per-vendor", type=int, default=None)
    parser.add_argument("--backfill-limit", type=int, default=DEFAULT_BACKFILL_LIMIT)
    parser.add_argument(
        "--max-vendors",
        type=int,
        default=DEFAULT_MAX_VENDORS,
        help="Max due vendors to check in one scheduled pass (0 for unlimited)",
    )
    parser.add_argument("--max-sitemaps", type=int, default=20, help="Cap on sitemap fetches per source")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Skip URLs whose sitemap/API date is older than this (YYYY-MM-DD); unknown dates are kept",
    )
    parser.add_argument("--skip-sitemaps", action="store_true", help="Use index pages only")
    parser.add_argument("--skip-index", action="store_true", help="Use sitemaps only")
    parser.add_argument("--force-all", action="store_true", help="Bypass vendor cooldown intervals")
    parser.add_argument("--full-sweep", action="store_true", help="Bypass API early-stop cursors and validator caches")
    parser.add_argument("--compact", action="store_true", help="Compact discovery_state.jsonl in place and exit")
    parser.add_argument("--status", action="store_true", help="Print vendor scheduling and yield status and exit")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=HTTP_CACHE_DIR,
        help="Disk cache for sitemap/index responses",
    )
    args = parser.parse_args()

    if args.compact:
        rows = compact_discovery_state(args.state)
        print(f"Compacted {rows} state row(s) -> {args.state}")
        return

    if args.status:
        print_discovery_status(
            sources_path=args.sources,
            discovered_path=args.output,
            state_path=args.state,
            triage_path=args.triage,
        )
        return

    counts = discover(
        sources_path=args.sources,
        output_path=args.output,
        vendor_filter=args.vendor,
        limit_per_vendor=args.limit_per_vendor,
        backfill_limit=args.backfill_limit,
        cache_dir=args.cache_dir,
        use_sitemaps=not args.skip_sitemaps,
        use_index_pages=not args.skip_index,
        max_sitemaps=args.max_sitemaps,
        since=args.since,
        state_path=args.state,
        triage_path=args.triage,
        max_vendors=args.max_vendors if args.max_vendors > 0 else None,
        force_all=args.force_all,
        full_sweep=args.full_sweep,
    )
    total = sum(counts.values())
    print(f"Discovered {total} new urls across {len(counts)} vendors -> {args.output}")


if __name__ == "__main__":
    main()
