/**
 * Tests for the PortsView catalog browser:
 *  - Tracked / Browse-all tabs drive the `tracked` query param
 *  - search drives the `q` param
 *  - Sync (=track) button calls syncPort then refetches
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import type { PortSummary } from '../api/types'

const fetchPorts = vi.fn()
const syncPort = vi.fn()
const untrackPort = vi.fn()
const getSyncToken = vi.fn(() => 'test-token')

vi.mock('../api/ports', () => ({ fetchPorts: (...a: unknown[]) => fetchPorts(...a) }))
vi.mock('../api/sync', () => ({
  getSyncToken: () => getSyncToken(),
  syncPort: (...a: unknown[]) => syncPort(...a),
  untrackPort: (...a: unknown[]) => untrackPort(...a),
}))
vi.mock('../router', () => ({ navigate: vi.fn() }))

import PortsView from '../views/PortsView'

function port(overrides: Partial<PortSummary> = {}): PortSummary {
  return {
    id: 1,
    portid: 'port1188',
    locode: 'CNSHA',
    name: 'Shanghai',
    country: 'China',
    region: 'Asia',
    is_tracked: false,
    severity: 'low',
    risk_score: 0.4,
    ...overrides,
  }
}

function pageOf(items: PortSummary[]) {
  return { items, total: items.length, has_more: false, limit: 50, offset: 0 }
}

beforeEach(() => {
  fetchPorts.mockReset().mockResolvedValue(pageOf([port()]))
  syncPort.mockReset().mockResolvedValue({ rows: 273, is_tracked: true, errors: [] })
  untrackPort.mockReset().mockResolvedValue({ is_tracked: false, errors: [] })
  getSyncToken.mockReturnValue('test-token')
})

describe('PortsView', () => {
  it('loads the Tracked tab by default (tracked=true)', async () => {
    render(<PortsView />)
    await waitFor(() => expect(fetchPorts).toHaveBeenCalled())
    expect(fetchPorts.mock.calls[0][0]).toMatchObject({ tracked: true })
  })

  it('switching to Browse all drops the tracked filter', async () => {
    render(<PortsView />)
    await screen.findByText('Shanghai')
    fireEvent.click(screen.getByText('Browse all'))
    await waitFor(() => {
      const last = fetchPorts.mock.calls.at(-1)![0]
      expect(last.tracked).toBeUndefined()
    })
  })

  it('search drives the q param', async () => {
    render(<PortsView />)
    await screen.findByText('Shanghai')
    fireEvent.change(screen.getByPlaceholderText('Search name or country'), {
      target: { value: 'rotter' },
    })
    await waitFor(() => {
      const last = fetchPorts.mock.calls.at(-1)![0]
      expect(last.q).toBe('rotter')
    })
  })

  it('Sync button calls syncPort for an untracked port', async () => {
    render(<PortsView />)
    await screen.findByText('Shanghai')
    fireEvent.click(screen.getByRole('button', { name: 'Sync' }))
    await waitFor(() => expect(syncPort).toHaveBeenCalledWith('port1188'))
  })

  it('hides Track column when no sync token', async () => {
    getSyncToken.mockReturnValue(null as unknown as string)
    render(<PortsView />)
    await screen.findByText('Shanghai')
    expect(screen.queryByRole('button', { name: 'Sync' })).toBeNull()
  })
})
