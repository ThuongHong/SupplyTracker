import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { Card } from '../components/ui/Card'
import { SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { StatusDot } from '../components/ui/StatusDot'
import { IconSearch, IconStar, IconStarFilled } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPorts } from '../api/ports'
import { tracked } from '../data/tracked'
import type { PortSummary, Severity } from '../api/types'

const SEVERITY_OPTIONS: Array<{ value: 'all' | Severity; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'low', label: 'Low' },
]

const REGIONS = ['All'] as const

export default function PortsView() {
  const [ports, setPorts] = useState<PortSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState<'all' | Severity>('all')
  const [trackedIds, setTrackedIds] = useState<Set<string>>(() => new Set(tracked.ports.getAll()))

  // Subscribe to tracked changes
  useEffect(() => {
    return tracked.ports.subscribe(() => setTrackedIds(new Set(tracked.ports.getAll())))
  }, [])

  useEffect(() => {
    fetchPorts({ limit: 500 })
      .then((res) => {
        setPorts(res.items)
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  const toggleTrack = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation()
      if (trackedIds.has(id)) {
        tracked.ports.remove(id)
      } else {
        tracked.ports.add(id)
      }
    },
    [trackedIds],
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return ports.filter((p) => {
      if (severityFilter !== 'all' && p.severity !== severityFilter) return false
      if (q) {
        const haystack = `${p.name} ${p.country}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [ports, search, severityFilter])

  // Pinned (tracked) ports at top
  const sorted = useMemo(() => {
    const pinned = filtered.filter((p) => trackedIds.has(p.id))
    const rest = filtered.filter((p) => !trackedIds.has(p.id))
    return [...pinned, ...rest]
  }, [filtered, trackedIds])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Ports</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Monitored ports and their current risk status
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name or country…"
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as 'all' | Severity)}
          className="text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {SEVERITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <Card padding="none">
        {loading ? (
          <DataState status="loading" />
        ) : error ? (
          <DataState status="error" error={error} />
        ) : sorted.length === 0 ? (
          <DataState status="empty" emptyMessage="No ports match your search" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 w-10" />
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    Port
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    Country
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    Severity
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    Risk Score
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {sorted.map((port) => {
                  const isTracked = trackedIds.has(port.id)
                  return (
                    <tr
                      key={port.id}
                      onClick={() => navigate(`/ports/${encodeURIComponent(port.id)}`)}
                      className={[
                        'cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50',
                        isTracked ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : '',
                      ].join(' ')}
                    >
                      <td className="px-4 py-3">
                        <button
                          onClick={(e) => toggleTrack(e, port.id)}
                          className="p-0.5 rounded text-gray-400 hover:text-amber-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
                          aria-label={isTracked ? `Untrack ${port.name}` : `Track ${port.name}`}
                        >
                          {isTracked ? (
                            <IconStarFilled className="w-4 h-4 text-amber-500" />
                          ) : (
                            <IconStar className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                        {port.name}
                      </td>
                      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                        {port.country}
                      </td>
                      <td className="px-4 py-3">
                        <SeverityBadge severity={port.severity} />
                      </td>
                      <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-mono">
                        {port.risk_score !== undefined ? port.risk_score.toFixed(2) : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs">
                        {port.updated_at ? port.updated_at.slice(0, 10) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div className="px-4 py-2 text-xs text-gray-400 dark:text-gray-500 border-t border-gray-100 dark:border-gray-700">
              {sorted.length} of {ports.length} ports shown
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
