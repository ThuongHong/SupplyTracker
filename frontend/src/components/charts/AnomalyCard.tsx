import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'
import type { AnomalyStats } from '../../api/types'

interface Props {
  series: Array<{ time: string; value: number }>
  stats?: AnomalyStats | null
}

const LEVEL_STYLE: Record<string, { label: string; cls: string }> = {
  low: { label: 'Low', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
  elevated: { label: 'Elevated', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
  high: { label: 'High', cls: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
}

/**
 * Probability-hypothesis view: z-score of the latest throughput point against
 * its trailing baseline, with a ±2σ band overlaid on the series.
 */
export function AnomalyCard({ series, stats }: Props) {
  if (!stats || stats.z_score == null || stats.mean == null || stats.std == null) {
    return (
      <DataState
        status="empty"
        emptyMessage="Not enough history for a probability estimate"
      />
    )
  }

  const upper = stats.mean + 2 * stats.std
  const lower = Math.max(0, stats.mean - 2 * stats.std)
  const chartData = series.map((p) => ({
    label: p.time.slice(0, 10),
    value: p.value,
    upper,
    lower,
  }))

  const level = stats.anomaly_level ?? 'low'
  const badge = LEVEL_STYLE[level] ?? LEVEL_STYLE.low

  const cells = [
    { label: 'z-score', value: stats.z_score.toFixed(2) },
    { label: 'p-value', value: stats.p_value != null ? stats.p_value.toFixed(3) : '—' },
    { label: 'Latest', value: stats.latest != null ? stats.latest.toFixed(1) : '—' },
    { label: 'Mean ± σ', value: `${stats.mean.toFixed(1)} ± ${stats.std.toFixed(1)}` },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Anomaly likelihood
        </span>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badge.cls}`}>
          {badge.label}
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          latest vs {stats.baseline_n}-point baseline
        </span>
      </div>

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

      {chartData.length > 0 && (
        <AreaChart
          data={chartData}
          height={200}
          showLegend
          series={[
            { key: 'upper', name: '+2σ', color: '#f97316', fillOpacity: 0 },
            { key: 'lower', name: '−2σ', color: '#f97316', fillOpacity: 0 },
            { key: 'value', name: stats.metric ?? 'Throughput', color: '#6366f1', fillOpacity: 0.15 },
          ]}
        />
      )}
    </div>
  )
}
