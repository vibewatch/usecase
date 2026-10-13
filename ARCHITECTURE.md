# System Architecture

This document describes **how** Customer Use Case Intelligence is built. For
the operational quickstart and command list see [README.md](README.md); this
file is the reference for anyone (human or agent) extending the system.

## 1. Goal in one paragraph

Turn vendor "customer story" pages (AWS / Microsoft / Google Cloud / Oracle /
Snowflake / Databricks / Alibaba Cloud / …) into a single, normalized,
queryable dataset so we can compare deployments across vendors, industries,
and use cases. The output is a static Astro dashboard plus a SQLite database
backed by per-record JSON files checked into the repo.

## 2. System context

```mermaid
flowchart LR
  vendors[(Vendor sites<br/>sitemaps + HTML)]
  ext[(External readers<br/>r.jina.ai · web.archive.org)]
  pipeline[Python pipeline<br/>pipeline/usecase_intel/]
  agent((Agent / human author))
  records[(data/records/**/*.json<br/>tracked)]
  db[(SQLite<br/>data/usecase_intel.sqlite)]
  json[(data/case-studies.generated.json)]
  astro[Astro dashboard<br/>src/]
  user((Reader))

  vendors --> pipeline
  ext --> pipeline
  pipeline --> agent
  agent --> records
  records --> db
  db --> json
  json --> astro
  astro --> user
```

Three runtimes cooperate by writing files into `data/`:

| Runtime | Where | What it does | Why this runtime |
| ------- | ----- | ------------ | ---------------- |
| **Python pipeline** | `pipeline/usecase_intel/` | Sitemap discovery, HTTP fetch, header/browser/reader/Wayback fallback fetch, HTML→text, prompt bundle assembly, SQLite seeding, JSON export | One batch entry point with deterministic manifests and no manual fetch side path |
| **Astro dashboard** | `src/` | Static-site build of one index + N detail pages over the dataset | File-based routing, zero client JS by default, builds in <2 s |

`fetch.py` is the canonical batch entry point. `FetchClient` first uses the
configured project `User-Agent`, then can retry per-host profile strategies,
render the page in headless Chrome, and use reader/Wayback fallbacks while
still writing the same raw HTML + manifest
contract.

## 3. End-to-end data flow

A single record's journey from a vendor page to the dashboard:

```mermaid
flowchart TD
  src[data/sources.json<br/>vendor → sitemap, index, regex filters]
  disc[data/discovered_urls.jsonl<br/>append-only, deduped]
  raw[data/raw_content/&lcub;vendor&rcub;/&lcub;sha256&rcub;.*]
  manifest[data/fetch_manifest.jsonl<br/>append-only]
  job[data/extract_jobs/&lcub;vendor&rcub;/&lcub;sha256&rcub;.json<br/>self-contained prompt bundle]
  rec[data/records/&lcub;vendor&rcub;/&lcub;slug&rcub;.json<br/>authored, tracked]
  merged[data/case-studies.merged.json<br/>built]
  db[(data/usecase_intel.sqlite<br/>built)]
  gen[data/case-studies.generated.json<br/>built, consumed by Astro]
  weekly[data/weekly/&lcub;year&rcub;/&lcub;YYYY-Www&rcub;.json<br/>tracked, week ledger]
  dash[dist/index.html + dist/cases/&lcub;slug&rcub;/ + browse/hub pages]
  triage[data/triage.jsonl<br/>tracked, keep/drop + score]
  pf[dist/pagefind/<br/>chunked search index]

  src -- discover.py --> disc
  disc -- triage.py pre --> triage
  disc -- fetch.py skips drops --> raw
  fetch.py --> manifest
  raw -- triage.py post + metadata + dates --> triage
  triage -- keep, by score --> job
  raw -- extract.py + clean.py --> job
  job -- "agent reads & authors" --> rec
  rec -- merge_records.py --> merged
  merged -- seed.py + scoring.py + storage.py --> db
  db -- export.py --> gen
  gen -- partition.py --> weekly
  manifest -. first fetch date .-> weekly
  gen -- astro build --> dash
  dash -- pagefind --> pf
```

