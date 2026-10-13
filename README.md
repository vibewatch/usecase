# Customer Use Case Intelligence

Astro dashboard backed by a Python pipeline that turns vendor customer stories
(AWS / Microsoft / Google Cloud / Oracle / Snowflake / Databricks / Alibaba
Cloud / …) into a normalized, comparable dataset.

The pipeline discovers candidate URLs from vendor sitemaps, fetches HTML,
prepares extraction bundles, and lets an agent (this assistant) author one
JSON record per page using the [`case-study-extraction`](.agents/skills/case-study-extraction/SKILL.md)
skill. Records are merged, seeded into SQLite, and re-exported as the JSON
the dashboard reads.

For the full system design (data flow, component responsibilities, schemas,
extension recipes, and known design debt) see [ARCHITECTURE.md](ARCHITECTURE.md).

## Evidence, provenance, and scoring

Every generated record contains a source ledger (`source_references`) and a
field-to-source map (`field_sources`). Each source records its publisher, URL,
authority, source type, publication date and provenance, retrieval timestamp,
and the fields it supports. The use-case page exposes this ledger directly;
normalized attributes without a separately documented source are called out.

Publication dates are intentionally strict: only a date stated on the source
page or in documented publisher metadata appears as **Published**. Internet
Archive first captures, sitemap modification dates, and unverified legacy
dates remain available under `date_evidence` with their exact label and source,
but are never presented as publication dates.

Missing company attributes use a separate customer-level enrichment ledger,
[`data/company-enrichment.jsonl`](data/company-enrichment.jsonl). Existing
authored values are never overwritten. Headquarters region and employee-count
evidence must come from an opened source, not a search snippet; size is then
normalized as SMB (0–249), Mid-market (250–999), or Enterprise (1,000+).
Every enrichment source is added to the case source ledger and linked through
`field_sources`. Unresolved values render as **Not documented** rather than a
prominent `Unknown`.

Scores are rebuilt deterministically on every `data:seed`:

- **Evidence confidence (0–100%)**: source authority (25), claim traceability
  (25), direct evidence (20), publication-date provenance (10), source
  transparency (10), and implementation specificity (10).
- **Customer reference value (0–100)**: problem clarity (20), implementation
  depth (25), outcome specificity (20), quantified impact (25), and deployment
  scale (10).
- **Evidence stage (0–6)**: a compact card/sort signal based on problem,
  products, architecture, outcome, quantified impact, and confirmed date provenance.

These scores describe the evidence available in the cited sources. They are
not independent verification of vendor claims and do not predict guaranteed
ROI.

The deployed site also publishes the complete normalized dataset at
`/data.json` and the latest collected stories as RSS at `/feed.xml`.

## Solution depth

Each record carries a structured per-component view:

- `solution_components[]` — `{name, role, layer?}` per product/service that is
  actually part of the implementation. `layer` comes from
  `taxonomy.json → component_layers` (`Ingest` / `Compute` / `Storage` /
  `Serving` / `Orchestration` / `Governance`).
- `data_flow` — one paragraph tracing how data moves end-to-end.
- `integration_points[]` — external systems, upstream sources, downstream
  consumers.

`solution_summary` targets 600–1000 characters covering ingest → process →
store → serve. Older records that predate the structured fields render via a
fallback chip list of `products_used`. See
[`.agents/skills/case-study-extraction/SKILL.md`](.agents/skills/case-study-extraction/SKILL.md)
for the full extraction contract.

## Commands

