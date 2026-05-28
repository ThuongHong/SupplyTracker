/**
 * Base fetch client with error-envelope handling.
 *
 * Error envelope shape (from backend):
 *   { detail: string } or { detail: [{ msg: string }] }
 *
 * Special cases:
 *   401 → throws AuthError
 *   429 → throws RateLimitError
 *   other 4xx/5xx → throws ApiError
 */

function getBaseUrl(): string {
  // Vite injects VITE_ env vars at build time
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (configured) return configured
  return 'http://localhost:8000'
}

// ─── Error types ────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export class AuthError extends ApiError {
  constructor(message = 'Unauthorized') {
    super(401, message)
    this.name = 'AuthError'
  }
}

export class RateLimitError extends ApiError {
  constructor(public readonly retryAfter?: number) {
    super(429, 'Rate limit exceeded')
    this.name = 'RateLimitError'
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function extractMessage(body: unknown): string {
  if (typeof body === 'object' && body !== null) {
    const b = body as Record<string, unknown>
    if (typeof b.detail === 'string') return b.detail
    if (Array.isArray(b.detail) && b.detail.length) {
      const first = b.detail[0]
      if (typeof first === 'object' && first !== null && 'msg' in first) {
        return String((first as Record<string, unknown>).msg)
      }
    }
    if (typeof b.message === 'string') return b.message
  }
  return 'An unexpected error occurred'
}

// ─── Core fetch wrapper ─────────────────────────────────────────────────────

export interface FetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Query parameters — appended to the URL */
  params?: object
}

export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { body, params, headers: extraHeaders, ...rest } = options

  // Build URL
  const url = new URL(path, getBaseUrl())
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (
        v !== null &&
        v !== undefined &&
        (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
      ) {
        url.searchParams.set(k, String(v))
      }
    }
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(extraHeaders as Record<string, string>),
  }

  let serializedBody: string | undefined
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    serializedBody = JSON.stringify(body)
  }

  const response = await fetch(url.toString(), {
    ...rest,
    headers,
    body: serializedBody,
  })

  // Handle special HTTP status codes before parsing body
  if (response.status === 401) {
    throw new AuthError()
  }

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After')
    throw new RateLimitError(retryAfter ? parseInt(retryAfter, 10) : undefined)
  }

  // Parse body (JSON for non-streaming, ignore errors on empty)
  let parsed: unknown = undefined
  const contentType = response.headers.get('Content-Type') ?? ''
  if (contentType.includes('application/json')) {
    try {
      parsed = await response.json()
    } catch {
      parsed = undefined
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      extractMessage(parsed),
      parsed,
    )
  }

  return parsed as T
}

/** GET convenience */
export function apiGet<T>(
  path: string,
  params?: FetchOptions['params'],
): Promise<T> {
  return apiFetch<T>(path, { method: 'GET', params })
}

/** POST convenience */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'POST', body })
}

/**
 * SSE streaming fetch — returns an async generator of parsed JSON chunks.
 * The server should send `data: {...}\n\n` lines.
 */
export async function* apiStream(
  path: string,
  body: unknown,
): AsyncGenerator<unknown> {
  const url = new URL(path, getBaseUrl())

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
  })

  if (response.status === 401) throw new AuthError()
  if (response.status === 429) throw new RateLimitError()
  if (!response.ok) {
    const parsed = await response.json().catch(() => undefined)
    throw new ApiError(response.status, extractMessage(parsed), parsed)
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') return
          try {
            yield JSON.parse(raw)
          } catch {
            // yield raw string on parse failure
            yield raw
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
