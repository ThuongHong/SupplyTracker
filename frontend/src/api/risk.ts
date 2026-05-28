import { apiGet } from './client'
import type { RiskScoresResponse, RiskScore, RiskForecast } from './types'

export function fetchRiskScores(): Promise<RiskScoresResponse> {
  return apiGet<RiskScoresResponse>('/api/v1/risk/scores')
}

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
  return apiGet<unknown>(
    `/api/v1/risk/forecasts/${encodeURIComponent(entityType)}:${encodeURIComponent(entityId)}`,
  ).then((raw) => {
    const d = raw as Record<string, unknown>
    const preds = (d.predictions as Array<Record<string, unknown>>) ?? []
    return {
      ...d,
      points: preds.map((p) => ({
        time: p.date as string,
        value: p.predicted_score as number,
        lower: p.lower_bound as number | undefined,
        upper: p.upper_bound as number | undefined,
      })),
    } as RiskForecast
  })
}
