"""Fetch discovered URLs to disk, idempotently.

Reads `data/discovered_urls.jsonl`, fetches each unfetched URL via the polite client,
writes raw HTML to `data/raw_html/{vendor_slug}/{sha256}.html`, and appends a manifest
record per URL.

Manifest JSONL line:
    {"vendor": str, "url": str, "html_path": str, "status": int,
     "sha256": str, "fetched_at": ISO8601, "from_cache": bool, "error": null | str}

Rerun-safe: URLs already in the manifest (with status 200) are skipped unless --refresh.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .http_client import PoliteClient


def _slugify_vendor(vendor: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", vendor.lower()).strip("-")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def fetch_urls(
    discovered_path: Path,
    manifest_path: Path,
    raw_root: Path,
    *,
    vendor_filter: Optional[str] = None,
    limit: Optional[int] = None,
    refresh: bool = False,
    sources_path: Optional[Path] = None,
) -> dict[str, int]:
    sources_path = sources_path or Path("data/sources.json")
    user_agent = "UseCaseIntelBot/0.1 (+https://github.com/vibewatch/usecase)"
    delay = 1.0
    if sources_path.exists():
        config = json.loads(sources_path.read_text(encoding="utf-8"))
        user_agent = config.get("user_agent", user_agent)
        delay = config.get("default_delay_seconds", delay)

    client = PoliteClient(user_agent=user_agent, per_host_delay_seconds=delay, cache_dir=None)

    discovered = _load_jsonl(discovered_path)
    manifest_entries = _load_jsonl(manifest_path)
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
        existing = already.get(url)
        if not refresh and existing and existing.get("status") == 200 and not existing.get("error"):
            continue
        queue.append(row)
        if limit is not None and len(queue) >= limit:
            break

    counts: dict[str, int] = {"ok": 0, "error": 0, "skipped": len(discovered) - len(queue)}
    print(f"Fetching {len(queue)} url(s); {counts['skipped']} already in manifest")

    with manifest_path.open("a", encoding="utf-8") as out:
        for row in queue:
            url = row["url"]
            vendor = row["vendor"]
            vendor_dir = raw_root / _slugify_vendor(vendor)
            vendor_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            try:
                result = client.fetch(url, use_cache=False)
                html_path = vendor_dir / f"{result.sha256}.html"
                if not html_path.exists():
                    html_path.write_bytes(result.body)
                entry = {
                    "vendor": vendor,
                    "url": url,
                    "html_path": str(html_path),
                    "status": result.status,
                    "sha256": result.sha256,
                    "content_type": result.content_type,
                    "fetched_at": now,
                    "from_cache": result.from_cache,
                    "error": None,
                }
                counts["ok"] += 1
                print(f"  ok  {vendor:14s} {url}")
            except Exception as exc:  # noqa: BLE001
                entry = {
                    "vendor": vendor,
                    "url": url,
                    "html_path": None,
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
    parser.add_argument("--discovered", type=Path, default=Path("data/discovered_urls.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/fetch_manifest.jsonl"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw_html"))
    parser.add_argument("--vendor", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh", action="store_true", help="Refetch URLs already in manifest")
    args = parser.parse_args()

    counts = fetch_urls(
        discovered_path=args.discovered,
        manifest_path=args.manifest,
        raw_root=args.raw_root,
        vendor_filter=args.vendor,
        limit=args.limit,
        refresh=args.refresh,
    )
    print(f"Fetched ok={counts['ok']} error={counts['error']} skipped={counts['skipped']}")


if __name__ == "__main__":
    main()
