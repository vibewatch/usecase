# Customer Use Case Intelligence — Documentation

Welcome to the engineering and product documentation for **Customer Use Case Intelligence** (`https://usecase.genisisiq.com/`), an evidence-backed intelligence platform and static Astro dashboard that normalizes, scores, and benchmarks real-world enterprise AI deployments across 50+ global technology vendors and consulting firms.

---

## Documentation Index

| Document | Scope & Contents |
| :--- | :--- |
| [**System Architecture & Data Model**](./architecture.md) | End-to-end data flow, Python pipeline + SQLite + Astro static architecture, `CaseStudyRecord` schema, provenance & date-evidence contracts, and repository layout. |
| [**Ingestion Pipeline & CI/CD Workflows**](./pipeline-and-workflows.md) | Sitemap/catalog discovery, multi-profile HTTP/Playwright/Jina/Wayback fetch chain, 4-stage deterministic triage, LLM agent extraction contract, provenance enrichment, and GitHub Actions automation. |
| [**Multi-Dimensional Analytics & Intelligence**](./analytics-and-intelligence.md) | Workflow-integrated analytics engine (`pipeline/usecase_intel/analytics.py`), Quantified ROI Benchmarks (Median/P75 `%` & `X` multipliers), 6-layer enterprise AI stack anatomy, product co-occurrence graph, and entity dossiers. |
| [**UI Architecture & Design System**](./ui-and-design-system.md) | `Mona Sans Variable` typography scale, warm-paper & ink editorial palette, official vendor brand logo pipeline (`public/logos/vendors/`), directory spotlight/toolbar patterns, and responsive layout rules. |

---

## Quick Reference

### Common Commands

```bash
# Install dependencies
npm install
python3 -m pip install -r requirements.txt

# Build normalized dataset, SQLite DB, weekly partitions, and multi-dimensional analytics
npm run data:build

# Run analytics engine standalone (also syncs official vendor logos)
npm run data:analytics

# Start local Astro development server (http://localhost:4321)
npm run dev

# Type-check, build static production site, and generate Pagefind search index
npm run build

# Run Python unit test suite
python3 -m unittest discover -s tests
```

### Published Machine-Readable Endpoints

Every production build publishes three static feeds alongside the HTML dashboard:

- **`/data.json`** — Complete normalized dataset of all case study records (`CaseStudyRecord[]`).
- **`/analytics.json`** — Pre-computed multi-dimensional intelligence payload (`GeneratedAnalytics`: ROI percentiles, 6-layer stack distributions, product co-occurrence pairs, macro-region & organization scale breakdowns, and per-vendor/use-case/industry dossiers).
- **`/feed.xml`** — RSS 2.0 feed of the latest collected enterprise AI customer stories.
