import { apiGet } from './client'
import type {
  PaginatedResponse,
  PaginationParams,
  ChokepointSummary,
  ChokepointDetail,
  ChokepointBreakdownResponse,
  ChokepointMetricsResponse,
} from './types'

export interface ChokepointsParams extends PaginationParams {
  severity?: string
}

export function fetchChokepoints(
  params: ChokepointsParams = {},
): Promise<PaginatedResponse<ChokepointSummary>> {
  return apiGet<PaginatedResponse<ChokepointSummary>>('/api/v1/chokepoints', params)
}

export function fetchChokepoint(id: string | number): Promise<ChokepointDetail> {
  return apiGet<ChokepointDetail>(`/api/v1/chokepoints/${encodeURIComponent(id)}`)
}

export function fetchChokepointBreakdown(id: string | number): Promise<ChokepointBreakdownResponse> {
  return apiGet<ChokepointBreakdownResponse>(
    `/api/v1/chokepoints/${encodeURIComponent(id)}/breakdown`,
  )
}

export function fetchChokepointMetrics(
  id: string | number,
  days = 90,
): Promise<ChokepointMetricsResponse> {
  return apiGet<ChokepointMetricsResponse>(
    `/api/v1/chokepoints/${encodeURIComponent(id)}/metrics`,
    { days },
  )
}
