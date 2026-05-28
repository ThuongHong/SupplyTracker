/**
 * Shared API response types for SupplyTracker backend.
 */

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  has_more: boolean
  limit: number
  offset: number
}

export interface PaginationParams {
  limit?: number
  offset?: number
}

// ─── Severity ────────────────────────────────────────────────────────────────

export type Severity = 'low' | 'elevated' | 'high' | 'critical' | 'unknown'

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  db: 'ok' | 'error'
  redis: 'ok' | 'error'
  version: string
}

// ─── Ports ───────────────────────────────────────────────────────────────────

export interface PortSummary {
  id: number
  locode: string | null
  name: string
  country: string
  region: string | null
  severity: string | null
  risk_score?: number | null
  congestion_score?: number | null
  dwell_time_hours?: number | null
  vessel_count?: number | null
  updated_at?: string | null
}

export interface RiskSnapshotEmbed {
  composite_score: number | null
  trend: string | null
  components: Record<string, number>
  updated_at: string | null
}

export interface MetricPoint {
  time: string
  value: number
}

export interface PortMetricsResponse {
  entity_id: string
  metrics: Record<string, MetricPoint[]>
}

export interface PortDetail extends PortSummary {
  radius_km: number
  twenty_ft_eq_units_year: number | null
  coordinates: [number, number] | null
  lat: number | null
  lon: number | null
  risk_score: number | null
  risk_snapshot: RiskSnapshotEmbed | null
  updated_at: string | null
  unlocode: string | null
  description?: string
  insights?: InsightItem[]
}

// ─── Chokepoints ─────────────────────────────────────────────────────────────

export interface ChokepointSummary {
  id: number
  name: string
  region?: string | null
  severity: string | null
  risk_score?: number | null
  transit_count?: number | null
  transit_time_hours?: number | null
  transit_delta_pct?: number | null
  updated_at?: string | null
}

export interface ChokepointDetail extends ChokepointSummary {
  coordinates: [number, number][] | null
  lat: number | null
  lon: number | null
  risk_score: number | null
  risk_snapshot: RiskSnapshotEmbed | null
  updated_at: string | null
  description?: string
  insights?: InsightItem[]
}

export interface ChokepointMetricsResponse {
  entity_id: string
  metrics: Record<string, MetricPoint[]>
}

export interface BreakdownDay {
  date: string
  total: number
  categories: Record<string, number>
}

export interface ChokepointBreakdownResponse {
  chokepoint_id: number
  name: string
  days: BreakdownDay[]
}

// ─── Indices ─────────────────────────────────────────────────────────────────

export interface IndexSummary {
  index_name: string
  latest_value: number
  change_pct_7d: number
  change_pct_30d: number
  unit?: string
  description?: string
}

export interface IndexPoint {
  time: string
  value: number
}

export interface IndexTimeseries {
  index_name: string
  points: IndexPoint[]
}

export interface IndicesResponse {
  items: IndexSummary[]
}

// ─── Risk ─────────────────────────────────────────────────────────────────────

export interface RiskScore {
  entity_type: string
  entity_id: string
  entity_name: string
  score: number | null
  severity: string
  freshness_status: string
  as_of: string
  time: string
}

export interface RiskScoresResponse {
  items: RiskScore[]
}

export interface ForecastPoint {
  time: string
  value: number
  lower?: number
  upper?: number
}

/** Backend returns predictions[], we map to points[] in the API layer */
export interface RiskForecast {
  entity_type: string
  entity_id: string
  entity_name: string
  horizon_days: number
  predictions: Array<{
    date: string
    predicted_score: number
    lower_bound: number | null
    upper_bound: number | null
  }>
  data_sufficiency_status: string
  created_at: string
  stale: boolean
  // mapped from predictions:
  points: ForecastPoint[]
}

// ─── Story ────────────────────────────────────────────────────────────────────

export interface StoryEvent {
  id: string
  title: string
  narrative: string
  entity_type?: string
  entity_id?: string
  entity_name?: string
  severity: string
  timestamp: string
}

export interface StoryResponse {
  events: StoryEvent[]
  count: number
}

// ─── Insights ────────────────────────────────────────────────────────────────

export interface InsightItem {
  id: string
  title: string
  attention_level: string
  narrative?: string
  entity_type?: string
  entity_id?: string
  entity_name?: string
  timestamp?: string
}

export interface InsightsResponse {
  items: InsightItem[]
  count: number
}

// ─── Stats / Coverage ────────────────────────────────────────────────────────

export interface CoverageItem {
  source: string
  entity_type: string
  total: number
  covered: number
  coverage_pct: number
}

export interface CoverageResponse {
  items: CoverageItem[]
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string
  entity_context?: Array<{ entity_type: string; entity_id: string; entity_name?: string }>
}

export interface ChatChunk {
  type: 'text' | 'done' | 'error'
  content?: string
  error?: string
}

// ─── News ──────────────────────────────────────────────────────────────────────
export interface NewsItem {
  id: number
  entity_type: string
  entity_id: string
  url: string
  title: string
  source: string
  published_at: string
  summary: string | null
  language: string
  fetched_at: string
}

export interface NewsListResponse {
  items: NewsItem[]
  count: number
}

// ─── Sync ──────────────────────────────────────────────────────────────────────
export interface SyncResponse {
  task_id: string
  source: string
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface EntityDashboardCharts {
  vessel_mix?: Array<{ time: string; anchored: number; moored: number; underway: number }>
  dwell_hours?: Array<{ time: string; value: number }>
  throughput?: Array<{ time: string; value: number }>
  vessel_count?: Array<{ time: string; value: number }>
  median_speed?: Array<{ time: string; value: number }>
  risk_trend?: Array<{ time: string; value: number }>
  forecast?: Array<{ time: string; value: number; lo?: number; hi?: number }>
  indices?: Array<{ time: string; fbx?: number; wci?: number }>
  bunker?: Array<{ time: string; value: number }>
}

export interface EntityDashboardStats {
  risk_latest?: number | null
  risk_30d_mean?: number | null
  risk_30d_max?: number | null
  dwell_latest?: number | null
  vessel_count_latest?: number | null
  fbx_pct_7d?: number | null
}

export interface DashboardDisruption {
  source_entity_id: string
  source_entity_name: string
  target_entity_id: string
  target_entity_name: string
  severity: string
  confidence: number
  explanation: string
  status: string
}

export interface DashboardResponse {
  entity: { type: string; id: string; name: string }
  window: string
  charts: EntityDashboardCharts
  stats: EntityDashboardStats
  disruptions: DashboardDisruption[]
}
