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

1. Identify the source.
   - Preserve the original `source_url` exactly when provided.
   - If a URL is provided and browsing or fetch tools are available, fetch the page content before extracting.
   - If only pasted text is available, use `unknown` for `source_url` unless the user provided a canonical URL.
   - If one page contains multiple distinct customers, create one record per customer.

2. Extract facts before interpreting.
   - Capture the customer name, vendor, industry, region, publication date, products, business problem, solution, outcome, metrics, and architecture clues from the source.
   - Do not infer product usage from general vendor context. Products must be explicitly mentioned or strongly evidenced in the source text.
   - Keep quoted metrics exact. Do not convert vague claims into numbers.

3. Normalize to the project taxonomy.
   - Read `taxonomy.json` when available.
   - Use taxonomy values for `industry`, `technical_area`, `use_case_category`, and `outcome_category`.
   - If no taxonomy value fits, use `unknown` or an empty array and mention the taxonomy gap separately if the user requested analysis.

4. Build the JSON record.
   - Generate a stable `id` and `slug` from vendor, customer name, and use case.
   - Use arrays for multi-value fields even when there is only one item.
   - Use an empty string, empty array, or `unknown` for unsupported fields rather than guessing.
   - Set `confidence_score` to `0.0` and `maturity_score` to `0` unless the extraction runtime explicitly asks you to compute scores.
   - When adding records to this repository, let `pipeline/usecase_intel/scoring.py` compute or recompute scores during seeding.

5. Add evidence.
   - Include short `evidence_quotes` that support the most important extracted fields.
   - Prefer quotes for business problem, products used, metrics, and outcomes.
   - If evidence is weak, keep the field conservative and let downstream scoring surface the weakness.

6. Validate before finishing.
   - Ensure the response is valid strict JSON.
   - Confirm every required field is present.
   - Check that all list fields are arrays of strings.
   - If editing the repo, run `python3 -m json.tool <file>` for JSON syntax and `npm run data:seed` when records are added to the data file.

## Required JSON Shape

```json
{
  "id": "stable-source-derived-id",
  "slug": "stable-url-slug",
  "vendor": "AWS | Microsoft | Google Cloud | Salesforce | Snowflake | Databricks | NVIDIA | other",
  "customer_name": "customer organization",
  "industry": "taxonomy industry or unknown",
  "region": "country, region, global, or unknown",
  "company_size": "Enterprise | mid-market | SMB | public sector | unknown",
  "business_problem": "factual problem from the source",
  "solution_summary": "factual implementation summary",
  "products_used": ["vendor products explicitly mentioned"],
  "technical_area": ["taxonomy technical areas"],
  "use_case_category": ["taxonomy use case categories"],
  "business_outcome": "reported benefit or outcome",
  "outcome_category": ["Cost Reduction | Productivity Improvement | Revenue Growth | Customer Experience | Risk Reduction | Compliance | Scalability | Speed to Market"],
  "metrics": ["quantitative metrics exactly as stated"],
  "architecture_clues": ["implementation, integration, or architecture details"],
  "source_url": "original URL",
  "published_date": "YYYY-MM-DD or unknown",
  "confidence_score": 0.0,
  "maturity_score": 0,
  "evidence_quotes": ["short source quote supporting the most important extracted fields"]
}
```

## Decision Rules

- Missing publication date: use `unknown`; do not invent a date from page freshness or copyright text.
- Vendor tag conflicts with source facts: trust explicit source text, preserve evidence, and flag the conflict outside JSON if needed.
- Customer name is unclear: use the named organization most central to the story; if still unclear, use `unknown` and lower confidence downstream.
- Multiple products are mentioned but only some are part of the solution: include products that are tied to implementation, architecture, or outcomes.
- Marketing-only story with no architecture or metrics: keep `architecture_clues` and `metrics` empty; do not manufacture maturity.
- Generic outcomes such as "improved efficiency": keep them as prose in `business_outcome`, but only add `outcome_category` values that are supported by the text.
- Taxonomy gaps: do not edit `taxonomy.json` automatically. Use `unknown` or an empty array in the record, then flag the missing category outside the JSON.

## Completion Criteria

- Output is strict JSON and parseable.
- Source URL is preserved.
- Required fields are present.
- Taxonomy fields use project vocabulary where possible.
- Important claims have evidence quotes.
- Unknowns remain explicit rather than hidden by speculation.
- Downstream scoring can recompute `confidence_score` and `maturity_score` deterministically.