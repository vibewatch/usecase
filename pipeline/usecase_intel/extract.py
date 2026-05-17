"""Build extraction prompt bundles from fetched content.

Reads the fetch manifest, cleans each fetched page/document to text, and emits one prompt
bundle per page under `data/extract_jobs/{vendor_slug}/{sha256}.json`. Each
bundle is a self-contained brief — source URL, taxonomy, SKILL.md instructions,
cleaned page text — for an agent to read and turn into a normalized record.

The agent (this assistant) reads the cleaned text or bundle, applies the
case-study-extraction skill, and writes the resulting record by hand to
`data/records/{vendor_slug}/{slug}.json`. From there `merge_records.py`
collects everything for `seed.py`.

Resumability: URLs whose record already exists under `data/records/` are
skipped, as are URLs whose bundle file already exists. Pass `--rebuild` to
force regeneration of bundles. Candidates are sorted by sitemap `lastmod`
desc (from `data/discovered_urls.jsonl`) so the freshest case studies are
bundled first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .clean import content_to_text
from .fetch_client import FetchClient
from .media import extract_related_images, materialize_related_images
from .settings import (
    DEFAULT_TIMEOUT_SECONDS,
    DISCOVERED_URLS_PATH,
    EXTRACTION_SKILL_PATH,
    EXTRACT_JOBS_ROOT,
    FETCH_MANIFEST_PATH,
    RECORDS_ROOT,
    SOURCES_PATH,
    TAXONOMY_PATH,
    fetch_options,
)
from .utils import load_json, load_jsonl, slugify

PROMPT_TEMPLATE = """You are an extraction agent. Follow the SKILL below exactly and return a single strict JSON object — no markdown fences, no prose.

=== SKILL.md ===
{skill}

=== TAXONOMY (taxonomy.json) ===
{taxonomy}

=== SOURCE URL ===
{source_url}

=== PAGE TITLE ===
{title}

=== PAGE TEXT ===
{body}

