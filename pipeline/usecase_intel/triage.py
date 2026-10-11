"""Filter discovered stories before the expensive extraction step.

Two stages, both cheap and deterministic:

* ``pre``  — runs on discovery metadata before fetching. Drops URLs whose
  sitemap/API date is older than the cutoff (``lastmod`` is a last-modified
  date, so ``lastmod < since`` proves the story was published before it).
* ``post`` — runs on fetched page text. Detects the publish date, then drops
  thin, non-English, off-topic, duplicate and (per vendor) non-story pages.
  Survivors get a relevance score; extraction takes them highest-score first.

Decisions are appended to ``data/triage.jsonl`` (tracked, latest row per URL
wins) so a page is judged once and every drop can be audited. Criteria live in
``pipeline/usecase_intel/config/triage.json``.

Row schema::

    {"url", "vendor", "stage": "pre"|"post", "decision": "keep"|"drop",
     "reasons": [str], "score": float|null, "published_date": "YYYY-MM-DD"|null,
     "title": str|null, "words": int|null, "fingerprint": str|null, "decided_at": ISO8601}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .clean import content_to_text
from .settings import (
    DISCOVERED_URLS_PATH,
    FETCH_MANIFEST_PATH,
    RECORDS_ROOT,
    SOURCES_PATH,
    TRIAGE_CONFIG_PATH,
    TRIAGE_PATH,
)
from .utils import load_json, load_jsonl

STOPWORDS = frozenset(
    "the and of to in a for with is on that by as are from this its it was we our their they be has have an at or".split()
)
MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"), ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
META_DATE_RE = re.compile(
    r"""(?:article:published_time|datePublished|date_published|publish[_-]?date|"""
    r"""dc\.date|og:published_time|pubdate)["']?\s*(?:content\s*=|:|=)\s*["']\s*([^"'<>]{6,40})""",
    re.IGNORECASE,
)
TIME_TAG_RE = re.compile(r"<time[^>]*datetime=[\"']([^\"']{6,40})", re.IGNORECASE)
MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})")
US_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")  # 09/22/2025 (Drupal-style metadata)
MONTH_DAY_YEAR_RE = re.compile(rf"\b({MONTH_NAMES})\.?\s+(\d{{1,2}}),?\s*(20\d{{2}})\b", re.IGNORECASE)
DAY_MONTH_YEAR_RE = re.compile(rf"\b(\d{{1,2}})\s+({MONTH_NAMES})\.?,?\s+(20\d{{2}})\b", re.IGNORECASE)
# Text dates are only trusted in a dateline ("Published May 2024", "Posted: 1 May 2024"),
# never free-floating — "founded in March 2000" is not a publish date.
DATELINE_RE = re.compile(
    rf"\b(?:published|posted|updated|date)\b[:\s]*(?:on\s+)?((?:\d{{1,2}}\s+)?(?:{MONTH_NAMES})\.?\s+(?:\d{{1,2}},?\s*)?20\d{{2}})",
    re.IGNORECASE,
)
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"


@dataclass
class Criteria:
    since: str
    min_words: int
    min_stopword_ratio: float
    topic_res: list[re.Pattern[str]]
    min_distinct: int
    min_hits: int
    metric_re: re.Pattern[str]
    arch_res: list[re.Pattern[str]]
    weights: dict[str, Any]
    wayback: bool

    @classmethod
    def load(cls, path: Path, since_override: Optional[str] = None) -> "Criteria":
        config = load_json(path, None)
        if not isinstance(config, dict):
            raise SystemExit(f"{path}: missing or invalid triage config")

        def words(terms: list[str]) -> list[re.Pattern[str]]:
            return [re.compile(rf"\b(?:{term})\b", re.IGNORECASE) for term in terms]

        topic = config["topic"]
        depth = config["depth"]
        return cls(
            since=since_override or config["since"],
            min_words=int(config["min_words"]),
            min_stopword_ratio=float(config["min_english_stopword_ratio"]),
            topic_res=words(topic["terms"]),
            min_distinct=int(topic["min_distinct_terms"]),
            min_hits=int(topic["min_total_hits"]),
            metric_re=re.compile(depth["metric_pattern"], re.IGNORECASE),
            arch_res=words(depth["architecture_terms"]),
            weights=config["score_weights"],
            wayback=bool(config.get("wayback_date_fallback", True)),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(year: int, month: int, day: int = 1) -> Optional[str]:
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def parse_date_value(value: str) -> Optional[str]:
    """Normalize one date string (ISO, US numeric, or month-name forms) to YYYY-MM-DD."""
    if match := ISO_DATE_RE.search(value):
        return _iso(int(match[1]), int(match[2]), int(match[3]))
    if match := US_DATE_RE.search(value):
        return _iso(int(match[3]), int(match[1]), int(match[2]))
    if match := MONTH_DAY_YEAR_RE.search(value):
        return _iso(int(match[3]), MONTHS[match[1].lower()], int(match[2]))
    if match := DAY_MONTH_YEAR_RE.search(value):
        return _iso(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
    if match := re.search(rf"\b({MONTH_NAMES})\.?\s+(20\d{{2}})\b", value, re.IGNORECASE):
        return _iso(int(match[2]), MONTHS[match[1].lower()])
    return None


def detect_published_date(raw_html: str, text: str) -> Optional[str]:
    """Best-effort publish date: structured metadata first, then a dateline near the top."""
    meta = [parse_date_value(value) for value in META_DATE_RE.findall(raw_html) + TIME_TAG_RE.findall(raw_html)]
    meta = [value for value in meta if value and "2000" <= value[:4] <= "2100"]
    if meta:
        return min(meta)
    match = DATELINE_RE.search(text[:2000])
    return parse_date_value(match[1]) if match else None


_last_wayback_call = 0.0
# True when the latest wayback_first_capture() returned None because the archive
# was unreachable (as opposed to the page never having been archived).
_last_lookup_failed = False


def _archive_json(url: str, timeout: float) -> Any:
    global _last_wayback_call
    wait = 1.0 - (time.monotonic() - _last_wayback_call)
    if wait > 0:
        time.sleep(wait)
    _last_wayback_call = time.monotonic()
    with urlopen(Request(url, headers={"User-Agent": "UseCaseIntelBot/0.1"}), timeout=timeout) as response:
        return json.loads(response.read() or b"null")


def _stamp_to_iso(stamp: str) -> Optional[str]:
    return _iso(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])) if len(stamp) >= 8 and stamp[:8].isdigit() else None


def wayback_first_capture(url: str, timeout: float = 30.0, attempts: int = 3) -> Optional[str]:
    """Date the Internet Archive first saw `url` (an upper bound on its publish date).

    Uses the availability API (closest snapshot to 2000-01-01, i.e. the earliest)
    and falls back to the CDX API; retries with backoff because both are flaky.
    Returns None when the page was never archived or the archive is unreachable;
    `_last_lookup_failed` tells the two apart.
    """
    global _last_lookup_failed
    queries = [
        "https://archive.org/wayback/available?" + urlencode({"url": url, "timestamp": "20000101"}),
        f"{WAYBACK_CDX}?" + urlencode({"url": url, "output": "json", "fl": "timestamp", "limit": 1, "filter": "statuscode:200"}),
    ]
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        for index, query in enumerate(queries):
            try:
                payload = _archive_json(query, timeout)
            except Exception as exc:  # noqa: BLE001 - archive outages must not stop triage
                last_error = exc
                continue
            if index == 0:
                snapshot = ((payload or {}).get("archived_snapshots") or {}).get("closest") or {}
                if snapshot.get("timestamp"):
                    _last_lookup_failed = False
                    return _stamp_to_iso(str(snapshot["timestamp"]))
            elif isinstance(payload, list):
                _last_lookup_failed = False
                return _stamp_to_iso(str(payload[1][0])) if len(payload) >= 2 and payload[1] else None
        time.sleep(2 ** attempt)
    print(f"  wayback lookup failed {url}: {last_error}", file=sys.stderr)
    _last_lookup_failed = True
    return None


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()[:3000]
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _url_key(url: str) -> str:
    return url.strip().rstrip("/").lower()


def evaluate_text(
    *,
    title: str,
    text: str,
    raw_html: str,
    lastmod: Optional[str],
    criteria: Criteria,
    story_cues: Optional[re.Pattern[str]],
    vendor_options: Optional[dict[str, Any]] = None,
    date_fallback: Optional[Callable[[], Optional[str]]] = None,
) -> dict[str, Any]:
    """Score one fetched page. Returns decision fields (without url/vendor/stage).

    `vendor_options` (from data/sources.json): `always_on_topic` skips the topic
    check for AI-native vendors; `lastmod_is_published` trusts the discovery date
    (e.g. AWS's API `sortDate`) as the publish date. `date_fallback` is called
    only for otherwise-passing pages with no known date (Wayback first capture).
    """
    options = vendor_options or {}
    reasons: list[str] = []
    tokens = re.findall(r"[A-Za-z']+", text.lower())
    words = len(tokens)
    published = detect_published_date(raw_html, text)
    published_source = "page" if published else None
    if not published and lastmod and options.get("lastmod_is_published"):
        published, published_source = lastmod, "discovery"

    if words < criteria.min_words:
        reasons.append(f"thin_{words}_words")
    elif sum(1 for token in tokens if token in STOPWORDS) / max(words, 1) < criteria.min_stopword_ratio:
        reasons.append("not_english")

    haystack = f"{title}\n{text}"
    if story_cues is not None and not story_cues.search(haystack):
        reasons.append("not_a_customer_story")

    hits = [len(pattern.findall(haystack)) for pattern in criteria.topic_res]
    distinct = sum(1 for count in hits if count)
    total_hits = sum(hits)
    if not options.get("always_on_topic") and (distinct < criteria.min_distinct or total_hits < criteria.min_hits):
        reasons.append(f"off_topic_{distinct}_terms_{total_hits}_hits")

    # Date: the publish date when known; otherwise lastmod is an upper bound; as a
    # last resort (only for pages that pass everything else) the archive's first capture.
    if not published and not reasons and not (lastmod and lastmod < criteria.since) and date_fallback:
        published = date_fallback()
        published_source = "wayback_first_capture" if published else None
    if published and published < criteria.since:
        reasons.append(f"published_before_{criteria.since}")
    elif not published and lastmod and lastmod < criteria.since:
        reasons.append(f"modified_before_{criteria.since}")

    weights = criteria.weights
    metrics = len(criteria.metric_re.findall(text))
    architecture = sum(1 for pattern in criteria.arch_res if pattern.search(text))
    year = (published or "")[:4]
    score = (
        distinct * float(weights["topic_distinct"])
        + min(total_hits, int(weights["topic_hits_cap"])) * float(weights["topic_hits"])
        + min(metrics, int(weights["metrics_cap"])) * float(weights["metrics"])
        + min(architecture, int(weights["architecture_cap"])) * float(weights["architecture"])
        + float(weights["recency_by_year"].get(year, 0))
        - (float(weights["unknown_date_penalty"]) if not published else 0.0)
    )
    return {
        "decision": "drop" if reasons else "keep",
        "reasons": reasons,
        "score": round(score, 2),
        "published_date": published,
        "published_source": published_source,
        "title": title or None,
        "words": words,
        "fingerprint": _fingerprint(text),
    }


def load_decisions(path: Path = TRIAGE_PATH) -> dict[str, dict[str, Any]]:
    """Latest triage row per URL."""
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        url = row.get("url")
        if isinstance(url, str):
            latest[url] = row
    return latest


def _record_urls(records_root: Path) -> set[str]:
    urls: set[str] = set()
    for path in records_root.glob("*/*.json"):
        try:
            source = json.loads(path.read_text(encoding="utf-8")).get("source_url")
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(source, str):
            urls.add(_url_key(source))
    return urls


@dataclass
class VendorRules:
    story_cues: Optional[re.Pattern[str]]
    include: list[re.Pattern[str]]
    options: dict[str, Any]


def load_vendor_rules(sources_path: Path) -> dict[str, VendorRules]:
    config = load_json(sources_path, {}) or {}
    rules: dict[str, VendorRules] = {}
    for source in config.get("sources", []):
        cues = source.get("story_cues")
        rules[source["vendor"]] = VendorRules(
            story_cues=re.compile(cues, re.IGNORECASE) if cues else None,
            include=[re.compile(pattern) for pattern in source.get("url_patterns", [])],
            options={key: source[key] for key in ("always_on_topic", "lastmod_is_published") if key in source},
        )
    return rules


def _last_segment(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1].lower()


def _redirected_off_story(row: dict[str, Any], rules: Optional[VendorRules]) -> bool:
    """True when the page redirected away from its story, e.g. a removed story sent to a listing page.

    Locale/host/tracking redirects keep the story slug (`/customers/x` ->
    `/en/customers/x?_p_lc=1`) and are fine.
    """
    final = str(row.get("final_url") or "")
    if not final or _url_key(final) == _url_key(row["url"]):
        return False
    if _last_segment(final) == _last_segment(row["url"]):
        return False
    return not (rules and any(pattern.search(final) for pattern in rules.include))


def triage(
    *,
    stage: str,
    criteria: Criteria,
    discovered_path: Path = DISCOVERED_URLS_PATH,
    manifest_path: Path = FETCH_MANIFEST_PATH,
    records_root: Path = RECORDS_ROOT,
    sources_path: Path = SOURCES_PATH,
    output_path: Path = TRIAGE_PATH,
    vendor_filter: Optional[str] = None,
    rejudge: bool = False,
) -> Counter[str]:
    decisions = load_decisions(output_path)
    done = _record_urls(records_root)
    lastmods = {row["url"]: row.get("lastmod") for row in load_jsonl(discovered_path) if row.get("url")}
    counts: Counter[str] = Counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = output_path.open("a", encoding="utf-8")

    def emit(row: dict[str, Any]) -> None:
        # Written immediately so an interrupted multi-hour run keeps its progress.
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()
        counts[row["decision"]] += 1
        for reason in row["reasons"]:
            counts["reason:" + re.sub(r"_\d+.*$|\s.*$", "", reason)] += 1

    def wanted(url: str, vendor: str) -> bool:
        if vendor_filter and vendor.lower() != vendor_filter.lower():
            return False
        if _url_key(url) in done:
            counts["skip_has_record"] += 1
            return False
        previous = decisions.get(url)
        if previous and not rejudge and (previous["stage"] == "post" or previous["stage"] == stage):
            counts["skip_already_judged"] += 1
            return False
        return True

    try:
        if stage == "pre":
            for row in load_jsonl(discovered_path):
                url, vendor = row.get("url"), row.get("vendor")
                if not url or not vendor or not wanted(url, vendor):
                    continue
                lastmod = row.get("lastmod")
                too_old = bool(lastmod) and lastmod < criteria.since
                emit(
                    {
                        "url": url,
                        "vendor": vendor,
                        "stage": "pre",
                        "decision": "drop" if too_old else "keep",
                        "reasons": [f"modified_before_{criteria.since}"] if too_old else [],
                        "score": None,
                        "published_date": None,
                        "title": row.get("title"),
                        "words": None,
                        "fingerprint": None,
                        "decided_at": _now(),
                    }
                )
        else:
            vendor_rules = load_vendor_rules(sources_path)
            # Fingerprints of pages already kept, so later copies are dropped as duplicates.
            seen = {
                row["fingerprint"]: url
                for url, row in decisions.items()
                if row.get("decision") == "keep" and row.get("fingerprint")
            }
            latest: dict[str, dict[str, Any]] = {}
            for row in load_jsonl(manifest_path):
                if isinstance(row.get("url"), str):
                    latest[row["url"]] = row
            for row in latest.values():
                url, vendor = row["url"], row.get("vendor", "")
                if row.get("status") != 200 or not row.get("raw_path"):
                    continue
                previous = decisions.get(url)
                if previous and previous.get("decision") == "drop" and previous["stage"] == "pre" and not rejudge:
                    continue
                if not wanted(url, vendor):
                    continue
                rules = vendor_rules.get(vendor)
                base = {"url": url, "vendor": vendor, "stage": "post"}
                if _redirected_off_story(row, rules):
                    emit({**base, "decision": "drop", "reasons": [f"redirected_to {row.get('final_url')}"],
                          "score": None, "published_date": None, "title": None, "words": None,
                          "fingerprint": None, "decided_at": _now()})
                    continue
                raw_path = Path(row["raw_path"])
                if not raw_path.exists():
                    counts["skip_missing_raw"] += 1
                    continue
                body = raw_path.read_bytes()
                try:
                    title, text, _method = content_to_text(body, content_type=str(row.get("content_type") or ""))
                except Exception as exc:  # noqa: BLE001 - one bad file must not stop the batch
                    print(f"  parse failed {url}: {exc}", file=sys.stderr)
                    counts["skip_parse_error"] += 1
                    continue
                result = evaluate_text(
                    title=title,
                    text=text,
                    raw_html=body[:400_000].decode("utf-8", errors="replace"),
                    lastmod=lastmods.get(url),
                    criteria=criteria,
                    story_cues=rules.story_cues if rules else None,
                    vendor_options=rules.options if rules else None,
                    date_fallback=None,  # archive lookups run in the separate `dates` stage
                )
                if result["decision"] == "keep":
                    original = seen.get(result["fingerprint"])
                    if original and original != url:
                        result["decision"] = "drop"
                        result["reasons"] = [f"duplicate_of {original}"]
                    else:
                        seen[result["fingerprint"]] = url
                emit({**base, **result, "decided_at": _now()})
                if sum(counts[key] for key in ("keep", "drop")) % 100 == 0:
                    print(f"  triaged {counts['keep'] + counts['drop']} (keep={counts['keep']})", file=sys.stderr, flush=True)
    finally:
        out.close()
    return counts


def enrich_dates(
    *,
    criteria: Criteria,
    output_path: Path = TRIAGE_PATH,
    vendor_filter: Optional[str] = None,
    limit: Optional[int] = None,
    max_consecutive_failures: int = 5,
) -> Counter[str]:
    """Date undated kept pages by their first Internet Archive capture.

    Runs after `post` so content triage never blocks on the archive. Pages first
    archived before the cutoff are dropped; the rest gain their recency bonus.
    Stops early after repeated archive failures — re-run later to finish.
    """
    counts: Counter[str] = Counter()
    weights = criteria.weights
    pending = [
        row
        for row in load_decisions(output_path).values()
        if row.get("stage") == "post"
        and row.get("decision") == "keep"
        and not row.get("published_date")
        and not row.get("date_checked")
        and (not vendor_filter or row.get("vendor", "").lower() == vendor_filter.lower())
    ]
    pending.sort(key=lambda row: float(row.get("score") or 0), reverse=True)
    if limit is not None:
        pending = pending[:limit]
    print(f"Dating {len(pending)} undated kept page(s) via the Internet Archive", file=sys.stderr, flush=True)

    failures = 0
    with output_path.open("a", encoding="utf-8") as out:
        for row in pending:
            if failures >= max_consecutive_failures:
                print("  archive unreachable; stopping (re-run --stage dates later)", file=sys.stderr, flush=True)
                counts["deferred"] = len(pending) - counts["dated"] - counts["never_archived"]
                break
            first_seen = wayback_first_capture(row["url"], timeout=15.0, attempts=2)
            if first_seen is None and _last_lookup_failed:
                failures += 1
                continue
            failures = 0
            updated = {**row, "date_checked": True, "decided_at": _now()}
            if first_seen:
                counts["dated"] += 1
                updated["published_date"] = first_seen
                updated["published_source"] = "wayback_first_capture"
                if first_seen < criteria.since:
                    updated["decision"] = "drop"
                    updated["reasons"] = [f"published_before_{criteria.since}"]
                    counts["drop"] += 1
                else:
                    bonus = float(weights["recency_by_year"].get(first_seen[:4], 0)) + float(weights["unknown_date_penalty"])
                    updated["score"] = round(float(row.get("score") or 0) + bonus, 2)
            else:
                counts["never_archived"] += 1  # likely new: keep as-is
            out.write(json.dumps(updated, ensure_ascii=False) + "\n")
            out.flush()
    return counts


def summarize(path: Path = TRIAGE_PATH, records_root: Path = RECORDS_ROOT) -> None:
    decisions = load_decisions(path)
    done = _record_urls(records_root)
    table: dict[str, Counter[str]] = {}
    for url, row in decisions.items():
        bucket = "has_record" if _url_key(url) in done else f"{row['stage']}_{row['decision']}"
        table.setdefault(row["vendor"], Counter())[bucket] += 1
    columns = ["pre_drop", "pre_keep", "post_drop", "post_keep", "has_record"]
    print(f"{'vendor':16s}" + "".join(f"{column:>12s}" for column in columns))
    for vendor in sorted(table):
        print(f"{vendor:16s}" + "".join(f"{table[vendor][column]:>12d}" for column in columns))
    totals = Counter()
    for counter in table.values():
        totals.update(counter)
    print(f"{'TOTAL':16s}" + "".join(f"{totals[column]:>12d}" for column in columns))
    print(
        f"Extraction queue (post_keep without record): {totals['post_keep']}; "
        f"awaiting fetch (pre_keep): {totals['pre_keep']}"
    )


def reject(url: str, reason: str, output_path: Path = TRIAGE_PATH, vendor: str = "") -> None:
    """Record an extraction-time rejection (e.g. the page is not a customer story)."""
    if not vendor:
        vendor = next((row.get("vendor", "") for row in load_jsonl(DISCOVERED_URLS_PATH) if row.get("url") == url), "")
    row = {
        "url": url,
        "vendor": vendor,
        "stage": "post",
        "decision": "drop",
        "reasons": [f"extractor: {reason}"],
        "score": None,
        "published_date": None,
        "title": None,
        "words": None,
        "fingerprint": None,
        "decided_at": _now(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Rejected {url}: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter discovered stories before extraction.")
    parser.add_argument("--stage", choices=["pre", "post", "dates", "summary", "reject"], required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max pages to date (--stage dates)")
    parser.add_argument("--url", type=str, default=None, help="URL to reject (--stage reject)")
    parser.add_argument("--reason", type=str, default="not a customer story", help="Rejection reason (--stage reject)")
    parser.add_argument("--config", type=Path, default=TRIAGE_CONFIG_PATH)
    parser.add_argument("--since", type=str, default=None, help="Override the config date cutoff (YYYY-MM-DD)")
    parser.add_argument("--vendor", type=str, default=None)
    parser.add_argument("--rejudge", action="store_true", help="Re-evaluate URLs that already have a decision")
    parser.add_argument("--output", type=Path, default=TRIAGE_PATH)
    args = parser.parse_args()

    if args.stage == "summary":
        summarize(args.output)
        return
    if args.stage == "reject":
        if not args.url:
            raise SystemExit("--stage reject requires --url")
        reject(args.url, args.reason, args.output, vendor=args.vendor or "")
        return
    if args.stage == "dates":
        counts = enrich_dates(
            criteria=Criteria.load(args.config, args.since),
            output_path=args.output,
            vendor_filter=args.vendor,
            limit=args.limit,
        )
        print("Triage dates: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        return
    counts = triage(
        stage=args.stage,
        criteria=Criteria.load(args.config, args.since),
        vendor_filter=args.vendor,
        rejudge=args.rejudge,
        output_path=args.output,
    )
    print(
        f"Triage {args.stage}: keep={counts['keep']} drop={counts['drop']} "
        + " ".join(f"{key}={value}" for key, value in sorted(counts.items()) if key not in ("keep", "drop"))
    )


if __name__ == "__main__":
    main()
