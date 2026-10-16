# Ingestion Pipeline & CI/CD Workflows

This guide covers the Python data pipeline (`pipeline/usecase_intel/`) and the automated GitHub Actions workflows (`.github/workflows/`) that continuously discover, triage, extract, enrich, analyze, and publish enterprise AI customer stories.

---

## 1. Pipeline Stages

### Stage 1: URL Discovery (`discover.py`)

```bash
npm run data:discover
# or target a single vendor:
python3 -m pipeline.usecase_intel.discover --vendor "Microsoft" --enough 200
```

- Reads [`data/sources.json`](../data/sources.json), which configures sitemaps, HTML/JSON index pages, `url_patterns` (inclusion regexes), and `exclude_patterns` per vendor.
- Walks sitemap indexes, child sitemaps, and index pages while deduplicating against `data/discovered_urls.jsonl`.
- Appends new candidate rows with discovery timestamps and any catalog/sitemap `lastmod` metadata.

### Stage 2: Multi-Strategy Fetch Recovery (`fetch.py` & `fetch_client.py`)

```bash
npm run data:fetch
# Probe a challenging host and persist the winning strategy:
npm run data:probe-fetch -- "https://www.snowflake.com/en/customers/..."
```

`FetchClient` executes a bounded, rate-limited recovery chain for every candidate URL:

1. **Origin HTTP Profiles** — Standard bot `User-Agent`, desktop Chrome headers, and search-crawler header profiles (`pipeline/usecase_intel/config/host-strategies.json`).
2. **Headless Chrome (`browser_fetch.py`)** — On-demand Playwright browser context for JavaScript-rendered SPAs or challenge-gated vendor pages.
3. **Jina Reader (`r.jina.ai`)** — Markdown/text extraction fallback when origin requests are blocked.
4. **Internet Archive Wayback Machine (`web.archive.org`)** — Historical snapshot recovery when origin and reader fail.

Every fetch writes content-addressed raw bytes to `data/raw_content/{vendor}/{sha256}.*` and appends a diagnostic row (`status`, `retrieval_source`, `profile`, `sha256`, `fetched_at`) to `data/fetch_manifest.jsonl`.

### Stage 3: Deterministic Triage (`triage.py`)

```bash
npm run data:triage
# View funnel summary across all stages:
python3 -m pipeline.usecase_intel.triage --stage summary
```

Before invoking an LLM agent, `triage.py` filters candidates through four deterministic stages configured in `pipeline/usecase_intel/config/triage.json`:

| Stage | Input | Filtering & Provenance Logic |
| :--- | :--- | :--- |
| **`pre`** | `discovered_urls.jsonl` | Drops URLs whose sitemap or catalog date predates the `2023-01-01` cutoff. |
| **`post`** | `raw_content/` | Drops pages that are too short (<300 words), off-topic (no AI/ML signal unless from an AI-native vendor), non-English (except `"language": "zh"` catalogs), redirected to generic landing pages, or dated before 2023. Computes a relevance priority score. |
| **`metadata`** | Cached HTML | Parses JSON-LD (`datePublished`), Open Graph (`article:published_time`), schema.org `itemprop`, and `<time>` tags to backfill verified publication dates. |
| **`dates`** | Undated survivors | Queries the Internet Archive CDX API; drops pages first archived before 2023 and records `wayback_first_capture` in `date_evidence`. |

### Stage 4: Prompt Bundle Assembly (`extract.py`, `clean.py`, `media.py`)

```bash
npm run data:extract
```

For every triage-kept page that does not yet have a record in `data/records/`:

- `clean.py` extracts the clean article title and body text from HTML, reader markdown, or PDF (`pypdf`).
- `media.py` scores and downloads up to 6 article-scoped architecture diagrams or product screenshots into `data/extract_jobs/{vendor}/{sha}.assets/`.
- `extract.py` writes a self-contained JSON bundle in `data/extract_jobs/{vendor}/{sha}.json` containing the cleaned text, date provenance, visual candidates, `taxonomy.json`, and `.agents/skills/case-study-extraction/SKILL.md`.

### Stage 5: Agent Extraction (`case-study-extraction`)

An extraction agent reads each bundle and follows [`.agents/skills/case-study-extraction/SKILL.md`](../.agents/skills/case-study-extraction/SKILL.md):

