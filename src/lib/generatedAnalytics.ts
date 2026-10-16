import rawAnalytics from "../../data/analytics.generated.json";

export interface FacetShareItem {
  label: string;
  count: number;
  share: number;
}

export interface ArchitectureLayerItem {
  layer: string;
  component_count: number;
  story_count: number;
  story_share: number;
  top_products: FacetShareItem[];
  top_vendors?: FacetShareItem[];
  top_use_cases?: FacetShareItem[];
  top_roles?: FacetShareItem[];
}

export interface ProductEcosystemItem {
  name: string;
  count: number;
  share: number;
  primary_vendor: string;
  primary_layer: string;
  top_use_cases: FacetShareItem[];
  quantified_rate: number;
}

export interface ProductPairItem {
  pair: string;
  product_a: string;
  product_b: string;
  count: number;
  share: number;
  top_vendor?: string;
  top_use_case?: string;
}

export interface SampleMetricItem {
  metric: string;
  customer_name: string;
  vendor: string;
  slug: string;
  industry?: string;
}

export interface RoiBenchmarkItem {
  category: string;
  description: string;
  story_count: number;
  story_share: number;
  metric_count: number;
  median_percent_gain: number | null;
  p75_percent_gain: number | null;
  multiplier_count: number;
  top_use_cases: FacetShareItem[];
  sample_metrics: SampleMetricItem[];
}

export interface MacroRegionItem {
  region: string;
  count: number;
  share: number;
  quantified_rate: number;
  top_vendors: FacetShareItem[];
  top_use_cases: FacetShareItem[];
}

export interface CountryItem {
  country: string;
  macro_region: string;
  count: number;
  share: number;
  top_vendor: string;
  top_industry: string;
}

export interface CompanySizeItem {
  company_size: string;
  count: number;
  share: number;
  avg_value_score: number;
  quantified_rate: number;
  top_use_cases: FacetShareItem[];
  top_vendors: FacetShareItem[];
}

export interface TopCaseItem {
  slug: string;
  customer_name: string;
  vendor: string;
  industry: string;
  region: string;
  value_score: number;
  headline_metric: string;
}

export interface EntityDossier {
  name: string;
  slug: string;
  count: number;
  share: number;
  avg_value_score: number;
  avg_confidence_score: number;
  quantified_count: number;
  quantified_rate: number;
  architecture_coverage_rate: number;
  data_flow_coverage_rate: number;
  integration_coverage_rate: number;
  distinct_products_count?: number;
  top_products: FacetShareItem[];
  co_occurring_pairs: ProductPairItem[];
  architecture_layers: {
    layer: string;
    component_count: number;
    story_count: number;
    story_share: number;
    top_products: FacetShareItem[];
  }[];
  top_integrations: FacetShareItem[];
  top_industries: FacetShareItem[];
  top_use_cases: FacetShareItem[];
  top_vendors: FacetShareItem[];
  top_technical_areas: FacetShareItem[];
  top_outcomes: FacetShareItem[];
  macro_regions: FacetShareItem[];
  company_sizes: FacetShareItem[];
  sample_metrics: SampleMetricItem[];
  top_cases: TopCaseItem[];
  category?: string;
  domain?: string;
  logo?: string;
}

export interface GeneratedAnalytics {
  generated_at: string;
  summary: {
    total_records: number;
    total_vendors: number;
    total_industries: number;
    total_use_cases: number;
    total_unique_products: number;
    total_solution_components: number;
    total_quantified_metrics: number;
    quantified_impact_count: number;
    quantified_impact_rate: number;
    architecture_coverage_count: number;
    architecture_coverage_rate: number;
    data_flow_coverage_count: number;
    data_flow_coverage_rate: number;
    integration_coverage_count: number;
    integration_coverage_rate: number;
    avg_value_score: number;
    avg_confidence_score: number;
  };
  architecture_layers: ArchitectureLayerItem[];
  product_ecosystem: {
    top_products: ProductEcosystemItem[];
    co_occurring_pairs: ProductPairItem[];
    top_integrations: FacetShareItem[];
  };
  quantified_roi_benchmarks: RoiBenchmarkItem[];
  geography_and_scale: {
    macro_regions: MacroRegionItem[];
    top_countries: CountryItem[];
    company_sizes: CompanySizeItem[];
  };
  vendor_dossiers: Record<string, EntityDossier>;
  use_case_dossiers: Record<string, EntityDossier>;
  industry_dossiers: Record<string, EntityDossier>;
}

export const generatedAnalytics = rawAnalytics as unknown as GeneratedAnalytics;

export const analyticsSummary = generatedAnalytics.summary;
export const architectureLayers = generatedAnalytics.architecture_layers;
export const productEcosystem = generatedAnalytics.product_ecosystem;
export const roiBenchmarks = generatedAnalytics.quantified_roi_benchmarks;
export const geographyAndScale = generatedAnalytics.geography_and_scale;

export const getVendorDossier = (name: string): EntityDossier | undefined =>
  generatedAnalytics.vendor_dossiers?.[name];

export const getUseCaseDossier = (name: string): EntityDossier | undefined =>
  generatedAnalytics.use_case_dossiers?.[name];

export const getIndustryDossier = (name: string): EntityDossier | undefined =>
  generatedAnalytics.industry_dossiers?.[name];

export const getFacetDossier = (
  facet: "vendors" | "use-cases" | "industries",
  name: string,
): EntityDossier | undefined => {
  if (facet === "vendors") return getVendorDossier(name);
  if (facet === "use-cases") return getUseCaseDossier(name);
  return getIndustryDossier(name);
};
