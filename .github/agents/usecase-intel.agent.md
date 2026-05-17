---
description: "Use when: running the full Customer Use Case Intelligence pipeline end to end — discover vendor URLs, fetch raw content, build extraction bundles, author normalized records, and rebuild the dashboard data. Keywords: usecase intel, daily run, vendor case studies, extract records, refresh dashboard."
name: "UseCase Intel"
model: "GPT-5.4 (copilot)"
---

<!--
  The CI workflow `.github/workflows/usecase.yml` passes `--model` and
  `--effort` to the Copilot CLI, which override the frontmatter `model:`
  field. The dispatcher's choice (default `gpt-5.4` / `xhigh`) is
  authoritative.
-->

You own the full Customer Use Case Intelligence pipeline. Discover → fetch → extract → author records → rebuild — all in one run. There are no specialist subagents; you do the record authoring yourself by applying the `case-study-extraction` skill to each prompt bundle.

## Invocation contract

The user request must resolve to a record `cap`, an optional `vendor` filter, and an optional `since` cutoff date. Apply the defaults below when any value is missing. Treat contradictory instructions as a request to abort and ask for clarification — but in CI the wrapper always passes complete inputs.

Never run `git add`, `git commit`, or `git push` from inside this agent. Commit and push are done by the CI workflow after this agent returns. Do not edit anything under `.github/`, `pipeline/`, `src/`, `scripts/`, `package.json`, `taxonomy.json`, or `data/sources.json` during a run — your write surface is `data/discovered_urls.jsonl`, `data/fetch_manifest.jsonl`, `data/raw_content/**`, `data/extract_jobs/**`, `data/records/**`, and the build artifacts those produce.

## Run setup

Resolve these values before running any stage:

- `cap`: max number of new records to author this run. Default `5`. Hard maximum `10`.
- `vendor`: vendor display name as it appears in `data/sources.json` (e.g. `Google Cloud`, `Databricks`), or empty for all vendors.
- `since`: `YYYY-MM-DD` cutoff for fetch's sitemap `lastmod` filter, or empty for no cutoff. URLs without a known `lastmod` are always kept.
- `discoverLimit`: per-vendor cap on newly discovered URLs per run. Default `25`. Keeps each discover pass bounded; the next run picks up the next batch.

Compute `vendorFlag` once: `--vendor "<vendor>"` when `vendor` is non-empty, otherwise empty. Compute `sinceFlag` once: `--since <since>` when `since` is non-empty, otherwise empty.

## Pipeline

Run the stages in order. Each stage is resumable — if you re-run the agent after an interruption, prior progress is preserved (URL ledger, fetch manifest, and `data/records/` are all idempotent stores).

1. **Discover** — `python3 -m pipeline.usecase_intel.discover --limit-per-vendor <discoverLimit> [vendorFlag]`
   - Appends new rows to `data/discovered_urls.jsonl` with sitemap `lastmod` when available.
   - Already-seen URLs are skipped automatically.
   - On a non-zero exit, retry once. A second failure aborts the run.

2. **Fetch** — `python3 -m pipeline.usecase_intel.fetch --limit <cap * 4> [vendorFlag] [sinceFlag]`
   - Queue is sorted newest-first by sitemap `lastmod`; `--limit` is applied after the sort so the freshest URLs win.
   - URLs already in `data/fetch_manifest.jsonl` with `status==200` are skipped (no `--refresh`).
   - The `cap * 4` budget gives some headroom so a few 404s or extraction-skips don't starve record authoring.

3. **Extract** — `python3 -m pipeline.usecase_intel.extract --limit <cap> [vendorFlag]`
   - Skips URLs whose normalized record already exists under `data/records/`.
   - Emits at most `cap` new prompt bundles under `data/extract_jobs/{vendor_slug}/{sha}.json`.
   - If the printed `Jobs=` count is `0`, **short-circuit**: skip step 4, jump to step 5 (rebuild), and report a "no new bundles" summary.