Every arrow is **idempotent**: rerunning a step skips inputs already
processed (by URL, by SHA, by record id). That makes the whole pipeline
resumable — kill it mid-run, fix a bug, rerun.

### Why each stage exists

- **discover** isolates URL enumeration from fetching. A 415-URL Databricks
  sitemap is cheap to walk; fetching 415 pages is not. Keeping them separate
  lets us re-filter / re-cap candidates without re-fetching.
- **fetch** is single-threaded with per-host delay and an always-on fallback
  chain. Lightweight HTTP/header attempts run first; headless Chrome is launched
  only when they fail, before external reader/archive recovery. Responses are
  size-bounded, 429 retries honor `Retry-After`, and raw bytes are written by SHA
  so identical bodies dedupe naturally on disk.
- **clean/media → extract** turns fetched content into a self-contained prompt bundle:
  source URL, cleaned text, article-scoped visual candidates with local assets,
  the taxonomy, and the extraction SKILL.md inlined. The bundle is the **agent
  contract** — anyone (or any agent) can read it without further context.
- **records** are authored once per page and committed. They are the source
  of truth.
- **merge → seed → export** is deterministic projection: take the authored
  records, fold in samples, normalize, score, store, dump back as a single
  JSON for the dashboard.
- **triage** filters before the only expensive step. `pre` drops URLs whose
  discovery date predates the cutoff; `post` judges fetched text (publish
  date, length, language, topic, duplicates, redirects) and scores survivors;
  `dates` asks the Internet Archive when undated survivors first appeared;
  the extractor itself can reject non-stories (`--stage reject`). Criteria
  live in `config/triage.json`; decisions are an append-only ledger.
- **partition** assigns each record to the ISO week it was first collected
  (earliest successful fetch, else build date), writes committed weekly files
  under `data/weekly/` (references, not copies), and stamps `collected_at` /
  `collected_week` onto the generated JSON. Existing assignments are read back
  from the weekly files, so a record never changes week.
- **search** — after `astro build`, Pagefind indexes every case page
  (`data-pagefind-body`) with filter values, card metadata and sort keys.
  `/explore/` queries it in the browser, loading only the chunks a query
  needs; `/browse/` and the facet hubs are static paginated fallbacks.

## 4. Agent-in-the-loop design (the unusual part)

Most extraction pipelines call an LLM API in step 4 and write JSON to disk.
This one **stops at the prompt bundle** and lets the agent (the current
conversation) read the bundle and write the JSON file by hand.

Why:

- **No API key, no provider lock-in.** The bundle is a plain JSON file; any
  capable agent or human can fulfil it.
- **Full evidence trail.** The agent quotes the page back into
  `evidence_quotes` while writing the record, so reviewers can verify each
  claim without re-fetching.
- **Taxonomy enforcement happens at author time, not as a post-hoc filter.**
  The bundle inlines `taxonomy.json`, so the author picks legal categories
  from the same vocabulary the dashboard understands.
- **Cheap regression**: a corrupt extraction is fixed by editing one
  `data/records/…/{slug}.json`; nothing else has to rerun until
  `npm run data:build`.

The downside: extraction throughput is bounded by the agent. This is a
deliberate trade-off — the dataset prizes signal-to-noise over volume.

## 5. Component-level breakdown

### Python pipeline (`pipeline/usecase_intel/`)

