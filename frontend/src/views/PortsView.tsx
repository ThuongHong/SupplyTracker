import React, { useCallback, useEffect, useState } from 'react'
import { DataState } from '../components/ui/DataState'
import { SeverityBadge } from '../components/ui/Badge'
import { IconSearch } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPorts } from '../api/ports'
import { getSyncToken, syncPort, untrackPort } from '../api/sync'
import type { PortSummary } from '../api/types'

type Tab = 'tracked' | 'browse'
const PAGE_SIZE = 50

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : value.toFixed(2)
}

export default function PortsView() {
  const [tab, setTab] = useState<Tab>('tracked')
  const [ports, setPorts] = useState<PortSummary[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const canTrack = getSyncToken() !== null

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchPorts({
      limit: PAGE_SIZE,
      offset,
      q: search.trim() || undefined,
      tracked: tab === 'tracked' ? true : undefined,
    })
      .then((res) => {
        setPorts(res.items)
        setTotal(res.total)
        setHasMore(res.has_more)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [tab, offset, search])

  useEffect(() => load(), [load])

  // Reset to first page when tab or search changes.
  const changeTab = (next: Tab) => {
    setTab(next)
    setOffset(0)
  }
  const onSearch = (value: string) => {
    setSearch(value)
    setOffset(0)
  }

  const handleTrack = useCallback(
    async (event: React.MouseEvent, port: PortSummary) => {
      event.stopPropagation()
      if (busyId) return
      setBusyId(port.portid)
      setNotice(null)
      try {
        if (port.is_tracked) {
          await untrackPort(port.portid)
          setNotice(`Untracked ${port.name}`)
        } else {
          const res = await syncPort(port.portid)
          setNotice(`Synced ${port.name} — ${res.rows} rows`)
        }
        load()
      } catch (e: unknown) {
        setNotice(e instanceof Error ? e.message : 'Action failed')
      } finally {
        setBusyId(null)
      }
    },
    [busyId, load],
  )

  return (
    <div className="space-y-6">
      <div className="section__head">
        <div>
          <p className="label-cap">Coverage desk</p>
          <h1 className="text-5xl">Ports - global terminals</h1>
        </div>
        <p className="mono text-sm text-[color:var(--ink-3)]">{total} total</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(['tracked', 'browse'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => changeTab(t)}
            className={[
              'ui border px-4 py-2 text-sm font-semibold',
              tab === t
                ? 'border-[color:var(--ink)] bg-[color:var(--ink)] text-[color:var(--paper)]'
                : 'border-[color:var(--rule-thin)] bg-[color:var(--card-2)] text-[color:var(--ink-2)] hover:bg-[color:var(--paper)]',
            ].join(' ')}
          >
            {t === 'tracked' ? 'Tracked' : 'Browse all'}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 border border-[color:var(--rule-thin)] bg-[color:var(--card)] p-3 md:flex-row md:items-center md:justify-between">
        <label className="relative min-w-0 flex-1">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--ink-4)]" />
          <input
            type="search"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search name or country"
            className="ui w-full border border-[color:var(--rule-thin)] bg-[color:var(--paper)] py-2 pl-9 pr-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-4)] focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
          />
        </label>
        {notice && <p className="mono text-xs text-[color:var(--ink-3)]">{notice}</p>}
      </div>

      {loading ? (
        <DataState status="loading" />
      ) : error ? (
        <DataState status="error" error={error} />
      ) : ports.length === 0 ? (
        <DataState
          status="empty"
          emptyMessage={tab === 'tracked' ? 'No tracked ports yet — switch to Browse all and Sync one' : 'No ports match your search'}
        />
      ) : (
        <>
          <div className="overflow-x-auto border border-[color:var(--rule-thin)] bg-[color:var(--card)]">
            <table className="dtable">
              <thead>
                <tr>
                  <th>Port / country</th>
                  <th>Severity</th>
                  <th>Risk score</th>
                  {canTrack && <th>Track</th>}
                </tr>
              </thead>
              <tbody>
                {ports.map((port) => (
                  <tr
                    key={port.portid}
                    onClick={() => navigate(`/ports/${encodeURIComponent(port.portid)}`)}
                    className={port.is_tracked ? 'bg-[color:var(--paper)]' : undefined}
                  >
                    <td>
                      <p className="font-semibold text-[color:var(--ink)]">{port.name}</p>
                      <p className="mt-1 text-xs text-[color:var(--ink-3)]">{port.country}</p>
                    </td>
                    <td><SeverityBadge severity={port.severity} /></td>
                    <td className="mono">{formatScore(port.risk_score)}</td>
                    {canTrack && (
                      <td>
                        <button
                          type="button"
                          disabled={busyId === port.portid}
                          onClick={(e) => handleTrack(e, port)}
                          className="ui border border-[color:var(--rule-thin)] bg-[color:var(--paper)] px-3 py-1.5 text-xs font-semibold text-[color:var(--ink-2)] hover:bg-[color:var(--card-2)] disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
                        >
                          {busyId === port.portid ? '…' : port.is_tracked ? 'Untrack' : 'Sync'}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="ui border border-[color:var(--rule-thin)] px-3 py-2 text-xs font-semibold disabled:opacity-40"
            >
              ← Prev
            </button>
            <span className="mono text-xs text-[color:var(--ink-3)]">
              {offset + 1}–{offset + ports.length} of {total}
            </span>
            <button
              type="button"
              disabled={!hasMore}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="ui border border-[color:var(--rule-thin)] px-3 py-2 text-xs font-semibold disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
