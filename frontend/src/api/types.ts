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

export type Severity = 'low' | 'moderate' | 'high' | 'critical'

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  db: 'ok' | 'error'
  redis: 'ok' | 'error'
  version: string
}

// ─── Ports ───────────────────────────────────────────────────────────────────

export interface PortSummary {
  id: string
  name: string
  country: string
  lat: number
  lon: number
  severity: Severity
  risk_score?: number
  vessel_count?: number
  congestion_index?: number
  updated_at: string
}

export interface PortDetail extends PortSummary {
  unlocode?: string
  region?: string
  description?: string
  insights?: InsightItem[]
  risk_snapshot?: RiskSnapshot
}

// ─── Chokepoints ─────────────────────────────────────────────────────────────

export interface ChokepointSummary {
  id: string
  name: string
  region: string
  lat: number
  lon: number
  severity: Severity
  risk_score?: number
  transit_count?: number
  updated_at: string
}

export interface ChokepointDetail extends ChokepointSummary {
  description?: string
  insights?: InsightItem[]
  risk_snapshot?: RiskSnapshot
}

export interface BreakdownDay {
  date: string
  value: number
  label?: string
}

export interface ChokepointBreakdown {
  entity_id: string
  entity_name: string
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

export interface RiskSnapshot {
  composite_score: number
  trend: 'rising' | 'falling' | 'stable'
  components: Record<string, number>
  updated_at: string
}

export interface RiskScore {
  entity_type: string
  entity_id: string
  entity_name: string
  composite_score: number
  severity: Severity
  trend: 'rising' | 'falling' | 'stable'
  snapshot?: RiskSnapshot
  updated_at: string
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

export interface RiskForecast {
  entity_type: string
  entity_id: string
  entity_name: string
  points: ForecastPoint[]
  generated_at: string
}

// ─── Story ────────────────────────────────────────────────────────────────────

export interface StoryEvent {
  id: string
  title: string
  narrative: string
  entity_type?: string
  entity_id?: string
  entity_name?: string
  severity: Severity
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
  attention_level: Severity
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
  entity_context?: {
    entity_type: string
    entity_id: string
    entity_name?: string
  }
}

export interface ChatChunk {
  type: 'text' | 'done' | 'error'
  content?: string
  error?: string
}