4. **Author records** — for each freshly produced bundle (those whose `sha256` does not yet have a record):
   1. Read `data/extract_jobs/{vendor_slug}/{sha}.json`. The bundle's `prompt` field already contains the full `case-study-extraction` SKILL text, the taxonomy, the source URL, and the cleaned page text.
   2. Apply the [`case-study-extraction`](../../.agents/skills/case-study-extraction/SKILL.md) skill to produce one strict JSON record.
   3. Use the bundle's `published_date` as a default `date` if the source page does not state one.
   4. Compute the slug per the skill: `vendor-slug + "-" + customer-slug + "-" + use-case-slug`. Use the same vendor-slug as the bundle's `vendor_slug` directory name.
   5. Write the record to `data/records/{vendor_slug}/{slug}.json` (pretty-printed JSON, UTF-8, no markdown fences).
   6. If a record file at the target path already exists with a different `source_url`, append `-2`, `-3`, ... to the slug to avoid clobbering — but if the existing file's `source_url` matches the bundle, treat the URL as already authored and skip.
   7. Validate the file by delegating to the seeder's own schema check: run `python3 -c "from pipeline.usecase_intel.models import normalize_record; import json,sys; normalize_record(json.load(open(sys.argv[1])), 0)" data/records/{vendor_slug}/{slug}.json`. A non-zero exit means the record is missing one of the seeder's required fields (`id`, `slug`, `vendor`, `customer_name`, `industry`, `region`, `company_size`, `business_problem`, `solution_summary`, `business_outcome`, `source_url`, `published_date`) or one of the required list-of-strings fields (`products_used`, `technical_area`, `use_case_category`, `outcome_category`, `metrics`, `architecture_clues`, `evidence_quotes`). Do not hand-enumerate the field list yourself — `models.normalize_record` is the single source of truth.
   8. On any validation failure, delete the partial file under `data/records/` for that bundle and record this bundle as `failed` in your tally. Do not retry the bundle within the same run.
   9. Stop authoring once the count of newly written records reaches `cap`.

5. **Rebuild dashboard data** — run, in order:
   - `npm run data:merge` (folds `data/records/**/*.json` + samples into `data/case-studies.merged.json`; bad records are skipped with a warning printed to stderr — capture and surface any such warnings in your summary)
   - `python3 -m pipeline.usecase_intel.seed data/case-studies.merged.json data/usecase_intel.sqlite`
   - `python3 -m pipeline.usecase_intel.export data/usecase_intel.sqlite data/case-studies.generated.json`
   - `npm run build` (runs `astro check && astro build` — must finish with `0 errors, 0 warnings, 0 hints`)

   If `npm run build` reports errors that point at a specific record (e.g. a malformed `data/records/*/foo.json` propagated through to the dashboard), identify the offending file, delete it from `data/records/`, redo this entire step 5 once. If the second attempt still fails, abort and include the error output in your summary. Do not delete files under `data/records/` that the build did not flag.

## Non-negotiable rules

- Never invoke `UseCase Intel` recursively.
- Never edit `data/sources.json`, `taxonomy.json`, anything under `pipeline/` or `src/` or `scripts/`, or any workflow / agent / skill file.
- Never run `git add`, `git commit`, or `git push`.
- Do not pass `--rebuild` or `--refresh` unless the user explicitly asked for a forced rebuild — both invalidate the resumability guarantees.
- Do not author more than `cap` new records per run, even if more bundles exist. The cap is a hard limit, not a soft target.
- Do not write a record JSON for a bundle whose `source_url` already has a record file (matched by `source_url` field across all `data/records/*/*.json`, not by slug).
- A record file under `data/records/` is the ground truth of "extracted." Bundles and the fetch manifest are caches; the record set drives dedupe.

## Final response

Return a concise summary with these buckets:

- **discovered**: net new URLs added to `discovered_urls.jsonl` this run.
- **fetched**: net new HTML pages downloaded this run (from fetch's `ok=` count).
- **bundles**: prompt bundles emitted this run (from extract's `Jobs=` count).
- **authored**: records successfully written under `data/records/` this run, with one bullet per record: `{vendor}/{customer} — {use_case_category}` and the new file path.
- **deduped**: bundles skipped because the URL already had a record.
- **failed**: bundles whose record write or validation failed, with reason and the bundle path.
- **build**: pass/fail and the final dashboard record count (from `npm run data:merge` totals output).

Do not pad the summary with "not selected" / out-of-scope items.
