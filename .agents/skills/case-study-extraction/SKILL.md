---
name: case-study-extraction
description: 'Extract vendor customer stories, case studies, success stories, or reference pages into normalized Customer Use Case Intelligence JSON. Use when: converting AWS, Microsoft, Google Cloud, Salesforce, Snowflake, Databricks, NVIDIA, or other vendor pages into structured records for taxonomy mapping, SQLite seeding, Astro dashboards, evidence-backed extraction, or LLM case study normalization.'
argument-hint: 'source URL, pasted page text, raw HTML, or vendor/customer story notes'
---

# Case Study Extraction

## What This Produces

One normalized JSON record per customer story, suitable for `data/case-studies.sample.json`, the SQLite seed pipeline, and the Astro intelligence dashboard.

The output must be factual, traceable, and strict JSON. Do not include markdown fences, prose before or after the object, or unsupported guesses.

## When to Use

Use this skill when the user asks to:

- Extract a vendor customer story or case study.
- Normalize AWS, Microsoft, Google Cloud, Salesforce, Snowflake, Databricks, NVIDIA, or similar customer references.
- Convert a source page into the Customer Use Case Intelligence schema.
- Map vendor-provided tags into the project taxonomy.
- Prepare records for SQLite seeding, JSON export, or the Astro dashboard.

## Procedure

0. Confirm the page is a customer story.
   - A customer story describes a named customer organization using the vendor's products or services, with a problem, a solution, or an outcome.
   - Product launches, feature announcements, policy posts, research, partnership or availability news, event recaps, listing/index pages, and pages that no longer contain the story are **not** customer stories.
   - If the page is not a customer story, output only `{"not_a_customer_story": true, "source_url": "<url>", "reason": "<one short sentence>"}` and stop. Do not write a record.
   - The catalog holds **AI use cases only**. The story qualifies only when AI/ML is a core, implemented part of the solution: generative AI / LLMs, AI agents or copilots, NLP/LLM chatbots or virtual assistants, machine-learning models (prediction, recommendation, forecasting, fraud or anomaly detection), computer vision, speech or NLP, document AI, vector search / RAG, or infrastructure built to train or serve AI models. Pure cloud/system migration, modernization, infrastructure, DevOps, security, ERP/CRM, rules-based automation, and analytics/BI/data-platform work without running AI do not qualify — nor does AI that is only planned, aspirational ("AI-ready", "foundation for future AI") or mentioned in passing.
   - If the story does not qualify, output only `{"not_an_ai_use_case": true, "source_url": "<url>", "reason": "<one short sentence>"}` and stop. Do not write a record.

1. Identify the source.
   - Preserve the original `source_url` exactly when provided.
   - If a URL is provided and browsing or fetch tools are available, fetch the page content before extracting.
   - If only pasted text is available, use `unknown` for `source_url` unless the user provided a canonical URL.
   - If one page contains multiple distinct customers, create one record per customer.
   - Record every consulted page in `source_references`, not only the original customer story. Never use an enrichment source without listing it.
   - Give each source a stable local `id`, classify its authority, record its publication-date provenance and retrieval timestamp, and list the exact record fields it supports.
   - Build `field_sources` as a field-to-source-id map. Fields inferred only for taxonomy normalization must not be presented as independently sourced.

2. Extract facts before interpreting.
   - Capture the customer name, vendor, industry, region, publication date, products, business problem, solution, outcome, metrics, and architecture clues from the source.
   - Do not infer product usage from general vendor context. Products must be explicitly mentioned or strongly evidenced in the source text.
   - Keep quoted metrics exact. Do not convert vague claims into numbers.

3. Normalize to the project taxonomy.
   - Read `taxonomy.json` when available.
   - Use taxonomy values for `industry`, `technical_area`, `use_case_category`, `outcome_category`, and `solution_components[].layer`.
   - `industry` is the customer organization's own industry and is never `unknown`: always pick the closest `taxonomy.json` industry (e.g. a law firm or consultancy → `Commercial and Professional Services`, a hotel group → `Travel and Hospitality`, a property developer → `Real Estate and Construction`).
   - For the other taxonomy fields, if no taxonomy value fits, use `unknown` or an empty array and mention the taxonomy gap separately if the user requested analysis.

