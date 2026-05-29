import { apiGet } from './client'
import type {
  PaginatedResponse,
  PaginationParams,
  PortSummary,
  PortDetail,
  PortMetricsResponse,
} from './types'

export interface PortsParams extends PaginationParams {
  severity?: string
  q?: string
  tracked?: boolean
}

export function fetchPorts(
  params: PortsParams = {},
): Promise<PaginatedResponse<PortSummary>> {
  return apiGet<PaginatedResponse<PortSummary>>('/api/v1/ports', params)
}

export function fetchPort(id: string | number): Promise<PortDetail> {
  return apiGet<PortDetail>(`/api/v1/ports/${encodeURIComponent(id)}`)
}

export function fetchPortMetrics(
  id: string | number,
  days = 90,
): Promise<PortMetricsResponse> {
  return apiGet<PortMetricsResponse>(`/api/v1/ports/${encodeURIComponent(id)}/metrics`, { days })
}
