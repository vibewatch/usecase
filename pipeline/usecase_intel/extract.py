"""Build extraction prompt bundles from fetched HTML.

Reads the fetch manifest, cleans each HTML page to text, and emits one prompt
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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .clean import html_to_text

SKILL_PATH_DEFAULT = Path(".agents/skills/case-study-extraction/SKILL.md")
TAXONOMY_PATH_DEFAULT = Path("taxonomy.json")
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


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-") or "untitled"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


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
    rebuild: bool = False,
) -> dict[str, int]:
    skill_text = skill_path.read_text(encoding="utf-8")
    taxonomy_text = taxonomy_path.read_text(encoding="utf-8")
    manifest = _load_jsonl(manifest_path)

    discovered_path = discovered_path or Path("data/discovered_urls.jsonl")
    records_root = records_root or Path("data/records")

    url_to_lastmod: dict[str, Optional[str]] = {}
    for row in _load_jsonl(discovered_path):
        url = row.get("url")
        if isinstance(url, str):
            # Last write wins; that's fine since lastmod for a given URL is stable
            # within a single sitemap and only changes on re-discover.
            url_to_lastmod[url] = row.get("lastmod")

    extracted_urls = _collect_extracted_source_urls(records_root)

    jobs_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {"jobs": 0, "skipped_existing_record": 0, "skipped_existing_bundle": 0, "skipped_missing_html": 0}
    candidates = [row for row in manifest if row.get("status") == 200 and row.get("html_path")]
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
        vendor_slug = _slugify(vendor)
        sha = row["sha256"]
        html_path = Path(row["html_path"])
        if not html_path.exists():
            counts["skipped_missing_html"] += 1
            continue

        job_dir = jobs_root / vendor_slug
        job_dir.mkdir(parents=True, exist_ok=True)
        job_path = job_dir / f"{sha}.json"
        if job_path.exists() and not rebuild:
            counts["skipped_existing_bundle"] += 1
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace")
        title, body = html_to_text(html)
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
                    "html_path": str(html_path),
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
        description="Build extraction prompt bundles from fetched HTML."
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/fetch_manifest.jsonl"))
    parser.add_argument("--discovered", type=Path, default=Path("data/discovered_urls.jsonl"))
    parser.add_argument("--records-root", type=Path, default=Path("data/records"))
    parser.add_argument("--jobs-root", type=Path, default=Path("data/extract_jobs"))
    parser.add_argument("--skill", type=Path, default=SKILL_PATH_DEFAULT)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH_DEFAULT)
    parser.add_argument("--vendor", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
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
        rebuild=args.rebuild,
    )
    print(
        "Jobs="
        f"{counts['jobs']} "
        f"skipped_existing_record={counts['skipped_existing_record']} "
        f"skipped_existing_bundle={counts['skipped_existing_bundle']} "
        f"skipped_missing_html={counts['skipped_missing_html']}"
    )


if __name__ == "__main__":
    main()

