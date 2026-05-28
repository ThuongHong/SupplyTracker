import { apiGet } from './client'
import type { RiskScoresResponse, RiskScore, RiskForecast } from './types'

export function fetchRiskScores(): Promise<RiskScoresResponse> {
  return apiGet<RiskScoresResponse>('/api/v1/risk/scores')
}

/**
 * @param entityType  e.g. "port" | "chokepoint"
 * @param entityId    e.g. "SGSIN"
 */
export function fetchRiskScore(
  entityType: string,
  entityId: string,
): Promise<RiskScore> {
  return apiGet<RiskScore>(
    `/api/v1/risk/scores/${encodeURIComponent(entityType)}:${encodeURIComponent(entityId)}`,
  )
}

export function fetchRiskForecast(
  entityType: string,
  entityId: string,
): Promise<RiskForecast> {
  return apiGet<RiskForecast>(
    `/api/v1/risk/forecasts/${encodeURIComponent(entityType)}:${encodeURIComponent(entityId)}`,
  )
}
