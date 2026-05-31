import { apiGet } from './client'

export interface Brief {
  brief: string
  as_of: string
}

let _cache: Brief | null = null

export function getCachedBrief(): Brief | null {
  return _cache
}

export async function fetchBrief(): Promise<Brief> {
  const data = await apiGet<Brief>('/api/v1/brief')
  _cache = data
  return data
}
