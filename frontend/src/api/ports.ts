import { apiGet } from './client'
import type {
  PaginatedResponse,
  PaginationParams,
  PortSummary,
  PortDetail,
  Severity,
} from './types'

export interface PortsParams extends PaginationParams {
  severity?: Severity
}

export function fetchPorts(
  params: PortsParams = {},
): Promise<PaginatedResponse<PortSummary>> {
  return apiGet<PaginatedResponse<PortSummary>>('/api/v1/ports', params)
}

export function fetchPort(id: string): Promise<PortDetail> {
  return apiGet<PortDetail>(`/api/v1/ports/${encodeURIComponent(id)}`)
}