| Module | Responsibility | Key invariants |
| ------ | -------------- | -------------- |
| [`settings.py`](pipeline/usecase_intel/settings.py) | Shared path and runtime defaults for command modules | One place for data paths, skill/taxonomy paths, user agent, delay, and host strategy config |
| [`utils.py`](pipeline/usecase_intel/utils.py) | Small shared helpers: slugify, JSONL load, and JSON load/write | Keeps command modules thin and consistent |
| [`fetch_client.py`](pipeline/usecase_intel/fetch_client.py) | `FetchClient`: stdlib `urllib.request`, per-host rate limit, bounded responses, 429 backoff, optional disk cache by URL SHA, and header/browser/reader/Wayback recovery | Single-threaded; never bursts; sets `User-Agent` from `sources.json`; fallbacks are always enabled |
| [`browser_fetch.py`](pipeline/usecase_intel/browser_fetch.py) | Lazy Playwright/Chrome renderer for JavaScript-dependent or challenge-gated pages | Reuses one browser per process, isolates each page in a fresh context, blocks heavy media, bounds rendered HTML, and records `retrieval_source=browser` |
| [`discover.py`](pipeline/usecase_intel/discover.py) | Walk sitemap index → child sitemaps → urls. Walk vendor "index pages" for `<a href>` candidates. Apply include/exclude regexes. Cap with `--enough` early-exit. | Output is append-only JSONL; reruns dedupe against existing rows |
| [`fetch.py`](pipeline/usecase_intel/fetch.py) | For each unfetched URL in `discovered_urls.jsonl`, fetch and write `raw_content/{vendor}/{sha256}.*` plus a `fetch_manifest.jsonl` line | Skip if URL already in manifest with `status == 200` unless `--refresh`; records `retrieval_source` and `profile` for diagnostics |
| [`clean.py`](pipeline/usecase_intel/clean.py) | `content_to_text(bytes) → (title, body, method)`. Uses BeautifulSoup for HTML main-content cleanup, pypdf for PDFs, and stdlib fallbacks for malformed HTML/plain text | One Python text extraction path for origin HTML, reader text, archived HTML, and PDFs |
| [`media.py`](pipeline/usecase_intel/media.py) | `extract_related_images(bytes) → related_images[]` and `materialize_related_images(...)`. Discovers article `img`/`picture`/`source`, low-confidence CSS background images, inline SVG, and metadata images; scores visible context plus decoded URL/file-name hints, filters low-value candidates, and requires useful hints for non-diagram images before attempting a bounded local asset plan | Agents can inspect local `local_path` images instead of reparsing HTML or fetching remote assets by hand; failed downloads remain annotated with `asset_error` and do not consume the asset budget |
| [`extract.py`](pipeline/usecase_intel/extract.py) | Read manifest, run `clean` + `media`, assemble prompt bundle `{vendor, source_url, sha256, title, raw_path, content_type, retrieval_source, profile, extraction_method, related_images, prompt, created_at}` | Each bundle is self-sufficient: inlines SKILL.md + taxonomy.json + cleaned text, date provenance, retrieval time, and local article visual assets |
| [`probe.py`](pipeline/usecase_intel/probe.py) | Probe origin profiles, headless browser, reader, and Wayback for hard URLs; optionally update the host strategy map | Uses the same public fetch attempt API as `FetchClient` |
| [`models.py`](pipeline/usecase_intel/models.py) | `load_records(path) → list[dict]` with `normalize_record` validation | Validates record shape plus source references and field-to-source ids; legacy records receive a conservative primary-story reference |
| [`scoring.py`](pipeline/usecase_intel/scoring.py) | Deterministic evidence-confidence, customer-reference-value, and evidence-stage rubrics with criterion-level breakdowns | Confidence measures source/evidence quality, not field completeness; value and confidence stay separate |
| [`storage.py`](pipeline/usecase_intel/storage.py) | `initialize_database`, `upsert_records`. Schema: `case_studies` (1 row per record) + `case_study_values` (KV table for multi-value fields keyed by `kind`) | All multi-value fields have a single `MULTI_VALUE_FIELDS` mapping; `raw_json` stores the canonical record |
| [`merge_records.py`](pipeline/usecase_intel/merge_records.py) | Walk `data/records/**/*.json`, optionally fold in samples, dedupe by `id`, attach matching date provenance from triage, write a single array | Date provenance is attached only when the ledger date exactly matches the authored date |
| [`seed.py`](pipeline/usecase_intel/seed.py) | `enrich_scores` + `upsert_records` | Recomputes every score and breakdown on every build so stale authored scores cannot survive |
| [`export.py`](pipeline/usecase_intel/export.py) | Round-trip records out of SQLite, reattaching multi-value lists via the KV table | Order is `vendor, customer_name` for deterministic diffs |

### Astro dashboard (`src/`)