4. Build a deep solution view (the part most extractions get wrong).
   - `solution_summary` must be **600–1000 characters** and cover the implementation across the layers the source describes: how data is ingested, processed, stored, and served, plus the key integration patterns. Mention each major component by name with its role.
   - `solution_components` must include **one object per named product or service** that is actually part of the implementation. Each object has:
     - `name`: the exact product name from the source.
     - `role`: one short sentence describing what this component does in this specific deployment (not a generic product blurb).
     - `layer`: one value from `taxonomy.json → component_layers` (`Ingest`, `Compute`, `Storage`, `Serving`, `Orchestration`, `Governance`) when the source supports it; omit `layer` rather than guess.
   - `data_flow` should be one paragraph (≤ 600 characters) tracing how data moves end-to-end through the components — sources → processing tier → storage tier → consumption — only when the source actually describes the flow. Leave empty when the page does not support it.
   - `integration_points` lists external systems, upstream data sources, downstream consumers, and third-party APIs that the solution connects to. Skip when the page does not name any.
   - `architecture_clues` remains a free-form bag for short technical notes (regions, deployment topology, capacity figures, observability hooks) that do not fit the other fields. Keep `products_used` in sync as a flat list of every `solution_components[].name`.

5. Compose the JSON record.
   - Generate a stable `id` and `slug` from vendor, customer name, and use case.
   - Use arrays for multi-value fields even when there is only one item.
   - Use an empty string, empty array, or `unknown` for unsupported fields rather than guessing. Omit `solution_components`, `data_flow`, and `integration_points` only when the source has nothing concrete to say about them.
   - Set `confidence_score` to `0.0` and `maturity_score` to `0` unless the extraction runtime explicitly asks you to compute scores.
   - Set `value_score` to `0`; downstream scoring recomputes value and confidence with a deterministic rubric.
   - When adding records to this repository, let `pipeline/usecase_intel/scoring.py` compute or recompute scores during seeding.

6. Add evidence.
   - Include short `evidence_quotes` that support the most important extracted fields.
   - Prefer quotes for business problem, products used, the data flow narrative, metrics, and outcomes.
   - If evidence is weak, keep the field conservative and let downstream scoring surface the weakness.
   - A quote is not a substitute for source metadata: every quote's source must also be represented in `source_references`.

7. Validate before finishing.
   - Ensure the response is valid strict JSON.
   - Confirm every required field is present.
   - Check that all list fields are arrays of strings; `solution_components` must be a list of `{name, role, layer?}` objects.
   - Confirm every `solution_components[].name` also appears in `products_used`.
   - If editing the repo, run `python3 -m json.tool <file>` for JSON syntax and `npm run data:build` after adding records.

## Required JSON Shape

```json
{
  "id": "stable-source-derived-id",
  "slug": "stable-url-slug",
  "vendor": "AWS | Microsoft | Google Cloud | Salesforce | Snowflake | Databricks | NVIDIA | Oracle | Alibaba Cloud | IBM | Tencent Cloud | Baidu AI Cloud | … (see taxonomy.json vendors)",
  "customer_name": "customer organization",
  "industry": "closest taxonomy industry (never unknown)",
  "region": "country, region, global, or unknown",
  "company_size": "Enterprise | Mid-market | SMB | Public sector | Unknown",
  "business_problem": "factual problem from the source",
  "solution_summary": "600–1000 char implementation summary covering ingest, processing, storage, serving, and key integrations",
  "products_used": ["flat list of every component name (must mirror solution_components[].name)"],
  "solution_components": [
    { "name": "Product or service name", "role": "What this component does in this deployment", "layer": "Ingest | Compute | Storage | Serving | Orchestration | Governance" }
  ],
  "data_flow": "Optional one-paragraph narrative of how data moves through the components end-to-end",
  "integration_points": ["External systems, upstream sources, downstream consumers, third-party APIs"],
  "technical_area": ["taxonomy technical areas"],
  "use_case_category": ["taxonomy use case categories"],
  "business_outcome": "reported benefit or outcome",
  "outcome_category": ["Cost Reduction | Productivity Improvement | Revenue Growth | Customer Experience | Risk Reduction | Compliance | Scalability | Speed to Market"],
  "metrics": ["quantitative metrics exactly as stated"],
  "architecture_clues": ["short technical notes not covered by other fields: regions, topology, capacity, observability"],
  "source_url": "original URL",
  "published_date": "YYYY-MM-DD or unknown",
  "published_date_source": "page | page metadata | vendor metadata | sitemap | wayback_first_capture | unknown",
  "source_references": [
    {
      "id": "primary-story",
      "title": "Source page title",
      "publisher": "Organization that published the page",
      "url": "exact source URL",
      "source_type": "Vendor-published customer story | Customer-published story | Company profile | Independent reporting | …",
      "authority": "First-party | Independent | Unknown",
      "published_date": "YYYY-MM-DD or unknown",
      "published_date_source": "page | page metadata | vendor metadata | sitemap | wayback_first_capture | unknown",
      "retrieved_at": "ISO 8601 timestamp or unknown",
      "supports": ["business_problem", "solution_summary", "metrics"]
    }
  ],
  "field_sources": {
    "business_problem": ["primary-story"],
    "company_size": ["company-profile"]
  },
  "confidence_score": 0.0,
  "maturity_score": 0,
  "value_score": 0,
  "evidence_quotes": ["short source quote supporting the most important extracted fields"]
}
```

