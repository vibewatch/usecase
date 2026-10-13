export interface SolutionComponent {
  name: string;
  role: string;
  layer?: string;
}

export interface ScoreCriterion {
  criterion: string;
  score: number;
  max_score: number;
  explanation: string;
}

export interface SourceReference {
  id: string;
  title: string;
  publisher: string;
  url: string;
  source_type: string;
  authority: string;
  published_date: string;
  published_date_source: string;
  retrieved_at: string;
  supports: string[];
  evidence?: string;
}

export interface DateEvidence {
  date: string;
  type: string;
  publisher: string;
  url: string;
  authority: string;
}

export interface CaseStudyRecord {
  id: string;
  slug: string;
  vendor: string;
  customer_name: string;
  industry: string;
  region: string;
  company_size: string;
  business_problem: string;
  solution_summary: string;
  products_used: string[];
  solution_components?: SolutionComponent[];
  data_flow?: string;
  integration_points?: string[];
  technical_area: string[];
  use_case_category: string[];
  business_outcome: string;
  outcome_category: string[];
  metrics: string[];
  architecture_clues: string[];
  source_url: string;
  published_date: string;
  published_date_source?: string;
  confidence_score: number;
  confidence_breakdown?: ScoreCriterion[];
  maturity_score: number;
  value_score?: number;
  value_breakdown?: ScoreCriterion[];
  evidence_quotes: string[];
  source_references?: SourceReference[];
  field_sources?: Record<string, string[]>;
  date_evidence?: DateEvidence[];
  /** ISO 639-1 code when the source story is not in English (the record is translated). */
  source_language?: string;
  /** "company" when the story was published on the adopting company's own website. */
  source_type?: string;
  is_sample?: boolean;
  /** ISO timestamp of first collection (set by `npm run data:partition`). */
  collected_at?: string | null;
  /** ISO week (`2026-W41`) or `undated`; matches the data/weekly/ partition. */
  collected_week?: string;
}

export interface CountItem {
  label: string;
  count: number;
  share: number;
}

export interface MatrixRow {
  label: string;
  total: number;
  cells: Array<{
    label: string;
    count: number;
  }>;
}

export interface Taxonomy {
  vendors: string[];
  industries: string[];
  technical_areas: string[];
  use_case_categories: string[];
  outcome_categories: string[];
  component_layers: string[];
}