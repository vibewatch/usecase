export interface SolutionComponent {
  name: string;
  role: string;
  layer?: string;
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
  confidence_score: number;
  maturity_score: number;
  evidence_quotes: string[];
  is_sample?: boolean;
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