| File | Responsibility |
| ---- | -------------- |
| [`src/pages/index.astro`](src/pages/index.astro) | Product positioning, audience/workflow guidance, latest records, market insights, methodology, and JSON/RSS access |
| [`src/pages/insights.astro`](src/pages/insights.astro) | Decision-oriented analytics: evidence coverage, source bias/concentration, median segment benchmarks, architecture coverage, confirmed-date trends, ranked dimensions, and heatmaps |
| [`src/pages/cases/[slug].astro`](src/pages/cases/[slug].astro) | Compact per-record research brief with grouped outcome, solution, architecture, evidence, related records, and a folded score/provenance workspace |
| [`src/pages/data.json.ts`](src/pages/data.json.ts) | Static downloadable export of the complete normalized dataset |
| [`src/pages/feed.xml.ts`](src/pages/feed.xml.ts) | RSS feed ordered by collection time for update notifications |
| [`src/layouts/BaseLayout.astro`](src/layouts/BaseLayout.astro) | Site chrome. Banner is dynamic: real vs sample counts come from `caseStudies` so the UI never lies |
| [`src/lib/caseStudies.ts`](src/lib/caseStudies.ts) | The single import point for the dataset (`data/case-studies.generated.json`). If you want to read records anywhere in `src/`, import from here |
| [`src/lib/analytics.ts`](src/lib/analytics.ts) | Pure aggregation helpers: `uniqueSorted`, `flattenValues`, `countValues`, `topValues`, `buildMatrix`, `averageConfidence`, `maturityDistribution`, `formatPercent`, `formatDate` (defensive — unparseable dates fall through to the raw string), `isParseableDate` |
| [`src/lib/types.ts`](src/lib/types.ts) | `CaseStudyRecord` and dashboard view models. **The TypeScript schema is the single source of truth that has to stay in sync with `models.py` and `storage.py`.** |
| [`src/styles/global.css`](src/styles/global.css) | All styling. Hand-rolled CSS; no Tailwind. Global width, gutter, spacing, type-scale, radius, section, panel, and card tokens define a compact standard shared by every page; case details add only research-brief-specific grouping. |

The dashboard intentionally has no client-side data fetching. The full
dataset is inlined at build time, so every page is a static HTML file in
`dist/`.

### Agent skills (`.agents/skills/`)

| Skill | Role |
| ----- | ---- |
| [`case-study-extraction`](.agents/skills/case-study-extraction/SKILL.md) | The contract for step 4 (record authoring). Inlined into every `data/extract_jobs/**/*.json` bundle so the prompt is portable. |

## 6. Key contracts

### `CaseStudyRecord` (the record schema)

Defined in [`src/lib/types.ts`](src/lib/types.ts) and validated in
[`models.py`](pipeline/usecase_intel/models.py). Mirror them when changing
either side.

```ts
interface SolutionComponent {
  name: string;                // exact product name as written in source
  role: string;                // one-line role in this specific deployment
  layer?: string;              // taxonomy.component_layers value
}

interface SourceReference {
  id: string;
  title: string;
  publisher: string;
  url: string;
  source_type: string;
  authority: string;
  published_date: string;
  published_date_source: string;
  retrieved_at: string;
  supports: string[];
}

interface DateEvidence {
  date: string;
  type: string;                 // confirmed publication, first archive, modified, or unverified
  publisher: string;
  url: string;
  authority: string;
}

interface CaseStudyRecord {
  id: string;                    // stable; record path of truth
  slug: string;                  // URL slug; must be unique
  vendor: string;                // from taxonomy.vendors
  customer_name: string;
  industry: string;              // from taxonomy.industries
  region: string;
  company_size: string;          // "Enterprise" | "Mid-market" | "SMB" | "Public sector" | "Unknown"
  business_problem: string;
  solution_summary: string;      // 600–1000 chars; covers ingest → process → store → serve
  products_used: string[];       // flat list; mirrors solution_components[].name
  solution_components?: SolutionComponent[];   // structured per-component view (new)
  data_flow?: string;            // optional end-to-end narrative (new)
  integration_points?: string[]; // optional external systems / upstream / downstream (new)
  technical_area: string[];      // from taxonomy.technical_areas
  use_case_category: string[];   // from taxonomy.use_case_categories
  business_outcome: string;
  outcome_category: string[];    // from taxonomy.outcome_categories
  metrics: string[];             // raw quantitative claims with units
  architecture_clues: string[];  // free-form bag for short technical notes
  source_url: string;
  published_date: string;        // ISO date or "unknown"
  published_date_source?: string;
  source_references?: SourceReference[];
  field_sources?: Record<string, string[]>;
  date_evidence?: DateEvidence[];
  confidence_score: number;      // 0–1 evidence quality
  confidence_breakdown?: ScoreCriterion[];
  maturity_score: number;        // 0–6 compact evidence stage
  value_score?: number;          // 0–100 customer reference value
  value_breakdown?: ScoreCriterion[];
  evidence_quotes: string[];     // verbatim spans backing the extraction
  is_sample?: boolean;           // true for synthetic seeds
}
```

