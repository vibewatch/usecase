# UI Architecture & Design System

This document describes the visual language, typography, color tokens, brand logo pipeline, and page templates used across the **Customer Use Case Intelligence** Astro dashboard (`https://usecase.genisisiq.com/`).

---

## 1. Design Philosophy: Editorial Intelligence Brief

The interface is designed as a high-density, low-noise **editorial research brief**:

- **Warm Paper & Ink Palette**: Long-form technical reading is set on warm paper (`#f3ede1` plane, `#fbf8f2` surface) with deep charcoal ink (`#1c1a17`), framed by high-contrast dark ink hero/navigation bands (`#1a1714`).
- **Compact Square-Corner Geometry**: Small radii (`2px–4px`), crisp `1.5px` structural rules, and tactile offset shadows (`3px 3px 0 var(--ink)`) give cards and matrices the clarity of an engineering specification.
- **Progressive Disclosure**: Case detail pages lead with the business problem, quantified outcome, and layered solution architecture, while full scoring rubrics and source provenance tables remain neatly collapsible under **Evidence & methodology**.

---

## 2. Unified Typography (`Mona Sans Variable`)

All typography across the entire site is unified on **`Mona Sans Variable`** (`@fontsource-variable/mona-sans`), matching `https://startup.genisisiq.com/`:

```css
:root {
  --font-sans: "Mona Sans Variable", "Mona Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-display: "Mona Sans Variable", "Mona Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "Mona Sans Variable", "Mona Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

### OpenType & Numeric Discipline

- **Stylistic Sets**: `html` enables `font-feature-settings: "cv11", "ss01", "ss03"` with antialiased rendering.
- **Tabular Numerals**: All KPIs, counts, badges, percentages, benchmark tables, heatmaps, and dates enforce `font-variant-numeric: tabular-nums lining-nums` (`"tnum" on, "lnum" on`) so columns align cleanly without requiring a separate monospace font.

---

## 3. Global Design Tokens (`src/styles/global.css`)

| Category | CSS Custom Properties | Values / Usage |
| :--- | :--- | :--- |
| **Layout & Grid** | `--container`, `--container-gutter`, `--header-h` | `1320px` max width, `16px` gutter, `60px` sticky header height. |
| **Paper Surfaces** | `--plane`, `--surface`, `--surface-2` | `#f3ede1` (page background), `#fbf8f2` (card surface), `#ece4d4` (nested panels/tracks). |
| **Ink Hierarchy** | `--ink`, `--ink-2`, `--ink-3`, `--ink-4` | `#1c1a17` (primary), `#3d3831` (body), `#696256` (secondary), `#948b7c` (muted). |
| **Night Bands** | `--night`, `--night-2`, `--on-night`, `--on-night-muted` | `#1a1714`, `#24201b`, `#efe7d8`, `#b3a998` for header, heroes, and footer. |
| **Semantic Accents** | `--accent`, `--accent-bright`, `--teal`, `--teal-ink` | Persimmon `#e8572a` / `#ff8a5c` (highlights, CTAs, ROI tags) and Verdigris Teal `#0b8a78` / `#0b5e52` (verified evidence, charts, links). |
| **Architecture Layer Colors** | Inline & class tokens | `Serving` (`#0b8a78`), `Compute` (`#e8572a`), `Storage` (`#2563eb`), `Orchestration` (`#7c3aed`), `Ingest` (`#d97706`), `Governance` (`#475569`). |

---

## 4. Official Vendor Brand Logo Pipeline

Vendor logos are stored as static assets under [`public/logos/vendors/`](../public/logos/vendors/) and mapped in [`src/lib/vendors.ts`](../src/lib/vendors.ts):

1. **Official Brand Assets Only**: Every vendor in `taxonomy.json` (51 vendors plus consulting partners) uses an official SVG, PNG, or high-resolution favicon sourced from the vendor's official domain, Wikimedia Commons, or Simple Icons—never hand-drawn monogram approximations.
2. **Base-Path Aware Rendering**: `vendorLogoUrl(vendor)` resolves paths through `href("/logos/vendors/...")`, and `vendorLogoSvg(vendor)` returns an `<img class="vendor-logo-svg vendor-logo-img" loading="lazy" decoding="async" />` element that fits cleanly inside `.hub-card__logo`, `.spotlight-card__logo`, `.page-hero__logo`, `.vendor-mini-pill__logo`, and `.case-card` badges.
3. **Automated Workflow Check**: `pipeline/usecase_intel/analytics.py` (`sync_vendor_logos()`) runs on every `npm run data:build` and verifies that every vendor in the catalog has a non-empty logo asset in `public/logos/vendors/`.

---

## 5. Key Page Templates & Interactive Components

| Template | Route(s) | Key UI Features |
| :--- | :--- | :--- |
| **Home Dashboard** | [`src/pages/index.astro`](../src/pages/index.astro) | Hero search, live catalog KPIs, latest weekly arrivals, newest case cards, Co-deployed AI Product Pairs, Global Macro-Region bars, and Industry × Use-Case heatmap. |
| **Directory Hubs** | [`src/pages/[facet]/index.astro`](../src/pages/[facet]/index.astro) | Serves `/vendors/`, `/use-cases/`, and `/industries/`. Features a **Top-4 Spotlight Row**, a sticky **Live Search + Sort (`Most stories`, `Value score`, `Quantified ROI %`, `A–Z`) + Category Filter Toolbar**, and enriched cards with 3-metric KPI strips, top products, 6-layer architecture signature bars, and flagship customer metrics. |
| **Entity Dossier & Listing** | [`src/pages/[facet]/[value]/[...page].astro`](../src/pages/[facet]/[value]/[...page].astro) | Serves `/vendors/[slug]/`, `/use-cases/[slug]/`, and `/industries/[slug]/`. Page 1 renders a 4-panel **Deep Intelligence Brief** (6-Layer Architecture Breakdown, Top Products & Co-deployed Pairs, Sector/Region/Scale Footprint, and Verified Outcome Benchmarks) above the paginated case listing. |
| **Market & Evidence Insights** | [`src/pages/insights.astro`](../src/pages/insights.astro) | Executive briefing with Quantified ROI Benchmarks (Median/P75 `%` + `X` multipliers), 6-Layer Enterprise AI Architecture Anatomy, Co-deployed Product Pairs, Global Macro-Region & Organization Scale, source authority concentration, and cross-tab heatmaps. |
| **Faceted Explorer** | [`src/pages/explore.astro`](../src/pages/explore.astro) | Client-side Pagefind full-text search with multi-select vendor/industry/use-case/technical-area/outcome/year filters, live facet counts, and shareable URL query state. |
| **Case Research Brief** | [`src/pages/cases/[slug].astro`](../src/pages/cases/[slug].astro) | Individual deployment brief with headline metric tiles, business problem, highlighted outcome panel, layered architecture stack (`solution_components` grouped by layer), end-to-end `data_flow`, verbatim `evidence_quotes`, and collapsible **Evidence & methodology** provenance sheets. |
