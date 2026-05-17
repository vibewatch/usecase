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

## Current dataset

66 records · 58 extracted from live vendor pages · 8 synthetic seeds.

| Vendor        | Records |
| ------------- | ------- |
| Alibaba Cloud | 15      |
| Databricks    | 15      |
| Oracle        | 13      |
| Microsoft     | 10      |
| Google Cloud  | 9       |
| AWS           | 4       |
| Seed samples  | 8       |

Average confidence ≈ 0.97, average maturity ≈ 5.9 / 6.

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
npm run build        # astro check && astro build → dist/

# Pipeline (Python 3)
npm run data:discover   # walk data/sources.json sitemaps → data/discovered_urls.jsonl
npm run data:fetch      # fetch raw content → data/raw_content/, append data/fetch_manifest.jsonl
npm run data:probe-fetch -- <url>  # probe/update Python fetch strategies for a hard host
npm run data:extract    # build prompt bundles in data/extract_jobs/{vendor}/
npm run data:merge      # fold data/records/**/*.json + samples → data/case-studies.merged.json
npm run data:build      # merge → seed SQLite → export data/case-studies.generated.json
```

The dashboard imports `data/case-studies.generated.json`, so any rerun of
`npm run data:build` is picked up by the next `npm run dev` / `build`.

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
tries the project user agent, known per-host profile strategies, and
reader/wayback recovery before giving up.

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
pass `--image-assets-limit 0` to keep URLs only. CSS `background-image` assets
are included as low-confidence article imagery and can be disabled with
`--no-css-background-images`. The agent reads local assets first, then visible
labels, arrows, captions, SVG text, and nearby page context, and returns Mermaid
plus evidence and uncertainty notes. Generated diagram outputs belong under
`data/diagrams/` and are ignored by git.

## Repository shape

- `src/pages/index.astro` — dashboard (top use cases, products, outcomes,
  maturity, vendor × use-case and industry × use-case coverage matrices,
  filterable record table).
- `src/pages/cases/[slug].astro` — per-record detail page.
- `src/lib/` — `caseStudies.ts` data import, `analytics.ts` aggregations,
  `types.ts` schema.
- `taxonomy.json` — canonical vocabulary for vendors / industries / technical
  areas / use cases / outcomes.
- `pipeline/usecase_intel/` — `discover`, `fetch`, `probe`, `clean`, `media`,
  `extract`, `merge_records`, `seed`, `scoring`, `export`, plus `fetch_client`,
  `settings`, `utils`, and `config/host-strategies.json`.
- `requirements.txt` — Python extraction dependencies (`beautifulsoup4`,
  `pypdf`) used by the fetch/extract pipeline.
- `data/sources.json` — vendor source config (sitemaps, index pages, regex
  filters).
- `data/records/{vendor_slug}/{slug}.json` — authored records (tracked).
- `data/case-studies.sample.json` — synthetic seed records (`is_sample: true`).
- `data/case-studies.generated.json` — built artifact consumed by the
  dashboard (gitignored).
- `data/usecase_intel.sqlite` — built SQLite database (gitignored).
- `.agents/skills/` — agent skills. `case-study-extraction` is the active
  record-authoring contract; URL fetching now lives in Python.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system architecture: data flow,
  component boundaries, schemas, extension recipes, known design debt.
- `DESIGN.md` — external design-system reference (Miro) used to inform the
  dashboard styling.