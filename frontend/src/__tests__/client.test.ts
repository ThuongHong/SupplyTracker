import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ApiError, AuthError, RateLimitError, apiFetch } from '../api/client'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function makeResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'Content-Type': 'application/json', ...headers }),
    json: () => Promise.resolve(body),
    body: null,
  } as unknown as Response
}

describe('apiFetch', () => {
  beforeEach(() => mockFetch.mockReset())

  it('returns parsed JSON on 200', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ ok: true }))
    const result = await apiFetch('/api/v1/health')
    expect(result).toEqual({ ok: true })
  })

  it('throws AuthError on 401', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({}, 401))
    await expect(apiFetch('/api/v1/health')).rejects.toBeInstanceOf(AuthError)
  })

  it('throws RateLimitError on 429', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({}, 429, { 'Retry-After': '30' }))
    const err = await apiFetch('/api/v1/health').catch((e) => e)
    expect(err).toBeInstanceOf(RateLimitError)
    expect((err as RateLimitError).retryAfter).toBe(30)
  })

  it('throws ApiError on 500', async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse({ detail: 'Internal server error' }, 500),
    )
    const err = await apiFetch('/api/v1/health').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Internal server error')
    expect(err.status).toBe(500)
  })

  it('appends query params', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse([]))
    await apiFetch('/api/v1/ports', { params: { limit: 10, offset: 0 } })
    const calledUrl = mockFetch.mock.calls[0][0] as string
    expect(calledUrl).toContain('limit=10')
    expect(calledUrl).toContain('offset=0')
  })

  it('omits null/undefined params', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse([]))
    await apiFetch('/api/v1/ports', { params: { limit: 10, severity: undefined } })
    const calledUrl = mockFetch.mock.calls[0][0] as string
    expect(calledUrl).not.toContain('severity')
  })
})
