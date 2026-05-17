"""Fetch discovered URLs to disk, idempotently.

Reads discovered URL rows, fetches each new URL via the pipeline client, writes
raw response bytes to disk, and appends one manifest record per URL.

Manifest JSONL line:
    {"vendor": str, "url": str, "raw_path": str, "status": int,
     "sha256": str, "fetched_at": ISO8601, "from_cache": bool, "error": null | str}

Rerun-safe: URLs already in the manifest (with status 200) are skipped unless --refresh.
Queue is sorted by sitemap `lastmod` desc so the most recent case studies are fetched
first; URLs without a `lastmod` (e.g. discovered via index pages) sort to the end.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .fetch_client import FetchClient
from .settings import (
    DISCOVERED_URLS_PATH,
    FETCH_MANIFEST_PATH,
    RAW_CONTENT_ROOT,
    SOURCES_PATH,
    fetch_options,
)
from .utils import load_json, load_jsonl, slugify


def _raw_suffix(content_type: str) -> str:
    content_type = content_type.lower()
    if "pdf" in content_type:
        return ".pdf"
    if "json" in content_type:
        return ".json"
    if content_type.startswith("text/plain"):
        return ".txt"
    return ".html"


def fetch_urls(
    discovered_path: Path,
    manifest_path: Path,
    raw_root: Path,
    *,
    vendor_filter: Optional[str] = None,
    limit: Optional[int] = None,
    refresh: bool = False,
    sources_path: Optional[Path] = None,
    since: Optional[str] = None,
) -> dict[str, int]:
    sources_path = sources_path or SOURCES_PATH
    user_agent, delay = fetch_options(load_json(sources_path, {}))

    client = FetchClient(user_agent=user_agent, per_host_delay_seconds=delay, cache_dir=None)

    discovered = load_jsonl(discovered_path)
    manifest_entries = load_jsonl(manifest_path)
    already: dict[str, dict] = {entry["url"]: entry for entry in manifest_entries}
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    queue: list[dict] = []
    for row in discovered:
        url = row.get("url")
        vendor = row.get("vendor")
        if not url or not vendor:
            continue
        if vendor_filter and vendor.lower() != vendor_filter.lower():
            continue
        if since and row.get("lastmod") and row["lastmod"] < since:
            # Skip stale items with a known lastmod; unknown-date items still pass.
            continue
        existing = already.get(url)
        if not refresh and existing and existing.get("status") == 200 and not existing.get("error"):
            continue
        queue.append(row)

    # Newest first; unknown dates sink to the bottom.
    queue.sort(
        key=lambda r: (r.get("lastmod") is not None, r.get("lastmod") or ""),
        reverse=True,
    )
    if limit is not None:
        queue = queue[:limit]

    counts: dict[str, int] = {"ok": 0, "error": 0, "skipped": len(discovered) - len(queue)}
    print(f"Fetching {len(queue)} url(s); {counts['skipped']} skipped (already fetched, vendor-filtered, --since, or trimmed by --limit)")

    with manifest_path.open("a", encoding="utf-8") as out:
        for row in queue:
            url = row["url"]
            vendor = row["vendor"]
            vendor_dir = raw_root / slugify(vendor)
            vendor_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            try:
                result = client.fetch(url, use_cache=False)
                if not result.body:
                    raise ValueError("empty response body")
                raw_path = vendor_dir / f"{result.sha256}{_raw_suffix(result.content_type)}"
                if not raw_path.exists():
                    raw_path.write_bytes(result.body)
                entry = {
                    "vendor": vendor,
                    "url": url,
                    "raw_path": str(raw_path),
                    "status": result.status,
                    "sha256": result.sha256,
                    "content_type": result.content_type,
                    "fetched_at": now,
                    "from_cache": result.from_cache,
                    "final_url": result.final_url,
                    "retrieval_source": result.retrieval_source,
                    "profile": result.profile,
                    "error": None,
                }
                counts["ok"] += 1
                print(f"  ok  {vendor:14s} {url}")
            except Exception as exc:  # noqa: BLE001
                entry = {
                    "vendor": vendor,
                    "url": url,
                    "raw_path": None,
                    "status": 0,
                    "sha256": None,
                    "content_type": None,
                    "fetched_at": now,
                    "from_cache": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                counts["error"] += 1
                print(f"  ERR {vendor:14s} {url} -> {exc}", file=sys.stderr)

            out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch discovered URLs to disk.")
    parser.add_argument("--discovered", type=Path, default=DISCOVERED_URLS_PATH)
    parser.add_argument("--manifest", type=Path, default=FETCH_MANIFEST_PATH)
    parser.add_argument("--raw-root", type=Path, default=RAW_CONTENT_ROOT)
    parser.add_argument("--vendor", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh", action="store_true", help="Refetch URLs already in manifest")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only fetch URLs whose sitemap lastmod is >= this date (YYYY-MM-DD). "
        "URLs without a known lastmod are kept.",
    )
    args = parser.parse_args()

    counts = fetch_urls(
        discovered_path=args.discovered,
        manifest_path=args.manifest,
        raw_root=args.raw_root,
        vendor_filter=args.vendor,
        limit=args.limit,
        refresh=args.refresh,
        since=args.since,
    )
    print(f"Fetched ok={counts['ok']} error={counts['error']} skipped={counts['skipped']}")


if __name__ == "__main__":
    main()
