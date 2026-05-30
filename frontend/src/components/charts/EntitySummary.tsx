import React, { useEffect, useRef, useState } from 'react'
import { Card } from '../ui/Card'
import { DataState } from '../ui/DataState'
import { fetchEntitySummary } from '../../api/dashboard'
import { formatMetric } from '../../lib/format'
import type { EntitySummaryResponse } from '../../api/types'

interface Props {
  entityType: 'port' | 'chokepoint'
  entityId: string
  window: '7d' | '30d' | '90d'
  reloadKey?: number
}

/** AI Summary tab: per-entity LLM narrative grounded in z-score anomaly stats. */
export function EntitySummary({ entityType, entityId, window, reloadKey }: Props) {
  const [data, setData] = useState<EntitySummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Track reloadKey so we only force LLM regeneration on a sync (key bump),
  // not on mount, window changes, or entity navigation.
  const prevReloadKey = useRef<number>(reloadKey ?? 0)

  useEffect(() => {
    let cancelled = false
    const force = (reloadKey ?? 0) > prevReloadKey.current
    prevReloadKey.current = reloadKey ?? 0
    setLoading(true)
    setError(null)
    fetchEntitySummary(entityType, entityId, window, force)
      .then((d) => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch((e: Error) => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [entityType, entityId, window, reloadKey])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!data) return <DataState status="empty" emptyMessage="No summary available" />

  const s = data.stats
  const metrics = data.metrics && data.metrics.length > 0 ? data.metrics : [s]

  const sections = [
    { label: 'What happened', body: data.what_happened, accent: 'text-indigo-600 dark:text-indigo-400' },
    { label: 'So what', body: data.so_what, accent: 'text-amber-600 dark:text-amber-400' },
    { label: 'To do', body: data.to_do, accent: 'text-emerald-600 dark:text-emerald-400' },
  ]

  return (
    <div className="space-y-4">
      <Card title="AI Summary">
        <div className="space-y-4">
          {sections.map((sec) => (
            <div key={sec.label}>
              <p className={`text-xs font-semibold uppercase tracking-wide ${sec.accent}`}>
                {sec.label}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                {sec.body || '—'}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 mono text-xs text-gray-400">
          headline metric: {formatMetric(s.metric)} (most anomalous) over {data.window}
        </p>
      </Card>
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
            <tr>
              <th className="text-left font-medium px-3 py-1.5">Metric</th>
              <th className="text-right font-medium px-3 py-1.5">Latest</th>
              <th className="text-right font-medium px-3 py-1.5">z-score</th>
              <th className="text-right font-medium px-3 py-1.5">Anomaly</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr
                key={m.metric ?? Math.random()}
                className="border-t border-gray-100 dark:border-gray-700"
              >
                <td className="px-3 py-1.5 text-gray-900 dark:text-gray-100">
                  {formatMetric(m.metric)}
                </td>
                <td className="px-3 py-1.5 text-right mono text-gray-700 dark:text-gray-300">
                  {m.latest != null ? m.latest.toFixed(1) : '—'}
                </td>
                <td className="px-3 py-1.5 text-right mono text-gray-700 dark:text-gray-300">
                  {m.z_score != null ? m.z_score.toFixed(2) : '—'}
                </td>
                <td className="px-3 py-1.5 text-right">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase ${LEVEL_CLS[m.anomaly_level ?? 'low'] ?? LEVEL_CLS.low}`}>
                    {m.anomaly_level ?? '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const LEVEL_CLS: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  elevated: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  high: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
}
