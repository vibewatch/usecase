import type { CaseStudyRecord, CountItem, MatrixRow } from './types';

export function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((left, right) => left.localeCompare(right));
}

export function flattenValues(
  records: CaseStudyRecord[],
  selector: (record: CaseStudyRecord) => string[]
): string[] {
  return records.flatMap((record) => selector(record).filter(Boolean));
}

export function countValues(values: string[], denominator = values.length): CountItem[] {
  const counts = new Map<string, number>();

  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .map(([label, count]) => ({
      label,
      count,
      share: denominator === 0 ? 0 : count / denominator
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function topValues(values: string[], limit = 10): CountItem[] {
  return countValues(values).slice(0, limit);
}

export function averageConfidence(records: CaseStudyRecord[]): number {
  if (records.length === 0) return 0;
  return records.reduce((sum, record) => sum + record.confidence_score, 0) / records.length;
}

export function maturityLabel(score: number): string {
  if (score >= 5) return 'Strong reference';
  if (score >= 3) return 'Useful but limited';
  return 'Marketing-level';
}

export function maturityDistribution(records: CaseStudyRecord[]): CountItem[] {
  return countValues(
    records.map((record) => maturityLabel(record.maturity_score)),
    records.length
  );
}

export function buildMatrix(
  records: CaseStudyRecord[],
  rows: string[],
  columns: string[],
  rowSelector: (record: CaseStudyRecord) => string[],
  columnSelector: (record: CaseStudyRecord) => string[]
): MatrixRow[] {
  return rows
    .map((rowLabel) => {
      const cells = columns.map((columnLabel) => {
        const count = records.filter(
          (record) => rowSelector(record).includes(rowLabel) && columnSelector(record).includes(columnLabel)
        ).length;
        return { label: columnLabel, count };
      });

      return {
        label: rowLabel,
        cells,
        total: cells.reduce((sum, cell) => sum + cell.count, 0)
      };
    })
    .sort((left, right) => right.total - left.total || left.label.localeCompare(right.label));
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const ISO_DATE_RE = /^\d{4}-\d{2}(?:-\d{2})?(?:T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z?)?$/;

export function isParseableDate(value: string): boolean {
  if (!value || !ISO_DATE_RE.test(value)) return false;
  const date = new Date(value);
  return !Number.isNaN(date.getTime());
}

export function formatDate(value: string): string {
  if (!isParseableDate(value)) return value || "—";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value),
  );
}