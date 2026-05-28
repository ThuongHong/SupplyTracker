import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { DataState } from '../components/ui/DataState'
import { SeverityBadge, normalizeSeverity } from '../components/ui/Badge'
import { StatusDot } from '../components/ui/StatusDot'
import { IconSearch, IconStar, IconStarFilled } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPorts } from '../api/ports'
import { tracked } from '../data/tracked'
import type { PortSummary } from '../api/types'

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'elevated', label: 'Elevated' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'low', label: 'Low' },
] as const

type SeverityFilter = (typeof SEVERITY_OPTIONS)[number]['value']

function scoreValue(port: PortSummary) {
  const raw = port.congestion_score ?? port.risk_score ?? 0
  const percent = raw <= 1 ? raw * 100 : raw
  return Math.min(Math.max(percent, 0), 100)
}

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : value.toFixed(2)
}

export default function PortsView() {
  const [ports, setPorts] = useState<PortSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')
  const [trackedIds, setTrackedIds] = useState<Set<string>>(() => new Set(tracked.ports.getAll()))

  useEffect(() => tracked.ports.subscribe(() => setTrackedIds(new Set(tracked.ports.getAll()))), [])

  useEffect(() => {
    fetchPorts({ limit: 500 })
      .then((res) => setPorts(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const toggleTrack = useCallback(
    (event: React.MouseEvent, id: number) => {
      event.stopPropagation()
      const key = String(id)
      if (trackedIds.has(key)) tracked.ports.remove(key)
      else tracked.ports.add(key)
    },
    [trackedIds],
  )

  const sorted = useMemo(() => {
    const query = search.trim().toLowerCase()
    return ports
      .filter((port) => {
        if (severityFilter !== 'all' && normalizeSeverity(port.severity) !== severityFilter) return false
        if (!query) return true
        return `${port.name} ${port.country}`.toLowerCase().includes(query)
      })
      .sort((a, b) => {
        const pinned = Number(trackedIds.has(String(b.id))) - Number(trackedIds.has(String(a.id)))
        if (pinned !== 0) return pinned
        return (b.risk_score ?? 0) - (a.risk_score ?? 0)
      })
  }, [ports, search, severityFilter, trackedIds])

  return (
    <div className="space-y-6">
      <div className="section__head">
        <div>
          <p className="label-cap">Coverage desk</p>
          <h1 className="text-5xl">Ports - global terminals</h1>
        </div>
        <p className="mono text-sm text-[color:var(--ink-3)]">{sorted.length} / {ports.length} shown</p>
      </div>

      <div className="flex flex-col gap-3 border border-[color:var(--rule-thin)] bg-[color:var(--card)] p-3 md:flex-row md:items-center md:justify-between">
        <label className="relative min-w-0 flex-1">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--ink-4)]" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name or country"
            className="ui w-full border border-[color:var(--rule-thin)] bg-[color:var(--paper)] py-2 pl-9 pr-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--ink-4)] focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          {SEVERITY_OPTIONS.map((option) => {
            const active = severityFilter === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setSeverityFilter(option.value)}
                className={[
                  'ui border px-3 py-2 text-xs font-semibold',
                  active
                    ? 'border-[color:var(--ink)] bg-[color:var(--ink)] text-[color:var(--paper)]'
                    : 'border-[color:var(--rule-thin)] bg-[color:var(--card-2)] text-[color:var(--ink-2)] hover:bg-[color:var(--paper)]',
                ].join(' ')}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>

      {loading ? (
        <DataState status="loading" />
      ) : error ? (
        <DataState status="error" error={error} />
      ) : sorted.length === 0 ? (
        <DataState status="empty" emptyMessage="No ports match your search" />
      ) : (
        <div className="overflow-x-auto border border-[color:var(--rule-thin)] bg-[color:var(--card)]">
          <table className="dtable">
            <thead>
              <tr>
                <th>Port / country</th>
                <th>Severity</th>
                <th>Risk score</th>
                <th>Congestion</th>
                <th>Status</th>
                <th>Track</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((port) => {
                const trackedPort = trackedIds.has(String(port.id))
                const score = scoreValue(port)
                return (
                  <tr
                    key={port.id}
                    onClick={() => navigate(`/ports/${encodeURIComponent(port.id)}`)}
                    className={trackedPort ? 'bg-[color:var(--paper)]' : undefined}
                  >
                    <td>
                      <p className="font-semibold text-[color:var(--ink)]">{port.name}</p>
                      <p className="mt-1 text-xs text-[color:var(--ink-3)]">{port.country}</p>
                    </td>
                    <td><SeverityBadge severity={port.severity} /></td>
                    <td className="mono">{formatScore(port.risk_score)}</td>
                    <td>
                      <span className="bar-cell" aria-label={`Congestion ${score.toFixed(0)} percent`}>
                        <span style={{ width: `${score}%` }} />
                      </span>
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-2">
                        <StatusDot severity={port.severity} />
                        <span className="text-sm text-[color:var(--ink-3)]">{normalizeSeverity(port.severity)}</span>
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={(event) => toggleTrack(event, port.id)}
                        className="inline-flex h-8 w-8 items-center justify-center border border-[color:var(--rule-thin)] bg-[color:var(--paper)] text-[color:var(--ink-3)] hover:text-[color:var(--accent)] focus:outline-none focus:ring-2 focus:ring-[color:var(--accent)]"
                        aria-label={trackedPort ? `Untrack ${port.name}` : `Track ${port.name}`}
                      >
                        {trackedPort ? (
                          <IconStarFilled className="h-4 w-4 text-[color:var(--highlight)]" />
                        ) : (
                          <IconStar className="h-4 w-4" />
                        )}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
