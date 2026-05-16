"""URL discovery from vendor sitemaps and listing pages.

Reads `data/sources.json`, walks each vendor's sitemap(s), applies include/exclude regex
filters, and appends new URLs to `data/discovered_urls.jsonl`.

JSONL schema per line:
    {"vendor": str, "url": str, "discovered_at": ISO8601,
     "source": "sitemap" | "index", "lastmod": "YYYY-MM-DD" | null}

`lastmod` is the sitemap-reported last-modified date when available (sitemap source
only; index-page URLs get null). Downstream stages (fetch, extract) sort the queue by
`lastmod` desc so the most recent case studies are processed first.

Idempotent — already-known URLs are skipped on rerun.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin
from xml.etree import ElementTree

from .http_client import PoliteClient

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


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


def _parse_sitemap(body: bytes) -> tuple[list[str], list[tuple[str, Optional[str]]]]:
    """Return (nested_sitemap_urls, [(page_url, lastmod_yyyy_mm_dd | None), ...]).

    Handles sitemap index + urlset. `lastmod` is normalized to YYYY-MM-DD (the
    first 10 chars of the ISO 8601 value) so it sorts lexicographically.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return [], []

    tag = root.tag.lower()
    nested: list[str] = []
    pages: list[tuple[str, Optional[str]]] = []

    if tag.endswith("sitemapindex"):
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
            if loc.text:
                nested.append(loc.text.strip())
    elif tag.endswith("urlset"):
        for url_el in root.findall("sm:url", SITEMAP_NS):
            loc_el = url_el.find("sm:loc", SITEMAP_NS)
            if loc_el is None or not loc_el.text:
                continue
            lastmod_el = url_el.find("sm:lastmod", SITEMAP_NS)
            lastmod: Optional[str] = None
            if lastmod_el is not None and lastmod_el.text:
                raw = lastmod_el.text.strip()
                lastmod = raw[:10] if len(raw) >= 10 else raw
            pages.append((loc_el.text.strip(), lastmod))
    return nested, pages


def _walk_sitemap(
    client: PoliteClient,
    root_url: str,
    *,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
    max_sitemaps: int = 20,
    enough: Optional[int] = None,
) -> list[tuple[str, Optional[str]]]:
    """Walk sitemap (index → child sitemaps → urls) with progress + early-exit.

    Returns `[(url, lastmod_yyyy_mm_dd | None), ...]`. Stops as soon as `enough`
    filter-matching urls accumulate, so a 180-child sitemap index doesn't fully
    expand on every run.
    """
    pending: list[str] = [root_url]
    visited: set[str] = set()
    matched: list[tuple[str, Optional[str]]] = []
    matched_seen: set[str] = set()
    fetched = 0

    while pending and fetched < max_sitemaps:
        url = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)
        print(f"  sitemap[{fetched + 1}/{max_sitemaps}] {url}", file=sys.stderr, flush=True)
        try:
            result = client.fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  sitemap fetch failed: {url} -> {exc}", file=sys.stderr, flush=True)
            continue
        fetched += 1
        nested, found = _parse_sitemap(result.body)
        for page, lastmod in found:
            if page in matched_seen:
                continue
            if include_patterns and not any(p.search(page) for p in include_patterns):
                continue
            if any(p.search(page) for p in exclude_patterns):
                continue
            matched.append((page, lastmod))
            matched_seen.add(page)
            if enough is not None and len(matched) >= enough:
                print(f"  sitemap walk: reached limit {enough}, stopping early", file=sys.stderr, flush=True)
                return matched
        for child in nested:
            if child not in visited:
                pending.append(child)
    print(f"  sitemap walk done: {fetched} sitemaps fetched, {len(matched)} matches", file=sys.stderr, flush=True)
    return matched


