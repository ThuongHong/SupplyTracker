/**
 * Tests for entity charts and chatbot context features:
 *  8.1 — fetchEntityDashboard (URL construction + response parsing)
 *  8.2 — WindowPicker (option rendering + onChange)
 *  8.3 — AnomalyCard (z-score stats + insufficient-data state)
 *  8.4 — openChatWithPrompt + AskAIButton
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ─── ResizeObserver stub (required by recharts in jsdom) ─────────────────────

global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// ─── Global fetch mock ───────────────────────────────────────────────────────

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

// ─── 8.1 — fetchEntityDashboard ─────────────────────────────────────────────

describe('fetchEntityDashboard', () => {
  let fetchEntityDashboard: typeof import('../api/dashboard').fetchEntityDashboard

  beforeEach(async () => {
    mockFetch.mockReset()
    const mod = await vi.importActual<typeof import('../api/dashboard')>('../api/dashboard')
    fetchEntityDashboard = mod.fetchEntityDashboard
  })

  it('calls correct URL with window param', async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse({
        entity: { type: 'port', id: 'SGSIN', name: 'Singapore' },
        window: '30d',
        charts: {},
        stats: {},
        disruptions: [],
      }),
    )
    await fetchEntityDashboard('port', 'SGSIN', '30d')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/v1/entities/port/SGSIN/dashboard')
    expect(url).toContain('window=30d')
  })

  it('returns parsed DashboardResponse', async () => {
    const payload = {
      entity: { type: 'port', id: 'SGSIN', name: 'Singapore' },
      window: '30d',
      charts: { risk_trend: [] },
      stats: { risk_latest: 0.72 },
      disruptions: [],
    }
    mockFetch.mockResolvedValueOnce(makeResponse(payload))
    const result = await fetchEntityDashboard('port', 'SGSIN', '30d')
    expect(result.entity.id).toBe('SGSIN')
    expect(result.window).toBe('30d')
    expect(result.charts).toBeDefined()
  })

  it('uses 30d as default window', async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse({
        entity: { type: 'port', id: 'SGSIN', name: 'Singapore' },
        window: '30d',
        charts: {},
        stats: {},
        disruptions: [],
      }),
    )
    await fetchEntityDashboard('port', 'SGSIN')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('window=30d')
  })

  it('supports chokepoint entity type', async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse({
        entity: { type: 'chokepoint', id: 'SUEZ', name: 'Suez Canal' },
        window: '7d',
        charts: {},
        stats: {},
        disruptions: [],
      }),
    )
    await fetchEntityDashboard('chokepoint', 'SUEZ', '7d')
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('/api/v1/entities/chokepoint/SUEZ/dashboard')
    expect(url).toContain('window=7d')
  })
})

// ─── 8.2 — WindowPicker ─────────────────────────────────────────────────────

import { WindowPicker } from '../components/ui/WindowPicker'

describe('WindowPicker', () => {
  it('renders all three options', () => {
    render(<WindowPicker value="30d" onChange={() => {}} />)
    expect(screen.getByText('7d')).toBeDefined()
    expect(screen.getByText('30d')).toBeDefined()
    expect(screen.getByText('90d')).toBeDefined()
  })

  it('calls onChange with selected window', () => {
    const handler = vi.fn()
    render(<WindowPicker value="30d" onChange={handler} />)
    fireEvent.click(screen.getByText('7d'))
    expect(handler).toHaveBeenCalledWith('7d')
  })

  it('calls onChange with 90d when 90d is clicked', () => {
    const handler = vi.fn()
    render(<WindowPicker value="30d" onChange={handler} />)
    fireEvent.click(screen.getByText('90d'))
    expect(handler).toHaveBeenCalledWith('90d')
  })

  it('selected option has bg-white class', () => {
    render(<WindowPicker value="30d" onChange={() => {}} />)
    const button = screen.getByText('30d')
    expect(button.className).toContain('bg-white')
  })

  it('unselected options do not have bg-white class', () => {
    render(<WindowPicker value="30d" onChange={() => {}} />)
    const button7d = screen.getByText('7d')
    expect(button7d.className).not.toContain('bg-white')
  })
})

// ─── 8.3 — AnomalyCard ───────────────────────────────────────────────────────

import { AnomalyCard } from '../components/charts/AnomalyCard'

describe('AnomalyCard', () => {
  const series = [
    { time: '2026-05-01T00:00:00Z', value: 60 },
    { time: '2026-05-02T00:00:00Z', value: 46 },
  ]

  it('renders z-score, p-value and anomaly badge', () => {
    const stats = {
      metric: 'transit_calls',
      latest: 46.4,
      mean: 60.7,
      std: 8.5,
      z_score: -1.67,
      p_value: 0.095,
      anomaly_level: 'elevated' as const,
      baseline_n: 88,
    }
    render(<AnomalyCard series={series} stats={stats} />)
    expect(screen.getByText('-1.67')).toBeDefined()
    expect(screen.getByText('0.095')).toBeDefined()
    expect(screen.getByText('Elevated')).toBeDefined()
  })

  it('shows insufficient-data state when stats are null', () => {
    render(<AnomalyCard series={series} stats={null} />)
    expect(screen.getByText(/not enough history/i)).toBeDefined()
  })

  it('shows insufficient-data state when z_score missing', () => {
    render(<AnomalyCard series={series} stats={{ metric: 'x', baseline_n: 3 }} />)
    expect(screen.getByText(/not enough history/i)).toBeDefined()
  })
})

// ─── 8.4 — ChatbotWidget entity_context + AskAIButton ────────────────────────

import { openChatWithPrompt } from '../components/ChatbotWidget'
import { AskAIButton } from '../components/ui/AskAIButton'

// 8.4a — openChatWithPrompt dispatches the correct CustomEvent
describe('openChatWithPrompt', () => {
  it('dispatches supplytracker:open-chat event with prompt and context', () => {
    const events: CustomEvent[] = []
    const handler = (e: Event) => events.push(e as CustomEvent)
    window.addEventListener('supplytracker:open-chat', handler)

    openChatWithPrompt('Why is risk elevated?', [
      { entity_type: 'port', entity_id: 'SGSIN' },
    ])

    window.removeEventListener('supplytracker:open-chat', handler)

    expect(events).toHaveLength(1)
    expect(events[0].detail.prompt).toBe('Why is risk elevated?')
    expect(events[0].detail.entityContext).toEqual([
      { entity_type: 'port', entity_id: 'SGSIN' },
    ])
  })

  it('dispatches event with multiple entity context items', () => {
    const events: CustomEvent[] = []
    const handler = (e: Event) => events.push(e as CustomEvent)
    window.addEventListener('supplytracker:open-chat', handler)

    openChatWithPrompt('Compare these entities', [
      { entity_type: 'port', entity_id: 'SGSIN' },
      { entity_type: 'chokepoint', entity_id: 'SUEZ' },
    ])

    window.removeEventListener('supplytracker:open-chat', handler)

    expect(events).toHaveLength(1)
    expect(events[0].detail.entityContext).toHaveLength(2)
  })

  it('dispatches event with empty context array', () => {
    const events: CustomEvent[] = []
    const handler = (e: Event) => events.push(e as CustomEvent)
    window.addEventListener('supplytracker:open-chat', handler)

    openChatWithPrompt('General question', [])

    window.removeEventListener('supplytracker:open-chat', handler)

    expect(events).toHaveLength(1)
    expect(events[0].detail.entityContext).toEqual([])
  })
})

// 8.4b — AskAIButton builds the right prompt and calls onAsk
describe('AskAIButton', () => {
  it('calls onAsk with contextual prompt when clicked', () => {
    const handler = vi.fn()
    render(
      <AskAIButton
        entity={{ entity_type: 'port', entity_id: 'SGSIN', entity_name: 'Singapore' }}
        chart="dwell hours"
        window="30d"
        onAsk={handler}
      />,
    )
    fireEvent.click(screen.getByText('Ask AI'))
    expect(handler).toHaveBeenCalledWith(
      "Why has Singapore's dwell hours moved over the last 30d?",
      [{ entity_type: 'port', entity_id: 'SGSIN' }],
    )
  })

  it('uses entity_id as name when entity_name is omitted', () => {
    const handler = vi.fn()
    render(
      <AskAIButton
        entity={{ entity_type: 'port', entity_id: 'SGSIN' }}
        chart="vessel count"
        window="7d"
        onAsk={handler}
      />,
    )
    fireEvent.click(screen.getByText('Ask AI'))
    expect(handler).toHaveBeenCalledWith(
      "Why has SGSIN's vessel count moved over the last 7d?",
      [{ entity_type: 'port', entity_id: 'SGSIN' }],
    )
  })

  it('renders an "Ask AI" button', () => {
    render(
      <AskAIButton
        entity={{ entity_type: 'port', entity_id: 'SGSIN', entity_name: 'Singapore' }}
        chart="dwell hours"
        window="30d"
      />,
    )
    expect(screen.getByText('Ask AI')).toBeDefined()
  })

  it('does not throw when onAsk is not provided', () => {
    render(
      <AskAIButton
        entity={{ entity_type: 'port', entity_id: 'SGSIN', entity_name: 'Singapore' }}
        chart="dwell hours"
        window="30d"
      />,
    )
    // Clicking should not throw even without onAsk
    expect(() => fireEvent.click(screen.getByText('Ask AI'))).not.toThrow()
  })
})