```bash
npm install          # install Astro tooling
python3 -m pip install -r requirements.txt
npm run dev          # local dashboard at http://localhost:4321
npm run build        # astro check && astro build && pagefind --site dist → dist/

# Pipeline (Python 3)
npm run data:discover   # walk data/sources.json sitemaps/APIs → data/discovered_urls.jsonl
npm run data:fetch      # fetch raw content → data/raw_content/, append data/fetch_manifest.jsonl
npm run data:triage     # filter + date provenance (pre → post → metadata → dates) → data/triage.jsonl
npm run data:probe-fetch -- <url>  # probe/update Python fetch strategies for a hard host
npm run data:extract    # build prompt bundles for triage-kept pages in data/extract_jobs/{vendor}/
npm run data:enrich-companies # queue customer region/size research jobs
npm run data:enrich-dates     # queue publisher-date research jobs
npm run data:validate-enrichment # validate the company enrichment ledger
npm run data:merge      # fold data/records/**/*.json + samples → data/case-studies.merged.json
npm run data:partition  # assign records to collection weeks → data/weekly/** (+ stamp generated JSON)
npm run data:build      # merge → seed SQLite → export → partition
```

The dashboard imports `data/case-studies.generated.json`, so any rerun of
`npm run data:build` is picked up by the next `npm run dev` / `build`.

## Filtering before extraction

Extraction is the only expensive step, so every discovered story passes a
cheap, deterministic filter first (`pipeline/usecase_intel/triage.py`,
criteria in `pipeline/usecase_intel/config/triage.json`):

| Stage | Input | Drops |
|---|---|---|
| `pre` | discovery metadata | stories whose sitemap/API date predates the cutoff |
| `post` | fetched page text | old (page metadata/dateline), thin, non-English, off-topic, duplicate, or redirected-away pages |
| `metadata` | cached source HTML | backfills publication-specific JSON-LD, Open Graph/meta, itemprop, and `<time>` dates without replacing conflicting authoritative dates |
| `dates` | undated survivors | pages the Internet Archive first saw before the cutoff |
| extraction | the extractor itself | pages that turn out not to be customer stories, or not AI use cases (`--stage reject`) |

Current criteria: published **2023 or later**, **AI** topics (AI-native
vendors like OpenAI, Anthropic and LangChain are exempt from the topic check),
at least 300 words, English (or Chinese for `"language": "zh"` catalogs, whose
records are written in English). The extractor then keeps only stories where AI
is actually implemented — pure migration, infrastructure or analytics stories
are rejected. Survivors get a relevance score (topic depth,
quantified results, architecture detail, recency) and extraction takes them
highest-score first. Every decision and its reasons is in `data/triage.jsonl`
(latest row per URL wins), so drops are auditable and nothing is judged twice.
`python3 -m pipeline.usecase_intel.triage --stage summary` prints the funnel.

## Search, browsing and pagination