The optional fields (`solution_components`, `data_flow`, `integration_points`)
give solution depth without breaking older records: the dashboard falls back
to the flat `products_used` chip list when `solution_components` is absent,
and simply hides the data-flow / integration sections when empty.
`normalize_record` also supplies a conservative primary-story source reference
for legacy records while deliberately leaving company size, region, and
industry without separate attribution.

`merge_records` applies the publication-date policy across the whole dataset:
page dates and documented publisher catalog dates remain `published_date`;
Internet Archive first captures and unverified legacy dates move to
`date_evidence`. Sorting may use that weaker evidence, but the UI labels it
explicitly and never calls it a publication date.

### `data/sources.json` (vendor source config)

```jsonc
{
  "user_agent": "UseCaseIntelBot/0.1 (+…)",
  "default_delay_seconds": 1.0,
  "sources": [
    {
      "vendor": "Databricks",
      "sitemaps":  ["https://www.databricks.com/en-customer-assets/sitemap/sitemap-index.xml"],
      "index_pages": [],
      "url_patterns":    ["^https://www\\.databricks\\.com/customers/[^/]+/?$"],
      "exclude_patterns":["/(gen-ai|your-ai|champions-program|solutions-accelerator-general|all)/?$"]
    }
  ]
}
```

### `data/fetch_manifest.jsonl` (one line per attempt)

```json
{"vendor":"Oracle","url":"…","final_url":"…","raw_path":"data/raw_content/oracle/<sha>.html",
 "status":200,"sha256":"…","content_type":"text/html; charset=utf-8",
 "retrieval_source":"origin","profile":"desktop-chrome",
 "fetched_at":"2026-05-16T…","from_cache":false,"error":null}
```

### `host-strategies.json` (fetch fallback memory)

Per-host best-known fetch strategy so future Python fetches skip the profile probe.
Stored at `pipeline/usecase_intel/config/host-strategies.json`. See entries
for `www.databricks.com` and `www.snowflake.com` for the two
patterns we use: **happy path** (`strategy: <profile>`, optional `note`) and
**known SPA / known-blocker** (`strategy: null` with a `note` describing
why).

### `taxonomy.json` (controlled vocabulary)

10 vendors · 13 industries · 15 technical areas · 15 use case categories ·
8 outcome categories · 6 component layers (`Ingest`, `Compute`, `Storage`,
`Serving`, `Orchestration`, `Governance`). Authoring outside this list is a
soft error today (not yet enforced — see §9).

## 7. Storage and tracking policy

| Path | Tracked? | Why |
| ---- | -------- | --- |
| `data/sources.json` | yes | Source config — code-like |
| `data/case-studies.sample.json` | yes | Synthetic seeds; small, useful as fixtures |
| `data/records/**/*.json` | yes | Authored records are the source of truth |
| `data/discovered_urls.jsonl` | no | Easily regenerable; grows large |
| `data/raw_content/` | no | Easily refetched; can be large |
| `data/fetch_manifest.jsonl` | no | Per-machine fetch log |
| `data/extract_jobs/` | no | Derived bundles |
| `data/case-studies.merged.json` | no | Build artifact |
| `data/case-studies.generated.json` | no | Build artifact (dashboard input) |
| `data/usecase_intel.sqlite` | no | Build artifact |
| `data/http_cache/` | no | Pipeline fetch cache |

