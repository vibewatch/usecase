import { formatDate, headlineMetric, isParseableDate, recencyKey } from "./analytics";
import { caseHref } from "./paths";
import type { CaseStudyRecord } from "./types";
import { vendorStyle } from "./vendors";

export const UNDATED_WEEK = "undated";

export interface WeekGroup {
  week: string;
  label: string;
  records: CaseStudyRecord[];
}

/** Slim projection shipped in the per-week JSON shards and rendered by the card template. */
export interface CardRecord {
  slug: string;
  url: string;
  vendor: string;
  vendorMark: string;
  vendorColor: string;
  customer: string;
  industry: string;
  region: string;
  useCases: string[];
  areas: string[];
  products: string[];
  problem: string;
  metric: string;
  published: string;
  maturity: number;
  sample: boolean;
  week: string;
  search: string;
}

function weekStart(week: string): Date | null {
  const match = /^(\d{4})-W(\d{2})$/.exec(week);
  if (!match) return null;
  // ISO week 1 is the week containing January 4th; weeks start on Monday.
  const jan4 = new Date(Date.UTC(Number(match[1]), 0, 4));
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() || 7) - 1) + (Number(match[2]) - 1) * 7);
  return monday;
}

export function weekLabel(week: string): string {
  const start = weekStart(week);
  if (!start) return "Reference set";
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 6);
  const day = new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" });
  return `${day.format(start)} – ${day.format(end)}, ${end.getUTCFullYear()}`;
}

export function weekShortLabel(week: string): string {
  const start = weekStart(week);
  if (!start) return "Undated";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" }).format(start);
}

export function recordWeek(record: CaseStudyRecord): string {
  return record.collected_week || UNDATED_WEEK;
}

/** Newest week first, undated last; records inside a week newest-published first. */
export function groupByWeek(records: CaseStudyRecord[]): WeekGroup[] {
  const buckets = new Map<string, CaseStudyRecord[]>();
  for (const record of records) {
    const week = recordWeek(record);
    if (!buckets.has(week)) buckets.set(week, []);
    buckets.get(week)!.push(record);
  }

  return Array.from(buckets.entries())
    .sort(([left], [right]) => {
      if (left === UNDATED_WEEK) return 1;
      if (right === UNDATED_WEEK) return -1;
      return right.localeCompare(left);
    })
    .map(([week, items]) => ({
      week,
      label: weekLabel(week),
      records: [...items].sort(
        (left, right) =>
          recencyKey(right).localeCompare(recencyKey(left)) ||
          left.customer_name.localeCompare(right.customer_name),
      ),
    }));
}

function truncate(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit).replace(/\s+\S*$/, "")}…`;
}

export function toCardRecord(record: CaseStudyRecord): CardRecord {
  const { color, mark } = vendorStyle(record.vendor);
  return {
    slug: record.slug,
    url: caseHref(record.slug),
    vendor: record.vendor,
    vendorMark: mark,
    vendorColor: color,
    customer: record.customer_name,
    industry: record.industry,
    region: record.region,
    useCases: record.use_case_category,
    areas: record.technical_area,
    products: record.products_used.slice(0, 3),
    problem: truncate(record.business_problem, 220),
    metric: headlineMetric(record),
    published: isParseableDate(record.published_date) ? formatDate(record.published_date) : "",
    maturity: record.maturity_score,
    sample: Boolean(record.is_sample),
    week: recordWeek(record),
    search: [
      record.customer_name,
      record.vendor,
      record.industry,
      record.region,
      record.business_problem,
      record.solution_summary,
      ...record.products_used,
      ...record.use_case_category,
      ...record.technical_area,
    ]
      .join(" ")
      .toLowerCase(),
  };
}