- Verifies the page is a genuine customer story where AI/ML is a core, implemented part of the solution (otherwise records a rejection via `triage.py --stage reject`).
- Normalizes industry, technical areas, use-case categories, outcome categories, and 6-layer `solution_components` (`Ingest`, `Compute`, `Storage`, `Serving`, `Orchestration`, `Governance`).
- Translates non-English stories (e.g., Chinese cloud stories from Alibaba Cloud, Tencent Cloud, Baidu AI Cloud, Huawei Cloud) into English while preserving verbatim original quotes in `evidence_quotes` and setting `"source_language": "zh"`.
- Writes the normalized JSON record to `data/records/{vendor_slug}/{slug}.json`.

### Stage 6: Provenance Enrichment (`company_enrichment.py` & `date_enrichment.py`)

```bash
npm run data:enrich-companies
npm run data:enrich-dates
npm run data:validate-enrichment
```

- **Company Enrichment**: Queues research jobs for customers missing `region` or `company_size`. Appends verified findings to `data/company-enrichment.jsonl` with primary source URLs, retrieval timestamps, and employee-band evidence (`SMB`: 0–249, `Mid-market`: 250–999, `Enterprise`: 1,000+).
- **Date Enrichment**: Inspects browser-rendered pages and publisher catalogs to recover missing publication dates without promoting sitemap/archive dates to `published_date`.

### Stage 7: Build, Partition & Multi-Dimensional Analytics (`npm run data:build`)

```bash
npm run data:build
```

Executes `merge_records` → `seed` (deterministic rubric scoring + SQLite upsert) → `export` → `partition` (immutable ISO weeks in `data/weekly/`) → `analytics` (`data/analytics.generated.json` + official vendor logo check).

---

## 2. Deterministic Scoring Rubrics (`scoring.py`)

Every record is scored deterministically during `npm run data:seed`:

### Customer Reference Value (`0–100`)

| Criterion | Max Points | What It Measures |
| :--- | :--- | :--- |
| **Problem Clarity** | `20` | Specificity and operational context of `business_problem`. |
| **Implementation Depth** | `25` | Named `products_used`, structured `solution_components` with layers, `data_flow`, and `integration_points`. |
| **Outcome Specificity** | `20` | Concrete operational outcomes and mapped `outcome_category` tags. |
| **Quantified Impact** | `25` | Count and diversity of numeric `metrics` (`%`, `x` multipliers, time/cost/volume units) and `evidence_quotes`. |
| **Deployment Scale** | `10` | Documented `company_size`, geographic `region`, and production maturity. |

### Evidence Confidence (`0–100%`)

| Criterion | Max Points | What It Measures |
| :--- | :--- | :--- |
| **Source Authority** | `25` | First-party vendor/customer or independent reporting authority in `source_references`. |
| **Claim Traceability** | `25` | Coverage of core fields in `field_sources`. |
| **Direct Evidence** | `20` | Verbatim `evidence_quotes` supporting claims and metrics. |
| **Date Provenance** | `10` | Page-confirmed or publisher-catalog publication date vs. fallback archive/modification evidence. |
| **Source Transparency** | `10` | Complete URL, publisher, retrieval timestamp, and source metadata. |
| **Implementation Specificity** | `10` | Concrete architectural components and technical clues. |

---

## 3. Automated GitHub Actions Workflows

| Workflow File | Schedule / Trigger | Purpose |
| :--- | :--- | :--- |
| [`.github/workflows/usecase.yml`](../.github/workflows/usecase.yml) | Every 6 hours (`00/06/12/18 UTC`) & manual dispatch | Runs the `UseCase Intel` agent end-to-end: discovers URLs, fetches pages, runs triage, extracts up to `cap` new records, runs `npm run data:build` (including `data:analytics` and logo verification), runs `npm run build`, and commits `data/records/**`, `data/weekly/**`, `data/triage.jsonl`, and `public/logos/vendors/**`. |
| [`.github/workflows/enrichment.yml`](../.github/workflows/enrichment.yml) | Daily & manual dispatch | Runs the `UseCase Enrichment` agent on queued company and publication-date research jobs, validates `data/company-enrichment.jsonl`, rebuilds the dataset, and commits enriched provenance. |
| [`.github/workflows/newsroom.yml`](../.github/workflows/newsroom.yml) | Scheduled & manual dispatch | Crawls first-party enterprise newsrooms for customer-published AI stories, triages candidates, and extracts qualified records. |
| [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) | Push to `main` touching `data/records/**`, `src/**`, `pipeline/**`, etc. | Runs `npm run data:build` and `npm run build` (including Pagefind indexing) and deploys the static site to GitHub Pages (`https://usecase.genisisiq.com/`). |
