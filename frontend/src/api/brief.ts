import { apiGet } from './client'

export interface Brief {
  brief: string
  as_of: string
}

const BRIEF_CACHE_KEY = 'supplytracker:brief:v1'

let _cache: Brief | null = null

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function isFreshBrief(data: Brief | null): data is Brief {
  return data !== null && data.as_of === todayIso()
}

function readStoredBrief(): Brief | null {
  try {
    const raw = localStorage.getItem(BRIEF_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<Brief>
    if (typeof parsed.brief !== 'string' || typeof parsed.as_of !== 'string') {
      return null
    }
    return { brief: parsed.brief, as_of: parsed.as_of }
  } catch {
    return null
  }
}

function writeStoredBrief(data: Brief): void {
  try {
    localStorage.setItem(BRIEF_CACHE_KEY, JSON.stringify(data))
  } catch {
    // Storage can be unavailable in private browsing or test environments.
  }
}

export function getCachedBrief(): Brief | null {
  if (isFreshBrief(_cache)) return _cache
  const stored = readStoredBrief()
  if (isFreshBrief(stored)) {
    _cache = stored
    return stored
  }
  return null
}

export function clearBriefCache(): void {
  _cache = null
  try {
    localStorage.removeItem(BRIEF_CACHE_KEY)
  } catch {
    // Ignore storage failures; memory cache is already cleared.
  }
}

export async function fetchBrief(): Promise<Brief> {
  const cached = getCachedBrief()
  if (cached) return cached

  const data = await apiGet<Brief>('/api/v1/brief')
  _cache = data
  writeStoredBrief(data)
  return data
}