Rule of thumb: anything that can be regenerated by running the pipeline is
gitignored.

## 8. Extension recipes

### Add a new vendor

1. Append a `sources[]` entry to `data/sources.json` with sitemaps, index
   pages (optional), `url_patterns`, and `exclude_patterns`.
2. Add the vendor name to `taxonomy.json` → `vendors`.
3. Run `npm run data:discover -- --vendor "<name>"`. Inspect
   `data/discovered_urls.jsonl` — adjust regexes until candidates look
   right.
4. Run `npm run data:fetch -- --vendor "<name>"`.
5. Run `npm run data:extract -- --vendor "<name>"`.
6. For each bundle: open it, read the cleaned text, follow the
   [`case-study-extraction`](.agents/skills/case-study-extraction/SKILL.md)
   skill, write `data/records/<vendor_slug>/<slug>.json`.
7. `npm run data:build` to rebuild the database and the dashboard JSON.

### Add a dashboard view

1. Pure aggregation goes in [`src/lib/analytics.ts`](src/lib/analytics.ts)
   as a new function over `CaseStudyRecord[]`.
2. Wire it into [`src/pages/index.astro`](src/pages/index.astro) as a new
   `<section>`. Reuse the `.surface-card`, `.feature-grid`, `.bar-list`,
   `.matrix-table` classes from `global.css` for visual consistency.
3. No build wiring needed — Astro picks up new sections automatically.

### Add a taxonomy category

1. Append to the relevant array in `taxonomy.json`.
2. Existing records pick it up automatically when the agent re-authors with
   the new bundle; old records keep their old categories until re-extracted.

## 9. Known design debt

Things the current implementation does **not** do, knowingly:

- **Generated ledgers are disposable.** If manifest or raw-content formats change,
  rerun discovery/fetch/extract instead of preserving compatibility shims.
- **No taxonomy validation at extraction time.** `models.py` checks field
  shape but not values. Free-form drift (e.g. `Cloud Native` vs
  `Cloud-Native`) silently leaks into the dashboard's facet selector and
  coverage matrix. Adding `validate_against_taxonomy(record, taxonomy)` in
  `models.py` is a small change and is on the roadmap.
- **`extract.py` truncates at 18000 chars.** Long pages may lose the
  metrics / architecture paragraphs near the end. Switching to a
  "head + tail" or "paragraph-aware" trim is queued.
- **Legacy records usually have one source.** Confidence measures whether that
  source is authoritative, transparent, and linked to each claim; it does not
  penalize a story merely for having one publisher. Additional customer or
  independent sources remain an optional enrichment signal.

These are intentional gaps, not unknowns. See the matching section in
[README.md](README.md) for the user-visible status.

## 10. Diagram of how files map to disk

```
usecase/
├── README.md                              quickstart
├── ARCHITECTURE.md                        this file
├── DESIGN.md                              external Miro design-system reference
├── taxonomy.json                          controlled vocabulary
├── astro.config.mjs · tsconfig.json · package.json
├── public/                                static assets served as-is
├── src/
│   ├── layouts/BaseLayout.astro
│   ├── lib/{analytics,caseStudies,types}.ts
│   ├── pages/index.astro · cases/[slug].astro
│   └── styles/global.css
├── pipeline/usecase_intel/                Python pipeline (one module per stage)
├── .agents/skills/case-study-extraction/  extraction contract
└── data/
    ├── sources.json                       vendor source config (tracked)
    ├── records/<vendor>/<slug>.json       authored records (tracked)
    ├── case-studies.sample.json           seeds (tracked)
    ├── discovered_urls.jsonl              build artifact
    ├── raw_content/<vendor>/<sha>.*       build artifact
    ├── fetch_manifest.jsonl               build artifact
    ├── extract_jobs/<vendor>/<sha>.json   build artifact
    ├── case-studies.merged.json           build artifact
    ├── case-studies.generated.json        dashboard input (build artifact)
    └── usecase_intel.sqlite               build artifact
```

Track changes to this file when you change any of: the data flow (§3), the
component responsibilities (§5), the schema (§6), or the tracking policy
(§7). The point of the doc is to stay accurate.
