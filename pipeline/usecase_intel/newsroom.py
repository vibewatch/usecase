"""Collect AI use cases that companies publish on their own websites.

Input is a private company list (e.g. a TSV of account names). Everything derived
from it — resolved domains, crawl ledgers, fetched pages, bundles — stays under
`data/private/` (gitignored). Only the resulting public stories become records.

Stages (`python3 -m pipeline.usecase_intel.newsroom <stage>`):
  resolve   company name -> official website + newsroom (LLM proposal, HTTP-verified)
  discover  robots.txt/sitemaps (and newsroom index pages) -> AI-related story URLs
  fetch     download candidates (parallel across companies, polite per host)
  triage    same AI / length / language / 2023+ filter as vendor stories
  bundle    extraction prompts with first-party guidance
  author    run the extraction skill on each bundle (Copilot CLI) -> data/records/
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import subprocess
import sys
import threading
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from .clean import content_to_text
from .discover import _parse_sitemap, _LinkExtractor
from .fetch_client import FetchClient
from .settings import TRIAGE_CONFIG_PATH
from .utils import load_jsonl, slugify

PRIVATE = Path("data/private")
COMPANIES_PATH = PRIVATE / "companies.json"
DISCOVERED_PATH = PRIVATE / "newsroom_discovered.jsonl"
MANIFEST_PATH = PRIVATE / "newsroom_manifest.jsonl"
TRIAGE_PATH = PRIVATE / "newsroom_triage.jsonl"
RAW_ROOT = PRIVATE / "raw"
JOBS_ROOT = PRIVATE / "jobs"
USER_AGENT = "UseCaseIntelBot/0.1 (+https://usecase.genisisiq.com)"
SINCE = "2023-01-01"

# A story URL must name AI in its path; content sections are preferred but not required.
AI_SLUG_RE = re.compile(
    r"(?:^|[/_.-])(?:ai|gen-?ai|generative-ai|artificial-intelligence|machine-learning|ml|llms?|chatgpt|openai|copilots?|"
    r"agentic|ai-agents?|gpt|gemini|watsonx|data-science|computer-vision|deep-learning|neural|intelligen[ct]e?-artificial|"
    r"intelligence-artificielle|ia|ia-generative|inteligencia-artificial|intelligenza-artificiale|kuenstliche-intelligenz|"
    r"kunstliche-intelligenz|generative|genai|ki)(?:$|[/_.-])",
    re.IGNORECASE,
)
SKIP_PATH_RE = re.compile(
    r"/(?:products?|shop|store|catalog|search|tag|tags|category|categories|author|careers?|jobs?|events?|webinars?|"
    r"privacy|legal|terms|cookie|login|account|cart|investors?/(?:financial|sec|stock))(?:/|$)|\.(?:pdf|jpg|png|zip)$",
    re.IGNORECASE,
)
CONTENT_SITEMAP_RE = re.compile(r"news|press|blog|stor(y|ies)|article|post|insight|media|newsroom|feature|innovation|en", re.I)
SKIP_SITEMAP_RE = re.compile(r"product|catalog|shop|store|image|video|categor|tag|author|location|dealer|job|career|sku|pdp|plp", re.I)
NON_ENGLISH_PATH_RE = re.compile(r"^/(?!en(?:[-_][a-z]{2})?/)[a-z]{2}(?:[-_][a-z]{2})?/", re.I)

MAX_SITEMAPS_PER_HOST = 60
MAX_URLS_PER_COMPANY = 120

_print_lock = threading.Lock()


def log(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_proxy(url: str) -> bool:
    return any(host in url for host in ("r.jina.ai/", "web.archive.org/"))


def _append(path: Path, row: dict[str, Any], lock: threading.Lock) -> None:
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def _copilot(prompt: str, model: str = "gpt-5.4", timeout: int = 900) -> str:
    result = subprocess.run(
        ["copilot", "-p", prompt, "-s", "--model", model, "--no-custom-instructions", "--no-ask-user", "--no-color", "--no-auto-update"],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout


def _json_block(text: str, opener: str = "[") -> Any:
    closer = "]" if opener == "[" else "}"
    match = re.search(re.escape(opener) + r".*" + re.escape(closer), text, re.S)
    return json.loads(match.group(0)) if match else None


# --- resolve -----------------------------------------------------------------

RESOLVE_PROMPT = """For each company below (names come from a CRM and may be abbreviated, upper-case, or a local legal entity), give the global corporate website and, if it exists, the corporate newsroom / press / stories site where the company publishes its own news.

