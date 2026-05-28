import { apiGet } from './client'
import type {
  PaginatedResponse,
  PaginationParams,
  ChokepointSummary,
  ChokepointDetail,
  ChokepointBreakdown,
  Severity,
} from './types'

export interface ChokepointsParams extends PaginationParams {
  severity?: Severity
}

export function fetchChokepoints(
  params: ChokepointsParams = {},
): Promise<PaginatedResponse<ChokepointSummary>> {
  return apiGet<PaginatedResponse<ChokepointSummary>>('/api/v1/chokepoints', params)
}

export function fetchChokepoint(id: string): Promise<ChokepointDetail> {
  return apiGet<ChokepointDetail>(`/api/v1/chokepoints/${encodeURIComponent(id)}`)
}

export function fetchChokepointBreakdown(id: string): Promise<ChokepointBreakdown> {
  return apiGet<ChokepointBreakdown>(
    `/api/v1/chokepoints/${encodeURIComponent(id)}/breakdown`,
  )
}
