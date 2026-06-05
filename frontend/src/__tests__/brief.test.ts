import { describe, it, expect, vi, beforeEach } from 'vitest'
import { clearBriefCache, fetchBrief } from '../api/brief'

describe('fetchBrief', () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
      clear: vi.fn(() => storage.clear()),
    })
    localStorage.clear()
    clearBriefCache()
  })

  it('returns brief + as_of from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ brief: '## Hi', as_of: '2026-05-31' }),
      }),
    )

    const result = await fetchBrief()

    expect(result.brief).toBe('## Hi')
    expect(result.as_of).toBe('2026-05-31')
  })

  it('reuses a same-day cached brief without another API call', async () => {
    const today = new Date().toISOString().slice(0, 10)
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ brief: '## Cached', as_of: today }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const first = await fetchBrief()
    const second = await fetchBrief()

    expect(first.brief).toBe('## Cached')
    expect(second.brief).toBe('## Cached')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
