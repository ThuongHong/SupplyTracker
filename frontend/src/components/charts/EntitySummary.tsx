import React, { useEffect, useState } from 'react'
import { Card } from '../ui/Card'
import { DataState } from '../ui/DataState'
import { fetchEntitySummary } from '../../api/dashboard'
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

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchEntitySummary(entityType, entityId, window)
      .then((d) => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch((e: Error) => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [entityType, entityId, window, reloadKey])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!data) return <DataState status="empty" emptyMessage="No summary available" />

  const s = data.stats
  const cells = [
    { label: 'Metric', value: s.metric ?? '—' },
    { label: 'z-score', value: s.z_score != null ? s.z_score.toFixed(2) : '—' },
    { label: 'p-value', value: s.p_value != null ? s.p_value.toFixed(3) : '—' },
    { label: 'Anomaly', value: s.anomaly_level ?? '—' },
  ]

  return (
    <div className="space-y-4">
      <Card title="AI Summary">
        <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          {data.narrative}
        </p>
        <p className="mt-2 mono text-xs text-gray-400">grounded on throughput over {data.window}</p>
      </Card>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cells.map((c) => (
          <div
            key={c.label}
            className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2"
          >
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{c.label}</p>
            <p className="mt-0.5 mono text-base font-semibold text-gray-900 dark:text-gray-100">
              {c.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
