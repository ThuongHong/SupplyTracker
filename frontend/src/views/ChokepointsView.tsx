import React, { useCallback, useEffect, useState } from 'react'
import { DataState } from '../components/ui/DataState'
import { SeverityBadge } from '../components/ui/Badge'
import { IconSearch } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchChokepoints } from '../api/chokepoints'
import { getSyncToken, syncChokepoint, untrackChokepoint } from '../api/sync'
import type { ChokepointSummary } from '../api/types'

type Tab = 'tracked' | 'browse'
const PAGE_SIZE = 50

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : value.toFixed(2)
}

export default function ChokepointsView() {
  const [tab, setTab] = useState<Tab>('tracked')
  const [chokepoints, setChokepoints] = useState<ChokepointSummary[]>([])
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
    fetchChokepoints({
      limit: PAGE_SIZE,
      offset,
      q: search.trim() || undefined,
      tracked: tab === 'tracked' ? true : undefined,
    })
      .then((res) => {
        setChokepoints(res.items)
        setTotal(res.total)
        setHasMore(res.has_more)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [tab, offset, search])

  useEffect(() => load(), [load])

  const changeTab = (next: Tab) => {
    setTab(next)
    setOffset(0)
  }
  const onSearch = (value: string) => {
    setSearch(value)
    setOffset(0)
  }

  const handleTrack = useCallback(
    async (event: React.MouseEvent, cp: ChokepointSummary) => {
      event.stopPropagation()
      if (busyId) return
      setBusyId(cp.chokepointid)
      setNotice(null)
      try {
        if (cp.is_tracked) {
          await untrackChokepoint(cp.chokepointid)
          setNotice(`Untracked ${cp.name}`)
        } else {
          const res = await syncChokepoint(cp.chokepointid)
          setNotice(`Synced ${cp.name} — ${res.rows} rows`)
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
          <p className="label-cap">Global arteries</p>
          <h1 className="text-5xl">Chokepoints - global arteries</h1>
        </div>
        <p className="mono text-sm text-[color:var(--ink-3)]">{total} total</p>
      </div>

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
            placeholder="Search name"
            className="ui w-full border border-[color:var(--rule-thin)] bg-[color:var(--paper)] py-2 pl-9 pr-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-4)] focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
          />
        </label>
        {notice && <p className="mono text-xs text-[color:var(--ink-3)]">{notice}</p>}
      </div>

      {loading ? (
        <DataState status="loading" />
      ) : error ? (
        <DataState status="error" error={error} />
      ) : chokepoints.length === 0 ? (
        <DataState
          status="empty"
          emptyMessage={tab === 'tracked' ? 'No tracked chokepoints yet — switch to Browse all and Sync one' : 'No chokepoints match your search'}
        />
      ) : (
        <>
          <div className="overflow-x-auto border border-[color:var(--rule-thin)] bg-[color:var(--card)]">
            <table className="dtable">
              <thead>
                <tr>
                  <th>Chokepoint</th>
                  <th>Severity</th>
                  <th>Risk score</th>
                  {canTrack && <th>Track</th>}
                </tr>
              </thead>
              <tbody>
                {chokepoints.map((cp) => (
                  <tr
                    key={cp.chokepointid}
                    onClick={() => navigate(`/chokepoints/${encodeURIComponent(cp.chokepointid)}`)}
                    className={cp.is_tracked ? 'bg-[color:var(--paper)]' : undefined}
                  >
                    <td>
                      <p className="font-semibold text-[color:var(--ink)]">{cp.name}</p>
                      <p className="mt-1 text-xs text-[color:var(--ink-3)]">{cp.region ?? 'Global artery'}</p>
                    </td>
                    <td><SeverityBadge severity={cp.severity} /></td>
                    <td className="mono">{formatScore(cp.risk_score)}</td>
                    {canTrack && (
                      <td>
                        <button
                          type="button"
                          disabled={busyId === cp.chokepointid}
                          onClick={(e) => handleTrack(e, cp)}
                          className="ui border border-[color:var(--rule-thin)] bg-[color:var(--paper)] px-3 py-1.5 text-xs font-semibold text-[color:var(--ink-2)] hover:bg-[color:var(--card-2)] disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
                        >
                          {busyId === cp.chokepointid ? '…' : cp.is_tracked ? 'Untrack' : 'Sync'}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

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
              {offset + 1}–{offset + chokepoints.length} of {total}
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
