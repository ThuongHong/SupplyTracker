import { apiFetch } from './client'
import type { SyncResponse } from './types'

export function getSyncToken(): string | null {
  return (
    (import.meta.env.VITE_SYNC_BEARER_TOKEN as string | undefined) ||
    localStorage.getItem('sync_token') ||
    null
  )
}

export function triggerSync(source: string): Promise<SyncResponse> {
  const token = getSyncToken()
  if (!token) {
    return Promise.reject(new Error('No sync token configured'))
  }
  return apiFetch<SyncResponse>(`/api/v1/sync/${source}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
}
