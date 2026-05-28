import { apiGet } from './client'
import type { CoverageResponse } from './types'

export interface CoverageParams {
  source?: string
  entity_type?: string
}

export function fetchCoverage(params: CoverageParams = {}): Promise<CoverageResponse> {
  return apiGet<CoverageResponse>('/api/v1/stats/coverage', params)
}
