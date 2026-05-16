# Customer Use Case Intelligence

Astro dashboard plus a lightweight Python data pipeline for normalizing vendor customer stories into comparable market intelligence records.

## Commands

```bash
npm install
npm run dev
npm run build
npm run data:seed
npm run data:export
```

The current dashboard reads `data/case-studies.sample.json`. Those records are synthetic placeholders with `is_sample: true` so the UI, SQLite schema, and analysis functions can be exercised before real crawlers and LLM extraction jobs are connected.

## Current Shape

- `src/pages/index.astro` renders the dashboard.
- `src/pages/cases/[slug].astro` renders traceable case detail pages.
- `data/case-studies.sample.json` is the normalized record format consumed by Astro.
- `taxonomy.json` is the canonical category vocabulary for extraction and analysis.
- `pipeline/usecase_intel` validates records, computes missing scores, seeds SQLite, and exports JSON.
- `prompts/extract_case_study.md` is the initial LLM extraction contract.