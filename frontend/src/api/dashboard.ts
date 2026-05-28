import { apiFetch } from './client'
import type { DashboardResponse } from './types'

export function fetchEntityDashboard(
  entityType: string,
  entityId: string,
  window: '7d' | '30d' | '90d' = '30d',
): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>(
    `/api/v1/entities/${entityType}/${entityId}/dashboard`,
    { method: 'GET', params: { window } },
  )
}