Return one JSON object matching the schema in SKILL.md. No other output.
"""


def build_prompt(
    *,
    skill_text: str,
    taxonomy_text: str,
    source_url: str,
    title: str,
    body: str,
    body_char_limit: int = 18000,
) -> str:
    if len(body) > body_char_limit:
        body = body[:body_char_limit] + "\n...[truncated]"
    return PROMPT_TEMPLATE.format(
        skill=skill_text.strip(),
        taxonomy=taxonomy_text.strip(),
        source_url=source_url,
        title=title or "(no title)",
        body=body,
    )



def _collect_extracted_source_urls(records_root: Path) -> set[str]:
    """Return the set of `source_url` values across every record under `records_root`.

    Used to skip URLs that already have a finished record on disk so re-running
    extract only produces bundles for new work.
    """
    urls: set[str] = set()
    if not records_root.exists():
        return urls
    for rec_path in records_root.glob("*/*.json"):
        try:
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        src = rec.get("source_url")
        if isinstance(src, str) and src:
            urls.add(src)
    return urls


def extract_jobs(
    *,
    manifest_path: Path,
    jobs_root: Path,
    skill_path: Path,
    taxonomy_path: Path,
    vendor_filter: Optional[str] = None,
    limit: Optional[int] = None,
    discovered_path: Optional[Path] = None,
    records_root: Optional[Path] = None,
    sources_path: Optional[Path] = None,
    image_assets_limit: int = 6,
    image_timeout_seconds: float = 4.0,
    image_min_score: int = 8,
    include_css_backgrounds: bool = True,
    image_client: Optional[object] = None,
    rebuild: bool = False,
) -> dict[str, int]:
    if image_assets_limit < 0:
        raise ValueError("image_assets_limit must be >= 0")
    if image_timeout_seconds <= 0:
        raise ValueError("image_timeout_seconds must be > 0")
    if image_min_score < 1:
        raise ValueError("image_min_score must be >= 1")

    skill_text = skill_path.read_text(encoding="utf-8")
    taxonomy_text = taxonomy_path.read_text(encoding="utf-8")
    manifest_latest: dict[str, dict] = {}
    for row in load_jsonl(manifest_path):
        url = row.get("url")
        if isinstance(url, str) and url:
            manifest_latest[url] = row
    manifest = list(manifest_latest.values())

    discovered_path = discovered_path or DISCOVERED_URLS_PATH
    records_root = records_root or RECORDS_ROOT
    sources_path = sources_path or SOURCES_PATH
    if image_assets_limit > 0 and image_client is None:
        user_agent, delay = fetch_options(load_json(sources_path, {}))
        image_client = FetchClient(
            user_agent=user_agent,
            per_host_delay_seconds=delay,
            timeout_seconds=image_timeout_seconds,
            cache_dir=None,
        )

    url_to_lastmod: dict[str, Optional[str]] = {}
    for row in load_jsonl(discovered_path):
        url = row.get("url")
        if isinstance(url, str):
            # Last write wins; that's fine since lastmod for a given URL is stable
            # within a single sitemap and only changes on re-discover.
            url_to_lastmod[url] = row.get("lastmod")

    extracted_urls = _collect_extracted_source_urls(records_root)

    jobs_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {
        "jobs": 0,
        "image_assets": 0,
        "skipped_existing_record": 0,
        "skipped_existing_bundle": 0,
        "skipped_missing_raw": 0,
    }
    candidates = [row for row in manifest if row.get("status") == 200 and row.get("raw_path")]
    if vendor_filter:
        candidates = [row for row in candidates if row["vendor"].lower() == vendor_filter.lower()]

    # Drop URLs whose final record already exists on disk.
    pruned: list[dict] = []
    for row in candidates:
        if row["url"] in extracted_urls:
            counts["skipped_existing_record"] += 1
            continue
        pruned.append(row)
    candidates = pruned

    # Newest first so a --limit cap keeps recent items over stale ones.
    candidates.sort(
        key=lambda r: (
            url_to_lastmod.get(r["url"]) is not None,
            url_to_lastmod.get(r["url"]) or "",
        ),
        reverse=True,
    )

    if limit is not None:
        candidates = candidates[:limit]

    print(
        f"Preparing {len(candidates)} extraction bundle(s); "
        f"skipped {counts['skipped_existing_record']} url(s) already in data/records/"
    )

    for row in candidates:
        vendor = row["vendor"]
        vendor_slug = slugify(vendor)
        sha = row["sha256"]
        raw_path = Path(row["raw_path"])
        if not raw_path.exists():
            counts["skipped_missing_raw"] += 1
            continue

        job_dir = jobs_root / vendor_slug
        job_dir.mkdir(parents=True, exist_ok=True)
        job_path = job_dir / f"{sha}.json"
        if job_path.exists() and not rebuild:
            counts["skipped_existing_bundle"] += 1
            continue

        raw_body = raw_path.read_bytes()
        title, body, extraction_method = content_to_text(
            raw_body,
            content_type=str(row.get("content_type") or ""),
            max_chars=18000,
        )
        related_images = extract_related_images(
            raw_body,
            content_type=str(row.get("content_type") or ""),
            source_url=str(row.get("final_url") or row["url"]),
            min_score=image_min_score,
            include_embedded=image_assets_limit > 0,
            include_css_backgrounds=include_css_backgrounds,
        )
        if image_client is not None and image_assets_limit > 0 and related_images:
            related_images = materialize_related_images(
                related_images,
                assets_dir=job_dir / f"{sha}.assets",
                client=image_client,
                max_assets=image_assets_limit,
            )
        counts["image_assets"] += sum(1 for image in related_images if image.get("local_path"))
        prompt = build_prompt(
            skill_text=skill_text,
            taxonomy_text=taxonomy_text,
            source_url=row["url"],
            title=title,
            body=body,
        )

        job_path.write_text(
            json.dumps(
                {
                    "vendor": vendor,
                    "source_url": row["url"],
                    "sha256": sha,
                    "title": title,
                    "raw_path": str(raw_path),
                    "content_type": row.get("content_type"),
                    "retrieval_source": row.get("retrieval_source"),
                    "profile": row.get("profile"),
                    "extraction_method": extraction_method,
                    "related_images": related_images,
                    "published_date": url_to_lastmod.get(row["url"]),
                    "prompt": prompt,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        counts["jobs"] += 1
        print(f"  job  {vendor:14s} {row['url']}", file=sys.stderr)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build extraction prompt bundles from fetched content."
    )
    parser.add_argument("--manifest", type=Path, default=FETCH_MANIFEST_PATH)
    parser.add_argument("--discovered", type=Path, default=DISCOVERED_URLS_PATH)
    parser.add_argument("--records-root", type=Path, default=RECORDS_ROOT)
    parser.add_argument("--jobs-root", type=Path, default=EXTRACT_JOBS_ROOT)
    parser.add_argument("--skill", type=Path, default=EXTRACTION_SKILL_PATH)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH)
    parser.add_argument("--sources", type=Path, default=SOURCES_PATH)
    parser.add_argument("--vendor", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--image-assets-limit",
        type=int,
        default=6,
        help="Download up to this many related image candidates per bundle; 0 keeps URLs only.",
    )
    parser.add_argument(
        "--image-timeout-seconds",
        type=float,
        default=min(4.0, DEFAULT_TIMEOUT_SECONDS),
        help="Per-image download timeout in seconds.",
    )
    parser.add_argument(
        "--image-min-score",
        type=int,
        default=8,
        help="Minimum related-image score to keep; diagram-like candidates are always kept.",
    )
    parser.add_argument(
        "--no-css-background-images",
        action="store_true",
        help="Skip article CSS background-image candidates.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate bundles even if a bundle file already exists.",
    )
    args = parser.parse_args()

    counts = extract_jobs(
        manifest_path=args.manifest,
        jobs_root=args.jobs_root,
        skill_path=args.skill,
        taxonomy_path=args.taxonomy,
        vendor_filter=args.vendor,
        limit=args.limit,
        discovered_path=args.discovered,
        records_root=args.records_root,
        sources_path=args.sources,
        image_assets_limit=args.image_assets_limit,
        image_timeout_seconds=args.image_timeout_seconds,
        image_min_score=args.image_min_score,
        include_css_backgrounds=not args.no_css_background_images,
        rebuild=args.rebuild,
    )
    print(
        "Jobs="
        f"{counts['jobs']} "
        f"image_assets={counts['image_assets']} "
        f"skipped_existing_record={counts['skipped_existing_record']} "
        f"skipped_existing_bundle={counts['skipped_existing_bundle']} "
        f"skipped_missing_raw={counts['skipped_missing_raw']}"
    )


if __name__ == "__main__":
    main()

