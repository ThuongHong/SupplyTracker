import { apiFetch } from './client'
import type { NewsListResponse } from './types'

export interface FetchEntityNewsOptions {
  limit?: number
  since?: string  // ISO 8601
}

export function fetchEntityNews(
  entityType: string,
  entityId: string,
  opts: FetchEntityNewsOptions = {},
): Promise<NewsListResponse> {
  const params: Record<string, string | number> = {}
  if (opts.limit !== undefined) params.limit = opts.limit
  if (opts.since !== undefined) params.since = opts.since
  return apiFetch<NewsListResponse>(`/api/v1/entities/${entityType}/${entityId}/news`, {
    method: 'GET',
    params,
  })
}