## Decision Rules

- Non-English source (e.g. a Chinese-language case from Tencent Cloud or Baidu AI Cloud): write every field of the record in English — translate faithfully, without embellishing. Keep the customer's official English name when the source or the company uses one; otherwise give the pinyin or translated name followed by the original in parentheses, e.g. `"Guangdong Provincial Government Services and Data Administration (广东省政务服务和数据管理局)"`. Keep product names as the vendor brands them in English (e.g. `Qianfan`, `ERNIE`, `Hunyuan`). Each `evidence_quotes` item is the English translation followed by the verbatim original: `"<English translation> (original: <source text>)"`. Keep `metrics` exact (numbers and units unchanged), translated to English. Add `"source_language": "<ISO 639-1 code, e.g. zh>"` to the record. Omit `source_language` for English sources.
- Missing publication date: use `unknown`; do not invent a date from page freshness or copyright text.
- A sitemap `lastmod`, collection timestamp, or archive capture is not a publication date. Preserve it only with the matching `published_date_source`, and prefer `unknown` over presenting a modification or retrieval date as publication.
- Company size, region, company background, and similar enrichment must either cite a separate supporting source or remain conservative/unknown. Do not silently hydrate them from outside knowledge.
- Vendor tag conflicts with source facts: trust explicit source text, preserve evidence, and flag the conflict outside JSON if needed.
- Customer name is unclear: use the named organization most central to the story; if still unclear, use `unknown` and lower confidence downstream.
- Multiple products are mentioned but only some are part of the solution: include products that are tied to implementation, architecture, or outcomes. Drop pure marketing co-mentions.
- Solution component role is not described: write the role from the source's own language (one short sentence). Do not paste vendor documentation blurbs.
- Component layer is ambiguous (e.g. a managed product spans Compute and Serving): omit `layer` rather than pick the wrong one.
- Source does not describe data flow: omit `data_flow` rather than narrate a generic pipeline.
- Marketing-only story with no architecture or metrics: keep `architecture_clues`, `metrics`, `solution_components`, `data_flow`, and `integration_points` empty; do not manufacture maturity.
- Generic outcomes such as "improved efficiency": keep them as prose in `business_outcome`, but only add `outcome_category` values that are supported by the text.
- Taxonomy gaps: do not edit `taxonomy.json` automatically. Use `unknown` or an empty array in the record, then flag the missing category outside the JSON.

## Completion Criteria

- Non-story pages produce only the `not_a_customer_story` object, and stories without implemented AI only the `not_an_ai_use_case` object (step 0), never a record.
- Output is strict JSON and parseable.
- Source URL is preserved.
- Required fields are present.
- `solution_summary` is 600–1000 characters when the source supports it.
- Every `solution_components[].name` also appears in `products_used`.
- Taxonomy fields use project vocabulary where possible (including `component_layers`).
- Important claims have evidence quotes.
- Every consulted source is listed, every source has retrieval metadata, and `field_sources` references valid source ids.
- Records from non-English sources are fully in English, carry `source_language`, and their evidence quotes keep the original text.
- Unknowns remain explicit rather than hidden by speculation.
- Downstream scoring can recompute `confidence_score` and `maturity_score` deterministically.