Return ONLY a JSON array, no prose, no code fences:
[{"name": "<exactly as given>", "company": "<common company name>", "website": "https://...", "newsroom": "https://... or null"}]
Use null when you are not sure. Prefer the English global site.

Companies:
"""


def resolve(list_path: Path, batch_size: int = 40, workers: int = 4) -> None:
    with list_path.open(encoding="utf-8") as handle:
        names = [row["AccountEnglishName"].strip() for row in csv.DictReader(handle, delimiter="\t") if row.get("AccountEnglishName")]
    names = list(dict.fromkeys(names))
    existing = json.loads(COMPANIES_PATH.read_text(encoding="utf-8")) if COMPANIES_PATH.exists() else {}
    todo = [name for name in names if name not in existing]
    log(f"resolve: {len(names)} companies, {len(todo)} to resolve")

    def propose(batch: list[str]) -> list[dict[str, Any]]:
        best: list[dict[str, Any]] = []
        for _ in range(3):
            try:
                rows = _json_block(_copilot(RESOLVE_PROMPT + "\n".join(batch)))
            except Exception as exc:  # noqa: BLE001
                log(f"  resolve retry: {exc!r}")
                continue
            rows = [row for row in rows or [] if isinstance(row, dict) and row.get("name")]
            if len(rows) > len(best):
                best = rows
            if {row["name"] for row in rows} >= set(batch):
                break
        return best

    batches = [todo[k:k + batch_size] for k in range(0, len(todo), batch_size)]
    with ThreadPoolExecutor(workers) as pool:
        proposals = [row for rows in pool.map(propose, batches) for row in rows]

    client = FetchClient(user_agent=USER_AGENT, per_host_delay_seconds=0.5, cache_dir=None)

    def verify(url: Optional[str]) -> Optional[str]:
        if not url or not str(url).startswith("http"):
            return None
        try:
            result = client.fetch(url, use_cache=False)
        except Exception:  # noqa: BLE001
            return None
        if not result.status or result.status >= 400:
            return None
        final = result.final_url or url
        # Reader/archive fallbacks reach blocked sites; keep the site's own address.
        return url if _is_proxy(final) else final

    def check(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        website, newsroom = verify(row.get("website")), verify(row.get("newsroom"))
        return row["name"], {"company": row.get("company") or row["name"], "website": website, "newsroom": newsroom,
                             "proposed": {"website": row.get("website"), "newsroom": row.get("newsroom")}}

    with ThreadPoolExecutor(12) as pool:
        for name, info in pool.map(check, [row for row in proposals if row.get("name") in todo]):
            existing[name] = info
    PRIVATE.mkdir(parents=True, exist_ok=True)
    COMPANIES_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for info in existing.values() if info.get("website") or info.get("newsroom"))
    log(f"resolve: {ok}/{len(existing)} companies have a verified site -> {COMPANIES_PATH}")


def load_companies() -> dict[str, dict[str, Any]]:
    """Display name -> {"sites": [...]} for companies with at least one verified site."""
    raw = json.loads(COMPANIES_PATH.read_text(encoding="utf-8")) if COMPANIES_PATH.exists() else {}
    companies: dict[str, dict[str, Any]] = {}
    for info in raw.values():
        sites = companies.setdefault(info["company"], {"sites": []})["sites"]
        for url in (info.get("newsroom"), info.get("website")):
            if url and url not in sites:
                sites.append(url)
    return {name: info for name, info in companies.items() if info["sites"]}


# --- discover ----------------------------------------------------------------

def _registrable(host: str) -> str:
    parts = host.lower().split(".")
    # Good enough for corporate sites: keep 3 labels for ccTLD second levels (co.uk, com.au, ...).
    return ".".join(parts[-3:] if len(parts) >= 3 and len(parts[-2]) <= 3 and len(parts[-1]) == 2 else parts[-2:])


def _robots(client: FetchClient, origin: str) -> urllib.robotparser.RobotFileParser:
    parser = urllib.robotparser.RobotFileParser()
    try:
        result = client.fetch(urljoin(origin, "/robots.txt"), use_cache=False)
        lines = result.body.decode("utf-8", errors="replace").splitlines() if result.status == 200 else []
    except Exception:  # noqa: BLE001
        lines = []
    parser.parse(lines)
    return parser


def _wanted(url: str, domains: set[str], robots: dict[str, urllib.robotparser.RobotFileParser]) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except ValueError:  # malformed links (e.g. bad IPv6 literals) in third-party markup
        return False
    if not parsed.scheme.startswith("http") or _registrable(host) not in domains:
        return False
    path = parsed.path or "/"
    if not AI_SLUG_RE.search(path) or SKIP_PATH_RE.search(path) or NON_ENGLISH_PATH_RE.match(path):
        return False
    rules = robots.get(f"{parsed.scheme}://{parsed.netloc}")
    return rules is None or rules.can_fetch(USER_AGENT, url)


def discover_company(name: str, sites: list[str], seen: set[str], lock: threading.Lock) -> int:
    client = FetchClient(user_agent=USER_AGENT, per_host_delay_seconds=1.0, cache_dir=None)
    origins = list(dict.fromkeys(f"{urlparse(s).scheme}://{urlparse(s).netloc}" for s in sites))
    domains = {_registrable(urlparse(s).hostname or "") for s in sites}
    robots = {origin: _robots(client, origin) for origin in origins}
    found: dict[str, Optional[str]] = {}

    # 1. Sitemaps (from robots.txt, else the conventional locations), content sitemaps first.
    for origin in origins:
        queue = list(dict.fromkeys((robots[origin].site_maps() or []) + [urljoin(origin, "/sitemap.xml"), urljoin(origin, "/sitemap_index.xml")]))
        fetched = 0
        while queue and fetched < MAX_SITEMAPS_PER_HOST:
            sitemap = queue.pop(0)
            try:
                result = client.fetch(sitemap, use_cache=False)
            except Exception:  # noqa: BLE001
                continue
            fetched += 1
            if result.status != 200:
                continue
            nested, pages = _parse_sitemap(result.body)
            nested = [n for n in nested if not SKIP_SITEMAP_RE.search(urlparse(n).path)]
            queue += sorted(nested, key=lambda n: 0 if CONTENT_SITEMAP_RE.search(urlparse(n).path) else 1)
            for url, lastmod in pages:
                if (lastmod is None or lastmod >= SINCE) and _wanted(url, domains, robots):
                    found.setdefault(url, lastmod)

    # 2. Newsroom / site index pages (also catches sites without usable sitemaps).
    for site in sites:
        for page in dict.fromkeys([site, urljoin(site, "/news"), urljoin(site, "/newsroom"), urljoin(site, "/stories")]):
            try:
                result = client.fetch(page, use_cache=False)
            except Exception:  # noqa: BLE001
                continue
            if result.status != 200:
                continue
            base = page if _is_proxy(result.final_url or "") else (result.final_url or page)
            body = result.body.decode("utf-8", errors="replace")
            extractor = _LinkExtractor(base)
            try:
                extractor.feed(body)
            except Exception:  # noqa: BLE001
                pass
            # Reader-proxy fallbacks return markdown, whose links are not <a href> tags.
            markdown_links = re.findall(r"https?://[^\s)\]\"'<>]+", body)
            for url in extractor.links + markdown_links:
                url = url.split("#")[0]
                if _wanted(url, domains, robots):
                    found.setdefault(url, None)

    # Newest first, capped; unknown dates after dated ones.
    ranked = sorted(found.items(), key=lambda item: (item[1] is not None, item[1] or ""), reverse=True)[:MAX_URLS_PER_COMPANY]
    added = 0
    for url, lastmod in ranked:
        with lock:
            if url in seen:
                continue
            seen.add(url)
        _append(DISCOVERED_PATH, {"url": url, "vendor": name, "lastmod": lastmod, "source": "newsroom", "discovered_at": _now()}, lock)
        added += 1
    log(f"  {name}: {len(found)} AI-path urls, +{added} new")
    return added


def discover(workers: int = 12, only: Optional[str] = None) -> None:
    companies = load_companies()
    if only:
        companies = {k: v for k, v in companies.items() if only.lower() in k.lower()}
    rows = load_jsonl(DISCOVERED_PATH)
    seen = {row["url"] for row in rows}
    # Resume: companies already crawled (they have rows, or a recorded empty result) are skipped.
    done = {row["vendor"] for row in rows} | {row["company"] for row in load_jsonl(PRIVATE / "newsroom_crawled.jsonl")}
    if not only:
        companies = {k: v for k, v in companies.items() if k not in done}
    lock = threading.Lock()

    def run(item: tuple[str, dict[str, Any]]) -> int:
        name, info = item
        try:
            added = discover_company(name, info["sites"], seen, lock)
        except Exception as exc:  # noqa: BLE001 - one bad site must not stop the crawl
            log(f"  {name}: discovery failed: {exc!r}")
            return 0
        _append(PRIVATE / "newsroom_crawled.jsonl", {"company": name, "added": added, "at": _now()}, lock)
        return added

    log(f"discover: {len(companies)} companies to crawl")
    with ThreadPoolExecutor(workers) as pool:
        total = sum(pool.map(run, companies.items()))
    log(f"discover: +{total} urls across {len(companies)} companies -> {DISCOVERED_PATH}")


# --- fetch -------------------------------------------------------------------

def fetch(workers: int = 12) -> None:
    done = {row["url"] for row in load_jsonl(MANIFEST_PATH) if row.get("status") == 200}
    by_company: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(DISCOVERED_PATH):
        if row["url"] not in done:
            by_company.setdefault(row["vendor"], []).append(row)
    lock = threading.Lock()
    counts = {"ok": 0, "error": 0}

    def run(rows: list[dict[str, Any]]) -> None:
        client = FetchClient(user_agent=USER_AGENT, per_host_delay_seconds=1.0, cache_dir=None)
        for row in rows:
            entry: dict[str, Any] = {"vendor": row["vendor"], "url": row["url"], "fetched_at": _now()}
            try:
                result = client.fetch(row["url"], use_cache=False)
                if not result.body:
                    raise ValueError("empty response body")
                folder = RAW_ROOT / slugify(row["vendor"])
                folder.mkdir(parents=True, exist_ok=True)
                raw_path = folder / f"{result.sha256}.html"
                raw_path.write_bytes(result.body)
                entry.update(raw_path=str(raw_path), status=result.status, sha256=result.sha256, content_type=result.content_type,
                             final_url=result.final_url, retrieval_source=result.retrieval_source, profile=result.profile, error=None)
                counts["ok"] += 1
            except Exception as exc:  # noqa: BLE001
                entry.update(raw_path=None, status=0, sha256=None, content_type=None, error=f"{type(exc).__name__}: {exc}")
                counts["error"] += 1
            _append(MANIFEST_PATH, entry, lock)

    log(f"fetch: {sum(len(r) for r in by_company.values())} urls across {len(by_company)} companies")
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(run, by_company.values()))
    log(f"fetch: ok={counts['ok']} error={counts['error']} -> {MANIFEST_PATH}")


# --- triage ------------------------------------------------------------------

def triage_pages() -> None:
    from .triage import Criteria, enrich_dates, triage

    criteria = Criteria.load(TRIAGE_CONFIG_PATH)
    counts = triage(stage="post", criteria=criteria, discovered_path=DISCOVERED_PATH, manifest_path=MANIFEST_PATH,
                    output_path=TRIAGE_PATH, sources_path=Path("/nonexistent"))
    log("triage post: " + " ".join(f"{k}={v}" for k, v in counts.most_common()))
    dated = enrich_dates(criteria=criteria, output_path=TRIAGE_PATH)
    log("triage dates: " + " ".join(f"{k}={v}" for k, v in dated.most_common()))


# --- bundle & author ---------------------------------------------------------

FIRST_PARTY_GUIDANCE = """

