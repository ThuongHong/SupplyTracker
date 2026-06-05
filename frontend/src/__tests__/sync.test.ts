import { describe, expect, it, beforeEach, vi } from 'vitest'
import { clearBriefCache, fetchBrief } from '../api/brief'
import { triggerSync } from '../api/sync'

describe('sync cache invalidation', () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    vi.restoreAllMocks()
    storage.clear()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
      clear: vi.fn(() => storage.clear()),
    })
    clearBriefCache()
    localStorage.setItem('sync_token', 'test-token')
  })

  it('clears the cached brief after a successful sync', async () => {
    const today = new Date().toISOString().slice(0, 10)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ brief: 'old brief', as_of: today }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ task_id: 'abc12345', source: 'all' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ brief: 'new brief', as_of: today }),
      })
    vi.stubGlobal('fetch', fetchMock)

    expect((await fetchBrief()).brief).toBe('old brief')
    await triggerSync('all')

    expect((await fetchBrief()).brief).toBe('new brief')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
