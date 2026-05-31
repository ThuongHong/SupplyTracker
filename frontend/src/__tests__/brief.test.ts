import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchBrief } from '../api/brief'

describe('fetchBrief', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
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
})