## First-party sources (company websites)

This page was published on the website of the company that adopted the technology (its newsroom, blog, or press release), not by a technology vendor.

- Step 0 still applies. The page qualifies only when it describes a concrete, implemented AI use case by a named organization — the company adopting AI in its operations, products or services, or delivering an AI solution for a named client. Thought leadership, opinion or trend pieces, event recaps, earnings, ESG or hiring news, generic AI strategy statements, partnership or investment announcements without a concrete implementation, and AI product marketing without implementation detail do not qualify: return the `not_an_ai_use_case` (or `not_a_customer_story`) object.
- `customer_name`: the organization that adopted the AI (usually the publishing company).
- `vendor`: the primary external AI or cloud technology provider explicitly named as powering the solution — use the exact `taxonomy.json` vendor name when it matches (e.g. `Microsoft`, `Google Cloud`, `AWS`, `OpenAI`, `NVIDIA`). If no provider is named, or the solution was built in-house, use `In-house`.
- Add `"source_type": "company"` to the record.
"""


def bundle() -> None:
    from .extract import extract_jobs
    from .settings import EXTRACTION_SKILL_PATH

    skill = PRIVATE / "first-party-skill.md"
    skill.write_text(EXTRACTION_SKILL_PATH.read_text(encoding="utf-8") + FIRST_PARTY_GUIDANCE, encoding="utf-8")
    counts = extract_jobs(manifest_path=MANIFEST_PATH, jobs_root=JOBS_ROOT, skill_path=skill, taxonomy_path=Path("taxonomy.json"),
                          discovered_path=DISCOVERED_PATH, triage_path=TRIAGE_PATH, image_assets_limit=0)
    log("bundle: " + " ".join(f"{k}={v}" for k, v in counts.items()))


def author(workers: int = 6, model: str = "gpt-5.4", limit: Optional[int] = None) -> None:
    from .models import normalize_record
    from .settings import RECORDS_ROOT
    from .triage import reject

    existing = {json.loads(p.read_text(encoding="utf-8")).get("source_url", "").rstrip("/").lower() for p in RECORDS_ROOT.glob("*/*.json")}
    rejected = {row["url"] for row in load_jsonl(TRIAGE_PATH) if any(str(r).startswith("extractor:") for r in row.get("reasons", []))}
    jobs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(JOBS_ROOT.glob("*/*.json"))]
    jobs = [job for job in jobs if job["source_url"].rstrip("/").lower() not in existing and job["source_url"] not in rejected]
    jobs.sort(key=lambda job: float(job.get("triage_score") or 0), reverse=True)
    if limit:
        jobs = jobs[:limit]
    lock = threading.Lock()
    counts = {"authored": 0, "rejected": 0, "failed": 0}
    log(f"author: {len(jobs)} bundles")

    def run(job: dict[str, Any]) -> None:
        url = job["source_url"]
        for _attempt in range(2):
            try:
                record = _json_block(_copilot(job["prompt"], model=model), "{")
            except Exception:  # noqa: BLE001
                record = None
            if not isinstance(record, dict):
                continue
            if record.get("not_a_customer_story") or record.get("not_an_ai_use_case"):
                kind = "not_ai_use_case" if record.get("not_an_ai_use_case") else "not_a_customer_story"
                with lock:
                    reject(url, f"{kind}: {record.get('reason', '')}", output_path=TRIAGE_PATH, vendor=job["vendor"])
                    counts["rejected"] += 1
                return
            record["source_url"] = url
            record["source_type"] = "company"
            if not record.get("published_date") or record["published_date"] == "unknown":
                record["published_date"] = job.get("published_date") or "unknown"
            record["vendor"] = (record.get("vendor") or "In-house").strip()
            try:
                normalize_record(record, 0)
            except ValueError as exc:
                log(f"  invalid record {url}: {exc}")
                continue
            vendor_slug = slugify(record["vendor"])
            slug = slugify(record.get("slug") or f"{vendor_slug}-{record['customer_name']}")
            if not slug.startswith(vendor_slug + "-"):
                slug = f"{vendor_slug}-{slug}"
            with lock:
                folder = RECORDS_ROOT / vendor_slug
                folder.mkdir(parents=True, exist_ok=True)
                path, n = folder / f"{slug}.json", 2
                while path.exists():
                    path, n = folder / f"{slug}-{n}.json", n + 1
                record["slug"], record["id"] = path.stem, path.stem
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                counts["authored"] += 1
            log(f"  + {record['customer_name']} ({record['vendor']}) {path}")
            return
        with lock:
            counts["failed"] += 1
        log(f"  failed {url}")

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(run, jobs))
    log("author: " + " ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="stage", required=True)
    p = sub.add_parser("resolve"); p.add_argument("list", type=Path)
    p = sub.add_parser("discover"); p.add_argument("--only"); p.add_argument("--workers", type=int, default=12)
    p = sub.add_parser("fetch"); p.add_argument("--workers", type=int, default=12)
    sub.add_parser("triage")
    sub.add_parser("bundle")
    p = sub.add_parser("author"); p.add_argument("--workers", type=int, default=6); p.add_argument("--model", default="gpt-5.4"); p.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.stage == "resolve":
        resolve(args.list)
    elif args.stage == "discover":
        discover(args.workers, args.only)
    elif args.stage == "fetch":
        fetch(args.workers)
    elif args.stage == "triage":
        triage_pages()
    elif args.stage == "bundle":
        bundle()
    elif args.stage == "author":
        author(args.workers, args.model, args.limit)
