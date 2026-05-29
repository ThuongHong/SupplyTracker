import { apiFetch } from './client'
import type { DashboardResponse, EntitySummaryResponse } from './types'

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

export function fetchEntitySummary(
  entityType: string,
  entityId: string,
  window: '7d' | '30d' | '90d' = '30d',
): Promise<EntitySummaryResponse> {
  return apiFetch<EntitySummaryResponse>(
    `/api/v1/entities/${entityType}/${entityId}/summary`,
    { method: 'GET', params: { window } },
  )
}
