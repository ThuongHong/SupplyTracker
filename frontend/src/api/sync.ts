import { apiFetch } from './client'
import { clearBriefCache } from './brief'
import type { SyncResponse } from './types'

export function getSyncToken(): string | null {
  return (
    (import.meta.env.VITE_SYNC_BEARER_TOKEN as string | undefined) ||
    localStorage.getItem('sync_token') ||
    null
  )
}

export function triggerSync(source: string): Promise<SyncResponse> {
  return _post<SyncResponse>(`/api/v1/sync/${source}`)
}

export interface EntitySyncResponse {
  entity_type: string
  entity_id: string
  rows: number
  is_tracked: boolean
  errors: string[]
}

/** Sync = track: fetch 90 days for one entity and mark it tracked. */
export function syncPort(portid: string): Promise<EntitySyncResponse> {
  return _post<EntitySyncResponse>(`/api/v1/sync/port/${encodeURIComponent(portid)}`)
}

export function syncChokepoint(id: string): Promise<EntitySyncResponse> {
  return _post<EntitySyncResponse>(`/api/v1/sync/chokepoint/${encodeURIComponent(id)}`)
}

export function untrackPort(portid: string): Promise<EntitySyncResponse> {
  return _post<EntitySyncResponse>(`/api/v1/untrack/port/${encodeURIComponent(portid)}`)
}

export function untrackChokepoint(id: string): Promise<EntitySyncResponse> {
  return _post<EntitySyncResponse>(`/api/v1/untrack/chokepoint/${encodeURIComponent(id)}`)
}

function _post<T>(path: string): Promise<T> {
  const token = getSyncToken()
  if (!token) {
    return Promise.reject(new Error('No sync token configured'))
  }
  return apiFetch<T>(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).then((result) => {
    clearBriefCache()
    return result
  })
}