def _extract_index_links(client: PoliteClient, index_url: str) -> list[str]:
    print(f"  index {index_url}", file=sys.stderr, flush=True)
    try:
        result = client.fetch(index_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  index fetch failed: {index_url} -> {exc}", file=sys.stderr, flush=True)
        return []
    parser = _LinkExtractor(index_url)
    try:
        parser.feed(result.body.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"  index parse failed: {index_url} -> {exc}", file=sys.stderr, flush=True)
        return []
    print(f"  index links: {len(parser.links)}", file=sys.stderr, flush=True)
    return parser.links


def _filter_urls(
    candidates: Iterable[str],
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for url in candidates:
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
    if not path.exists():
        return set()
    urls: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                urls.add(json.loads(line)["url"])
            except (json.JSONDecodeError, KeyError):
                continue
    return urls


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
) -> dict[str, int]:
    config = json.loads(sources_path.read_text(encoding="utf-8"))
    client = PoliteClient(
        user_agent=config.get("user_agent", "UseCaseIntelBot/0.1"),
        per_host_delay_seconds=config.get("default_delay_seconds", 1.0),
        cache_dir=cache_dir,
    )

    existing = _load_existing(output_path)
    counts: dict[str, int] = {}
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("a", encoding="utf-8") as out:
        for source in config.get("sources", []):
            vendor = source["vendor"]
            if vendor_filter and vendor.lower() != vendor_filter.lower():
                continue
            print(f"vendor: {vendor}", file=sys.stderr, flush=True)

            include = [re.compile(p) for p in source.get("url_patterns", [])]
            exclude = [re.compile(p) for p in source.get("exclude_patterns", [])]

            filtered_sitemap: list[tuple[str, Optional[str]]] = []
            if use_sitemaps:
                for sitemap in source.get("sitemaps", []):
                    filtered_sitemap.extend(
                        _walk_sitemap(
                            client,
                            sitemap,
                            include_patterns=include,
                            exclude_patterns=exclude,
                            max_sitemaps=max_sitemaps,
                            enough=limit_per_vendor,
                        )
                    )
                    if limit_per_vendor is not None and len(filtered_sitemap) >= limit_per_vendor:
                        break

            filtered_index: list[str] = []
            if use_index_pages:
                for index in source.get("index_pages", []):
                    raw_links = _extract_index_links(client, index)
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

            if limit_per_vendor is not None:
                combined = combined[:limit_per_vendor]

            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for url, source_kind, lastmod in combined:
                out.write(
                    json.dumps(
                        {
                            "vendor": vendor,
                            "url": url,
                            "discovered_at": now,
                            "source": source_kind,
                            "lastmod": lastmod,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                existing.add(url)
            counts[vendor] = len(combined)
            print(
                f"  {vendor}: +{len(combined)} new urls (sitemap={len(filtered_sitemap)}, index={len(filtered_index)})",
                flush=True,
            )

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover vendor case study URLs from sitemaps.")
    parser.add_argument("--sources", type=Path, default=Path("data/sources.json"))
    parser.add_argument("--output", type=Path, default=Path("data/discovered_urls.jsonl"))
    parser.add_argument("--vendor", type=str, default=None, help="Restrict to one vendor name")
    parser.add_argument("--limit-per-vendor", type=int, default=None)
    parser.add_argument("--max-sitemaps", type=int, default=20, help="Cap on sitemap fetches per source")
    parser.add_argument("--skip-sitemaps", action="store_true", help="Use index pages only")
    parser.add_argument("--skip-index", action="store_true", help="Use sitemaps only")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/http_cache"),
        help="Disk cache for sitemap/index responses",
    )
    args = parser.parse_args()

    counts = discover(
        sources_path=args.sources,
        output_path=args.output,
        vendor_filter=args.vendor,
        limit_per_vendor=args.limit_per_vendor,
        cache_dir=args.cache_dir,
        use_sitemaps=not args.skip_sitemaps,
        use_index_pages=not args.skip_index,
        max_sitemaps=args.max_sitemaps,
    )
    total = sum(counts.values())
    print(f"Discovered {total} new urls across {len(counts)} vendors -> {args.output}")


if __name__ == "__main__":
    main()
