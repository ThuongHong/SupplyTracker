import React, { useEffect, useMemo, useState } from 'react'
import { DataState } from '../components/ui/DataState'
import { SeverityBadge, normalizeSeverity } from '../components/ui/Badge'
import { StatusDot } from '../components/ui/StatusDot'
import { IconSearch } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchChokepoints } from '../api/chokepoints'
import type { ChokepointSummary } from '../api/types'

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'elevated', label: 'Elevated' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'low', label: 'Low' },
] as const

type SeverityFilter = (typeof SEVERITY_OPTIONS)[number]['value']

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : value.toFixed(2)
}

function formatDate(value: string | null | undefined) {
  if (!value) return '-'
  return value.slice(0, 10)
}

function transitValue(cp: ChokepointSummary) {
  return cp.transit_time_hours ?? cp.transit_count ?? null
}

function deltaValue(cp: ChokepointSummary) {
  if (cp.transit_delta_pct != null) return cp.transit_delta_pct
  const risk = cp.risk_score == null ? 50 : cp.risk_score <= 1 ? cp.risk_score * 100 : cp.risk_score
  return (risk - 50) / 5
}

export default function ChokepointsView() {
  const [chokepoints, setChokepoints] = useState<ChokepointSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')

  useEffect(() => {
    fetchChokepoints({ limit: 200 })
      .then((res) => setChokepoints(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const sorted = useMemo(() => {
    const query = search.trim().toLowerCase()
    return chokepoints
      .filter((cp) => {
        if (severityFilter !== 'all' && normalizeSeverity(cp.severity) !== severityFilter) return false
        if (!query) return true
        return `${cp.name} ${cp.region ?? ''}`.toLowerCase().includes(query)
      })
      .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
  }, [chokepoints, search, severityFilter])

  return (
    <div className="space-y-6">
      <div className="section__head">
        <div>
          <p className="label-cap">Global arteries</p>
          <h1 className="text-5xl">Chokepoints - global arteries</h1>
        </div>
        <p className="mono text-sm text-[color:var(--ink-3)]">{sorted.length} / {chokepoints.length} shown</p>
      </div>

      <div className="flex flex-col gap-3 border border-[color:var(--rule-thin)] bg-[color:var(--card)] p-3 md:flex-row md:items-center md:justify-between">
        <label className="relative min-w-0 flex-1">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--ink-4)]" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name or region"
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
        <DataState status="empty" emptyMessage="No chokepoints match your search" />
      ) : (
        <div className="overflow-x-auto border border-[color:var(--rule-thin)] bg-[color:var(--card)]">
          <table className="dtable">
            <thead>
              <tr>
                <th>Chokepoint / region</th>
                <th>Severity</th>
                <th>Risk score</th>
                <th>Status</th>
                <th>Transit time</th>
                <th>Delta</th>
                <th>Last updated</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((cp) => {
                const transit = transitValue(cp)
                const delta = deltaValue(cp)
                return (
                  <tr key={cp.id} onClick={() => navigate(`/chokepoints/${encodeURIComponent(cp.id)}`)}>
                    <td>
                      <p className="font-semibold text-[color:var(--ink)]">{cp.name}</p>
                      <p className="mt-1 text-xs text-[color:var(--ink-3)]">{cp.region ?? 'Global artery'}</p>
                    </td>
                    <td><SeverityBadge severity={cp.severity} /></td>
                    <td className="mono">{formatScore(cp.risk_score)}</td>
                    <td>
                      <span className="inline-flex items-center gap-2">
                        <StatusDot severity={cp.severity} />
                        <span className="text-sm text-[color:var(--ink-3)]">{normalizeSeverity(cp.severity)}</span>
                      </span>
                    </td>
                    <td className="mono">{transit != null ? `${transit.toFixed(1)} h` : '-'}</td>
                    <td
                      className="mono"
                      style={{ color: delta > 0 ? 'var(--negative)' : 'var(--positive)' }}
                    >
                      {delta >= 0 ? '+' : ''}{delta.toFixed(1)}%
                    </td>
                    <td className="mono text-xs text-[color:var(--ink-3)]">{formatDate(cp.updated_at)}</td>
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
