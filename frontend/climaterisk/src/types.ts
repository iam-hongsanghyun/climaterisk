// Mirror of the backend domain model (src/climaterisk/core/entities.py).

export type DepthLevel = "asset" | "portfolio" | "national";
export type GeographicScale = "point" | "footprint" | "regional" | "national";

export type ExposureSource = "points" | "litpop" | "osm" | "crop";

export interface Asset {
  id: string;
  name: string;
  lat: number;
  lon: number;
  sector: string;
  geographic_scale: GeographicScale;
  value: number;
  currency: string;
  annual_emissions_tco2e: number | null;
  vulnerability_class: string | null;
  geometry?: Record<string, unknown> | null; // GeoJSON footprint (Polygon/MultiPolygon)
  properties: Record<string, string | number | boolean>;
}

export interface Scenario {
  climate: string;
  transition: string;
  anchor_years: number[];
}

export interface RunConfig {
  perils: string[];
  discount_rate: number;
  exposure_source?: ExposureSource;
  options: Record<string, string | number | boolean>;
}

export interface VulnerabilityOverride {
  tc_v_half?: number;
  wf_max_mdd?: number;
  flood_mdr?: number[];
}

export interface Portfolio {
  id: string;
  name: string;
  depth_level: DepthLevel;
  assets: Asset[];
  scenario: Scenario;
  run_config: RunConfig;
  vulnerability_overrides?: Record<string, VulnerabilityOverride>;
}

// Bundled libraries (assets/libraries/*.json), as served by /api/libraries.
export interface SectorOption {
  id: string;
  label: string;
  default_vulnerability_class: string;
  emission_intensity_tco2e_per_musd: number;
}
export interface PerilOption {
  id: string;
  label: string;
  supported_mvp: boolean;
  future_source?: string;
  reason?: string;
  historical_only?: boolean;
  coverage?: string;
}
export interface ScenarioOption {
  id: string;
  label: string;
}
export interface VulnerabilityClass {
  id: string;
  label: string;
  tc_v_half: number;
  wf_max_mdd: number;
  flood_mdr: number[];
}

export interface DataSourceCategory {
  id: string;
  label: string;
  note?: string;
}
export type FetchMode = "auto" | "manual" | "needs_login" | "operational";
export interface DataSourceFetch {
  mode: FetchMode;
  source?: "dataapi" | "aqueduct";
  peril?: string;
}
export interface DataSource {
  id: string;
  category: string;
  name: string;
  url: string;
  access: string;
  license: string;
  for: string;
  scenarios?: string;
  place_at?: string;
  required?: boolean;
  fetch?: DataSourceFetch;
  notes?: string;
}
export interface DataSourcesLib {
  categories: DataSourceCategory[];
  sources: DataSource[];
}

export interface Libraries {
  sectors: { sectors: SectorOption[] };
  perils: { perils: PerilOption[] };
  scenarios: {
    climate: ScenarioOption[];
    transition: ScenarioOption[];
    anchor_years: number[];
  };
  impact_functions: { classes: VulnerabilityClass[]; flood_depth_m: number[] };
  carbon_prices?: { prices: Record<string, Record<string, number>> };
  data_sources: DataSourcesLib;
}

export interface HazardCatalogEntry {
  peril: string;
  haz_type: string;
  climate_scenario: string;
  region: string;
  year: number | null;
  units: string;
  n_events: number;
  n_centroids: number;
  source: string;
  license: string;
}
export interface HazardCatalog {
  dir: string;
  entries: HazardCatalogEntry[];
}

// Run results (mirror of src/climaterisk/engines/base.py + runs/store.py).
export interface AssetImpact {
  id: string;
  lat: number;
  lon: number;
  eai: number;
  country: string | null;
}
export interface FreqCurve {
  return_periods: number[];
  impact: number[];
}
export interface PhysicalRunResult {
  peril: string;
  status: string;
  target_year: number | null;
  aai_agg: number;
  present_aai_agg: number | null;
  delta_pct: number | null;
  total_value: number;
  per_asset: AssetImpact[];
  freq_curve: FreqCurve | null;
  result_kind?: "monetary" | "yield" | "productivity";
  metric_unit?: string | null;
  detail: string | null;
}
export interface PhysicalRunOutput {
  status: string;
  climate_scenario: string;
  results: PhysicalRunResult[];
  detail: string | null;
}
// Adaptation cost-benefit (mirror of engines/base.py + worker/cost_benefit.py).
export interface MeasureSpec {
  name: string;
  cost: number;
  damage_reduction: number; // 0..1
  hazard_freq_cutoff?: number;
  risk_transf_attach?: number;
  risk_transf_cover?: number;
}
export interface MeasureResult {
  name: string;
  cost: number;
  benefit: number;
  benefit_cost_ratio: number | null;
}
export interface CostBenefitResult {
  status: string;
  peril: string;
  future_year: number | null;
  discount_rate: number;
  currency: string;
  tot_climate_risk: number;
  measures: MeasureResult[];
  detail: string | null;
}

// Monte-Carlo uncertainty (mirror of engines/base.py + worker/uncertainty.py).
export interface UncertaintyResult {
  status: string;
  peril: string;
  future_year: number | null;
  n_samples: number;
  currency: string;
  aai_mean: number;
  aai_std: number;
  aai_p5: number;
  aai_p50: number;
  aai_p95: number;
  distribution: number[];
  sensitivity: Record<string, number>;
  sensitivity_s1?: Record<string, number>;
  sensitivity_st?: Record<string, number>;
  sensitivity_method?: string;
  detail: string | null;
}

// LitPop modeled exposure (mirror of engines/base.py + worker/litpop.py).
export interface LitPopResult {
  status: string;
  country: string;
  peril: string;
  future_year: number | null;
  total_value: number;
  aai_agg: number;
  n_points: number;
  currency: string;
  per_point: { lat: number; lon: number; eai: number }[];
  detail: string | null;
}

// Data ingestion (mirror of engines/base.py IngestResult + worker/ingest.py).
export interface IngestResult {
  status: string;
  source: string;
  peril: string;
  entry: HazardCatalogEntry | null;
  detail: string | null;
}

export interface Run {
  id: string;
  session_id: string;
  status: "queued" | "running" | "done" | "error";
  climate_scenario: string;
  perils: string[];
  output:
    | PhysicalRunOutput
    | CostBenefitResult
    | UncertaintyResult
    | LitPopResult
    | IngestResult
    | null;
  detail: string | null;
  created_at: string;
  updated_at: string;
}

// Transition risk (mirror of src/climaterisk/transition/carbon.py).
export interface AssetCarbon {
  id: string;
  name: string;
  emissions_tco2e: number;
  emissions_source: "reported" | "sector_proxy";
  annual_cost_by_year: Record<string, number>;
  npv: number;
}
export interface TransitionResult {
  scenario: string;
  discount_rate: number;
  base_year: number;
  years: number[];
  total_cost_by_year: number[];
  total_npv: number;
  per_asset: AssetCarbon[];
  method: string;
  detail: string | null;
}
