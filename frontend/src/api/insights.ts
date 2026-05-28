import { apiGet } from './client'
import type { InsightsResponse, Severity } from './types'

export interface InsightsParams {
  attention_level?: Severity
  limit?: number
}

export function fetchInsights(params: InsightsParams = {}): Promise<InsightsResponse> {
  return apiGet<InsightsResponse>('/api/v1/insights', params)
}
