import { isParseableDate } from "./analytics";
import { href } from "./paths";
import type { CaseStudyRecord } from "./types";

export type FacetKind = "vendors" | "industries" | "use-cases";

export const FACETS: Record<FacetKind, { label: string; plural: string; values: (record: CaseStudyRecord) => string[] }> = {
  vendors: { label: "Vendor", plural: "Vendors", values: (record) => [record.vendor] },
  industries: { label: "Industry", plural: "Industries", values: (record) => [record.industry] },
  "use-cases": { label: "Use case", plural: "Use cases", values: (record) => record.use_case_category },
};

export const PAGE_SIZE = 24;

export function facetSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "other";
}

export function facetHref(kind: FacetKind, value: string): string {
  return href(`/${kind}/${facetSlug(value)}/`);
}

/** Every distinct value of a facet with its records (most records first). */
export function facetGroups(kind: FacetKind, records: CaseStudyRecord[]) {
  const groups = new Map<string, CaseStudyRecord[]>();
  for (const record of records) {
    for (const value of FACETS[kind].values(record)) {
      if (!value) continue;
      if (!groups.has(value)) groups.set(value, []);
      groups.get(value)!.push(record);
    }
  }
  return Array.from(groups.entries())
    .map(([value, items]) => ({ value, slug: facetSlug(value), records: sortNewest(items) }))
    .sort((left, right) => right.records.length - left.records.length || left.value.localeCompare(right.value));
}

/** Newest first by publish date; undated stories sort last (collection date breaks ties). */
export function newestKey(record: CaseStudyRecord): string {
  return isParseableDate(record.published_date) ? record.published_date : "";
}

export function sortNewest(records: CaseStudyRecord[]): CaseStudyRecord[] {
  return [...records].sort(
    (left, right) =>
      newestKey(right).localeCompare(newestKey(left)) ||
      (right.collected_at ?? "").localeCompare(left.collected_at ?? "") ||
      left.customer_name.localeCompare(right.customer_name),
  );
}

export function publishedYear(record: CaseStudyRecord): string {
  return isParseableDate(record.published_date) ? record.published_date.slice(0, 4) : "Undated";
}