- **Search index** — `npm run build` runs [Pagefind](https://pagefind.app) over
  the built site. Each case page carries hidden filter values (vendor,
  industry, use case, technical area, outcome, year), card metadata and sort
  keys; the browser downloads only the index chunks a query needs, so search
  stays fast at thousands of stories.
- **`/explore/`** — full-text search, multi-select filters with live counts
  (OR within a group, AND across groups), sort by relevance / newest /
  maturity, numbered pagination, shareable URLs. Without JavaScript it shows
  the newest stories and links to the static pages below.
- **Static pages** — `/browse/` (all stories, newest first, 24 per page) and
  hubs per vendor, industry and use case (`/vendors/aws/`,
  `/industries/retail/2/`, …), generated at build time.

## Automation & publishing

- **Collection** — [`.github/workflows/usecase.yml`](.github/workflows/usecase.yml)
  runs four times a day (00/06/12/18 UTC, cap 40 records per run, model
  `gpt-5.4` by default) and on demand via *Run workflow*. It invokes
  the `UseCase Intel` agent (discover → triage → fetch → triage → extract →
  author up to `cap` records), rebuilds the data, validates the site build,
  and commits `data/records/**`, `data/weekly/**`, `data/triage.jsonl` and the
  URL/fetch ledgers. Requires the `COPILOT_PAT` and `USECASE_PAT` secrets.
- **Evidence enrichment** —
  [`.github/workflows/enrichment.yml`](.github/workflows/enrichment.yml) runs
  daily and on demand with a combined 1–40 job cap. It exits before invoking
  an agent when both queues are empty. The
  [`UseCase Enrichment`](.github/agents/usecase-enrichment.agent.md) agent
  researches missing company attributes and exact publisher-confirmed dates,
  appends only validated ledger entries, rebuilds the site, and commits the
    resulting evidence. Completed searches with no defensible value are recorded
    so later batches advance instead of retrying the same job; pass
    `--retry-researched` to the queue command for a deliberate recheck. It
    requires `COPILOT_PAT` and `USECASE_PAT`.
- **GitHub Pages** — [`.github/workflows/pages.yml`](.github/workflows/pages.yml)
  rebuilds and deploys the dashboard on every push to `main` that touches
  records or site code, which includes the daily collection commit. One-time
  setup: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
  The site is served at `https://usecase.genisisiq.com/` (Pages custom
  domain; DNS `CNAME usecase → vibewatch.github.io`). Links are
  base-path aware (`src/lib/paths.ts`), and `SITE_URL` / `BASE_PATH` are
  supplied by `actions/configure-pages`.

## Weekly storage

`npm run data:partition` writes the dataset into week-sized files that are
committed to the repository:

```
data/weekly/index.json            newest-first list of weeks + counts
data/weekly/2026/2026-W41.json    references (id, vendor, customer, URLs, dates,
                                  record path) for stories first collected that ISO week
data/weekly/undated.json          synthetic samples (no collection date)
```

A record's week is its earliest successful fetch in `data/fetch_manifest.jsonl`
(or the build date for brand-new records) and never changes afterwards — the
committed weekly files are the ledger. They hold references rather than full
copies, so `data/records/` stays the single source of record content.

## Adding records

End-to-end agent loop:

1. Add the vendor to [`data/sources.json`](data/sources.json) with a sitemap,
   index page(s), include `url_patterns`, and `exclude_patterns`.
2. `npm run data:discover` to populate `data/discovered_urls.jsonl`.
3. `npm run data:fetch` to mirror raw content and write the fetch manifest.
4. `npm run data:extract` to produce `data/extract_jobs/{vendor_slug}/{sha}.json`
  bundles (self-contained prompts with cleaned text + related article image
  candidates + the extraction skill + the taxonomy).
5. Open the bundle and write the structured record to
   `data/records/{vendor_slug}/{slug}.json` following the
   [`case-study-extraction`](.agents/skills/case-study-extraction/SKILL.md) skill.
6. `npm run data:build` to merge, seed SQLite, and refresh the dashboard JSON.

`npm run data:fetch` uses the full Python-native fetch chain by default: it
tries the project user agent, search-bot and browser header profiles, an
on-demand headless Chrome render for JavaScript-dependent pages, and then
reader/Wayback recovery. Downloads and rendered HTML are size-bounded, and
HTTP 429 responses honor `Retry-After` before moving to the next strategy.

## Diagram extraction

Use the `Diagram Extractor` custom agent when a fetched page, PDF, SVG, or image
contains an architecture/workflow diagram that should be converted to Mermaid.
Give it a local path, extract job path, or source URL, for example:

```text
Use Diagram Extractor on data/extract_jobs/<vendor>/<sha>.json and convert the
architecture image to Mermaid. Write outputs under data/diagrams/.
```

`npm run data:extract` stores article-scoped visual candidates in each bundle as
`related_images[]`, including image URLs, source type, local asset path, alt
text, captions, nearby context, dimensions, score, and `is_diagram_like`. By
default it attempts a source-diverse set of candidates until it has up to six
local assets beside the bundle under `data/extract_jobs/{vendor}/{sha}.assets/`;
pass `--image-assets-limit 0` to keep URLs only. Asset downloads use a short
timeout by default; tune it with `--image-timeout-seconds` for slower networks.
Low-value candidates are filtered by score before local asset download; the
default threshold is intentionally strict (`--image-min-score 8`) and can be
lowered when you want a wider run.
The score uses visible context plus image URL/file-name hints, so generic
backgrounds, heroes, banners, thumbnails, social cards, and Open Graph images are
filtered. Diagram-like candidates are strongly retained when hints include terms
such as architecture, workflow, topology, service map, dependency map, process
flow, sequence diagram, block diagram, ERD, UML, BPMN, swimlane, tech stack,
data lineage, or network topology. Non-diagram images also need useful hints
such as app, dashboard, screenshot, assistant, agent, GenAI, search,
recommendation, or analytics.
CSS `background-image` assets are included as low-confidence article imagery and
can be disabled with `--no-css-background-images`. The agent reads local assets
first, then visible labels, arrows, captions, SVG text, and nearby page context,
and returns Mermaid plus evidence and uncertainty notes. Generated diagram
outputs belong under `data/diagrams/` and are ignored by git.

## Repository shape

- `src/pages/index.astro` — home: hero search, latest arrivals, newest use
  cases, insight charts, industry × use-case heatmap, methodology.
- `src/pages/insights.astro` — evidence coverage, source concentration and
  bias indicators, use-case/outcome benchmarks, architecture-layer coverage,
  confirmed-date trends, ranked dimensions, and cross-tab heatmaps.
- `src/pages/explore.astro` — Pagefind-powered search with filters, sorting
  and pagination.
- `src/pages/browse/[...page].astro` — static paginated list of all stories.
- `src/pages/[facet]/` — hub index and paginated hub pages per vendor,
  industry and use case.
- `src/pages/cases/[slug].astro` — per-record detail page (metrics, layered
  solution architecture, evidence, related use cases); also carries the
  search-index filters, metadata and sort keys.
- `src/components/` — `CaseCard` (also the client-side card template),
  `CaseListing`, `Pagination`, `BarList`, `BenchmarkTable`.
- `src/scripts/cards.ts` — builds result cards in the browser from search metadata.
- `src/lib/` — `caseStudies.ts` data import, `analytics.ts` aggregations,
  `facets.ts` facet grouping/slugs/sorting, `weeks.ts` week grouping + card
  projection, `paths.ts` base-path-aware links, `vendors.ts` vendor marks,
  `types.ts` schema.
- `taxonomy.json` — canonical vocabulary for vendors / industries / technical
  areas / use cases / outcomes.
- `pipeline/usecase_intel/` — `discover`, `fetch`, `probe`, `clean`, `media`,
  `extract`, `merge_records`, `seed`, `scoring`, `export`, `partition`, plus `fetch_client`,
  `settings`, `utils`, and `config/host-strategies.json`.
- `requirements.txt` — Python extraction dependencies (`beautifulsoup4`,
  `playwright`, `pypdf`) used by the fetch/extract pipeline.
- `data/sources.json` — vendor source config (sitemaps, index pages, regex
  filters).
- `data/records/{vendor_slug}/{slug}.json` — authored records (tracked).
- `data/company-enrichment.jsonl` — append-only, customer-level region and
  company-size evidence (tracked).
- `data/weekly/` — weekly partitions of the dataset (tracked; see
  [Weekly storage](#weekly-storage)).
- `data/case-studies.sample.json` — synthetic seed records (`is_sample: true`).
- `data/case-studies.generated.json` — built artifact consumed by the
  dashboard (gitignored).
- `data/usecase_intel.sqlite` — built SQLite database (gitignored).
- `.agents/skills/` — agent skills. `case-study-extraction` is the active
  record-authoring contract; URL fetching now lives in Python.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system architecture: data flow,
  component boundaries, schemas, extension recipes, known design debt.
- `DESIGN.md` — external design-system reference (Miro) that informed the
  original dashboard styling. The current UI uses its own night/gradient theme
  defined in `src/styles/global.css`.