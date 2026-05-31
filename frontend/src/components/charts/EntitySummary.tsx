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
    { label: 'What happened', body: data.what_happened, accent: 'text-[color:var(--accent)]' },
    { label: 'So what', body: data.so_what, accent: 'text-[color:var(--caution)]' },
    { label: 'To do', body: data.to_do, accent: 'text-[color:var(--positive)]' },
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
              <p className="mt-1 text-sm leading-relaxed text-[color:var(--ink-2)]">
                {sec.body || '—'}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 mono text-xs text-[color:var(--ink-4)]">
          headline metric: {formatMetric(s.metric)} (most anomalous) over {data.window}
        </p>
      </Card>
      <div className="border border-[color:var(--rule-thin)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[color:var(--paper-2)] text-[color:var(--ink-3)]">
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
                className="border-t border-[color:var(--rule-hair)]"
              >
                <td className="px-3 py-1.5 text-[color:var(--ink)]">
                  {formatMetric(m.metric)}
                </td>
                <td className="px-3 py-1.5 text-right mono text-[color:var(--ink-2)]">
                  {m.latest != null ? m.latest.toFixed(1) : '—'}
                </td>
                <td className="px-3 py-1.5 text-right mono text-[color:var(--ink-2)]">
                  {m.z_score != null ? m.z_score.toFixed(2) : '—'}
                </td>
                <td className="px-3 py-1.5 text-right">
                  <span className={LEVEL_CLS[m.anomaly_level ?? 'low'] ?? LEVEL_CLS.low}>
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
  low: 'pill pill--low',
  elevated: 'pill pill--elevated',
  high: 'pill pill--high',
}
