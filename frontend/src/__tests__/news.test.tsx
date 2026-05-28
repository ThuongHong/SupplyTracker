/**
 * Tests for the news feature frontend:
 *  8.1 — fetchEntityNews (URL construction + response parsing)
 *  8.2 — SyncButton (hidden without token, fires POST once, disabled after click, error re-enables)
 *  8.3 — EventLog (tab switching and news rendering with mocked fetch)
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'

// ─── 8.1 — fetchEntityNews ───────────────────────────────────────────────────

// These vi.mock() calls must appear before importing the mocked modules.
vi.mock('../api/sync', () => ({
  getSyncToken: vi.fn(),
  triggerSync: vi.fn(),
}))

vi.mock('../api/story', () => ({
  fetchStory: vi.fn(),
}))

vi.mock('../api/news', () => ({
  fetchEntityNews: vi.fn(),
}))

// Now import the real fetchEntityNews for 8.1 (we need its actual implementation,
// not the mock). We do this by bypassing the module mock with a direct import of
// the real module — but vi.mock() hoists and intercepts all imports from '../api/news'.
// Instead we test fetchEntityNews by importing the *unmocked* module via a separate
// describe block that re-uses global fetch stubbing.

// For 8.1 we import the real implementation directly (vi.mock is module-scoped, so
// we can import the real module using an alias via importActual inside the test).
import { fetchEntityNews as fetchEntityNewsMocked } from '../api/news'
import { getSyncToken, triggerSync } from '../api/sync'
import { fetchStory } from '../api/story'
import { SyncButton } from '../components/SyncButton'
import { EventLog } from '../components/EventLog'

// ─── Global fetch mock (used for 8.1 via importActual) ───────────────────────

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function makeResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: () => Promise.resolve(body),
    body: null,
  } as unknown as Response
}

// ─── 8.1 — fetchEntityNews ───────────────────────────────────────────────────

describe('fetchEntityNews', () => {
  // Use importActual to get the real (non-mocked) implementation.
  let fetchEntityNews: typeof fetchEntityNewsMocked

  beforeEach(async () => {
    mockFetch.mockReset()
    const mod = await vi.importActual<typeof import('../api/news')>('../api/news')
    fetchEntityNews = mod.fetchEntityNews
  })

  it('calls correct URL for port entity', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [], count: 0 }))
    await fetchEntityNews('port', 'SGSIN')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/v1/entities/port/SGSIN/news')
  })

  it('passes limit as query param', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [], count: 0 }))
    await fetchEntityNews('port', 'SGSIN', { limit: 10 })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('limit=10')
  })

  it('passes since as query param', async () => {
    const since = '2026-01-01T00:00:00Z'
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [], count: 0 }))
    await fetchEntityNews('port', 'SGSIN', { since })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain(`since=${encodeURIComponent(since)}`)
  })

  it('omits params when not provided', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [], count: 0 }))
    await fetchEntityNews('port', 'SGSIN')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).not.toContain('limit')
    expect(url).not.toContain('since')
  })

  it('returns parsed response with items and count', async () => {
    const newsItem = {
      id: 42,
      entity_type: 'port',
      entity_id: 'SGSIN',
      url: 'https://example.com/news/1',
      title: 'Singapore port congestion',
      source: 'Reuters',
      published_at: '2026-05-01T12:00:00Z',
      summary: null,
      language: 'en',
      fetched_at: '2026-05-01T13:00:00Z',
    }
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [newsItem], count: 1 }))
    const result = await fetchEntityNews('port', 'SGSIN')
    expect(result.count).toBe(1)
    expect(result.items).toHaveLength(1)
    expect(result.items[0].title).toBe('Singapore port congestion')
    expect(result.items[0].source).toBe('Reuters')
  })

  it('works for chokepoint entity type', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ items: [], count: 0 }))
    await fetchEntityNews('chokepoint', 'SUEZ')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/v1/entities/chokepoint/SUEZ/news')
  })
})

// ─── 8.2 — SyncButton ────────────────────────────────────────────────────────

describe('SyncButton', () => {
  beforeEach(() => {
    vi.mocked(getSyncToken).mockReset()
    vi.mocked(triggerSync).mockReset()
  })

  it('returns null (renders nothing) when no token', () => {
    vi.mocked(getSyncToken).mockReturnValue(null)
    const { container } = render(<SyncButton />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a button when token is present', () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    render(<SyncButton />)
    expect(screen.getByRole('button')).toBeDefined()
    expect(screen.getByText('Sync')).toBeDefined()
  })

  it('fires triggerSync once on click', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    vi.mocked(triggerSync).mockResolvedValueOnce({ task_id: 'abc12345', source: 'all' })
    render(<SyncButton />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
    })
    expect(vi.mocked(triggerSync)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(triggerSync)).toHaveBeenCalledWith('all')
  })

  it('disables button after successful click', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    vi.mocked(triggerSync).mockResolvedValueOnce({ task_id: 'abc12345', source: 'all' })
    render(<SyncButton />)
    const btn = screen.getByRole('button')
    await act(async () => {
      fireEvent.click(btn)
    })
    expect(btn).toHaveProperty('disabled', true)
  })

  it('shows success message with task_id prefix after successful click', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    vi.mocked(triggerSync).mockResolvedValueOnce({ task_id: 'abc12345-full-uuid', source: 'all' })
    render(<SyncButton />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
    })
    // Status shows first 8 chars of task_id
    await waitFor(() => {
      expect(screen.getByText(/Sync started/)).toBeDefined()
      expect(screen.getByText(/abc12345/)).toBeDefined()
    })
  })

  it('re-enables button on error', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    vi.mocked(triggerSync).mockRejectedValueOnce(new Error('Network error'))
    render(<SyncButton />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
    })
    expect(screen.getByRole('button')).toHaveProperty('disabled', false)
  })

  it('shows error message on failure', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    vi.mocked(triggerSync).mockRejectedValueOnce(new Error('Network error'))
    render(<SyncButton />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
    })
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeDefined()
    })
  })

  it('does not call triggerSync again if button is already disabled', async () => {
    vi.mocked(getSyncToken).mockReturnValue('test-token')
    // First call resolves after a delay so the button stays disabled
    vi.mocked(triggerSync).mockResolvedValueOnce({ task_id: 'abc12345', source: 'all' })
    render(<SyncButton />)
    const btn = screen.getByRole('button')
    // Click once (succeeds, disables)
    await act(async () => {
      fireEvent.click(btn)
    })
    // Try clicking again while disabled
    fireEvent.click(btn)
    // triggerSync should still have been called only once
    expect(vi.mocked(triggerSync)).toHaveBeenCalledTimes(1)
  })
})

// ─── 8.3 — EventLog ──────────────────────────────────────────────────────────

describe('EventLog', () => {
  beforeEach(() => {
    vi.mocked(fetchStory).mockReset()
    vi.mocked(fetchEntityNewsMocked).mockReset()
  })

  it('shows both System events and News tabs by default', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })
    expect(screen.getByText('System events')).toBeDefined()
    expect(screen.getByText('News')).toBeDefined()
  })

  it('starts on System events tab (not News)', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })
    // fetchEntityNews should NOT have been called on initial render
    expect(vi.mocked(fetchEntityNewsMocked)).not.toHaveBeenCalled()
  })

  it('renders news items when News tab is clicked', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    vi.mocked(fetchEntityNewsMocked).mockResolvedValueOnce({
      items: [
        {
          id: 1,
          entity_type: 'port',
          entity_id: 'SGSIN',
          url: 'http://example.com/news/1',
          title: 'Test News Title',
          source: 'Reuters',
          published_at: '2026-05-01T00:00:00Z',
          summary: null,
          language: 'en',
          fetched_at: '2026-05-01T01:00:00Z',
        },
      ],
      count: 1,
    })

    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })

    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })

    await waitFor(() => {
      expect(screen.getByText('Test News Title')).toBeDefined()
    })

    expect(vi.mocked(fetchEntityNewsMocked)).toHaveBeenCalledWith('port', 'SGSIN')
  })

  it('news link opens in a new tab', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    vi.mocked(fetchEntityNewsMocked).mockResolvedValueOnce({
      items: [
        {
          id: 2,
          entity_type: 'port',
          entity_id: 'SGSIN',
          url: 'http://example.com/news/2',
          title: 'Shipping News',
          source: 'Bloomberg',
          published_at: '2026-05-02T00:00:00Z',
          summary: null,
          language: 'en',
          fetched_at: '2026-05-02T01:00:00Z',
        },
      ],
      count: 1,
    })

    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })

    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })

    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'Shipping News' })
      expect(link).toHaveProperty('target', '_blank')
      expect(link).toHaveProperty('href', 'http://example.com/news/2')
    })
  })

  it('shows empty state message when no news items', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    vi.mocked(fetchEntityNewsMocked).mockResolvedValueOnce({ items: [], count: 0 })

    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })

    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })

    await waitFor(() => {
      expect(screen.getByText('No news available')).toBeDefined()
    })
  })

  it('does not refetch news on repeated tab visits', async () => {
    vi.mocked(fetchStory).mockResolvedValue({ events: [], count: 0 })
    vi.mocked(fetchEntityNewsMocked).mockResolvedValue({ items: [], count: 0 })

    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })

    // Click News (first time — triggers fetch)
    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })
    await waitFor(() => expect(vi.mocked(fetchEntityNewsMocked)).toHaveBeenCalledTimes(1))

    // Switch back to System events, then back to News
    await act(async () => {
      fireEvent.click(screen.getByText('System events'))
    })
    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })

    // fetchEntityNews should still have been called only once
    expect(vi.mocked(fetchEntityNewsMocked)).toHaveBeenCalledTimes(1)
  })

  it('shows source next to news items', async () => {
    vi.mocked(fetchStory).mockResolvedValueOnce({ events: [], count: 0 })
    vi.mocked(fetchEntityNewsMocked).mockResolvedValueOnce({
      items: [
        {
          id: 3,
          entity_type: 'port',
          entity_id: 'SGSIN',
          url: 'http://example.com/news/3',
          title: 'Port Delay Alert',
          source: 'AP News',
          published_at: '2026-05-03T00:00:00Z',
          summary: null,
          language: 'en',
          fetched_at: '2026-05-03T01:00:00Z',
        },
      ],
      count: 1,
    })

    await act(async () => {
      render(<EventLog entityType="port" entityId="SGSIN" />)
    })

    await act(async () => {
      fireEvent.click(screen.getByText('News'))
    })

    await waitFor(() => {
      expect(screen.getByText('AP News')).toBeDefined()
    })
  })
})
