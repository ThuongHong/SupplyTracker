import React, { useState, useEffect, useCallback } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { Sparkline } from '../components/ui/Sparkline'
import { AreaChart } from '../components/ui/AreaChart'
import { InsightRow } from '../components/ui/InsightRow'
import { IconX } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPorts } from '../api/ports'
import { fetchChokepoints, fetchChokepointBreakdown } from '../api/chokepoints'
import { fetchIndices, fetchIndexTimeseries } from '../api/indices'
import { fetchInsights } from '../api/insights'
import { fetchRiskScores } from '../api/risk'
import { tracked } from '../data/tracked'
import type { PortSummary, ChokepointSummary, IndexSummary, InsightItem, Severity } from '../api/types'

// ─── Severity ordering ───────────────────────────────────────────────────────

const SEV_ORDER: Record<Severity, number> = {
  critical: 4,
  high: 3,
  moderate: 2,
  low: 1,
}

function compareSeverity(a: Severity, b: Severity, aTracked: boolean, bTracked: boolean): number {
  // Higher severity first; break ties by tracked status (tracked = higher)
  const sevDiff = SEV_ORDER[b] - SEV_ORDER[a]
  if (sevDiff !== 0) return sevDiff
  return (bTracked ? 1 : 0) - (aTracked ? 1 : 0)
}

// ─── Freshness Banner ────────────────────────────────────────────────────────

function FreshnessBanner({ updatedAt }: { updatedAt: string | null }) {
  if (!updatedAt) return null
  const ageHours = (Date.now() - new Date(updatedAt).getTime()) / 3_600_000
  if (ageHours < 24) return null
  return (
    <div className="rounded-lg bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
      Data may be stale — last updated{' '}
      <strong>{Math.floor(ageHours)} hours ago</strong>. Refresh or check backend status.
    </div>
  )
}

// ─── KPI Strip ───────────────────────────────────────────────────────────────

function KpiStrip({
  critical,
  high,
  moderate,
  low,
}: {
  critical: number
  high: number
  moderate: number
  low: number
}) {
  const kpis = [
    { label: 'Critical', value: critical, variant: 'critical' as Severity },
    { label: 'High', value: high, variant: 'high' as Severity },
    { label: 'Moderate', value: moderate, variant: 'moderate' as Severity },
    { label: 'Low', value: low, variant: 'low' as Severity },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {kpis.map(({ label, value, variant }) => (
        <Card key={label} padding="sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</span>
            <SeverityBadge severity={variant} />
          </div>
          <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">entities</p>
        </Card>
      ))}
    </div>
  )
}

// ─── Index Modal ─────────────────────────────────────────────────────────────

function IndexModal({
  indexName,
  onClose,
}: {
  indexName: string
  onClose: () => void
}) {
  const [points, setPoints] = useState<{ label: string; value: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchIndexTimeseries(indexName)
      .then((ts) => {
        if (cancelled) return
        setPoints(
          ts.points.map((p) => ({
            label: p.time.slice(0, 10),
            value: p.value,
          })),
        )
        setLoading(false)
      })
      .catch((e: Error) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [indexName])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${indexName} timeseries`}
    >
      <div
        className="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {indexName} — Full Timeseries
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Close"
          >
            <IconX className="w-5 h-5" />
          </button>
        </div>
        {loading && <DataState status="loading" />}
        {error && <DataState status="error" error={error} />}
        {!loading && !error && points.length === 0 && (
          <DataState status="empty" emptyMessage="No timeseries data" />
        )}
        {!loading && !error && points.length > 0 && (
          <AreaChart data={points} height={250} />
        )}
      </div>
    </div>
  )
}

// ─── Indices Strip ────────────────────────────────────────────────────────────

function IndicesStrip({ indices }: { indices: IndexSummary[] }) {
  const [modalIndex, setModalIndex] = useState<string | null>(null)

  return (
    <>
      <div className="flex gap-4 overflow-x-auto pb-1">
        {indices.map((idx) => {
          const spark: number[] = [] // no sparkline data from summary endpoint
          const d7 = idx.change_pct_7d
          const d30 = idx.change_pct_30d
          return (
            <button
              key={idx.index_name}
              onClick={() => setModalIndex(idx.index_name)}
              className="flex-shrink-0 flex flex-col gap-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 hover:border-indigo-300 dark:hover:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors text-left min-w-[140px]"
              aria-label={`View ${idx.index_name} timeseries`}
            >
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 truncate">
                {idx.index_name}
              </span>
              <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
                {idx.latest_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                {idx.unit ? <span className="text-xs font-normal ml-1">{idx.unit}</span> : null}
              </span>
              <div className="flex gap-2 flex-wrap">
                <Badge variant={d7 >= 0 ? 'info' : 'high'}>
                  7d {d7 >= 0 ? '+' : ''}{d7.toFixed(1)}%
                </Badge>
                <Badge variant={d30 >= 0 ? 'info' : 'high'}>
                  30d {d30 >= 0 ? '+' : ''}{d30.toFixed(1)}%
                </Badge>
              </div>
            </button>
          )
        })}
      </div>
      {modalIndex && (
        <IndexModal indexName={modalIndex} onClose={() => setModalIndex(null)} />
      )}
    </>
  )
}

// ─── Chokepoint 50-day strip chart ──────────────────────────────────────────

function ChokepointStripChart({ id }: { id: string }) {
  const [data, setData] = useState<{ label: string; value: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchChokepointBreakdown(id)
      .then((bd) => {
        if (cancelled) return
        const slice = bd.days.slice(-50)
        setData(slice.map((d) => ({ label: d.date.slice(5), value: d.value })))
        setLoading(false)
      })
      .catch((e: Error) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!data.length) return <DataState status="empty" emptyMessage="No breakdown data" />
  return <AreaChart data={data} height={160} />
}

// ─── Decision Brief ──────────────────────────────────────────────────────────

function DecisionBrief({ insights }: { insights: InsightItem[] }) {
  const critical = insights.filter((i) => i.attention_level === 'critical').slice(0, 3)
  const display = critical.length ? critical : insights.slice(0, 3)

  if (!display.length) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 italic py-4">
        No high-priority insights at this time.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Top {display.length} attention item{display.length !== 1 ? 's' : ''}
      </p>
      {display.map((item) => (
        <div
          key={item.id}
          className="rounded-lg bg-gray-50 dark:bg-gray-700/50 px-4 py-3 border-l-4"
          style={{
            borderLeftColor:
              item.attention_level === 'critical'
                ? '#ef4444'
                : item.attention_level === 'high'
                  ? '#f97316'
                  : item.attention_level === 'moderate'
                    ? '#f59e0b'
                    : '#22c55e',
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {item.title}
            </span>
            <SeverityBadge severity={item.attention_level as Severity} />
          </div>
          {item.narrative && (
            <p className="text-sm text-gray-600 dark:text-gray-300">{item.narrative}</p>
          )}
          {item.entity_name && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{item.entity_name}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Top-5 Ports ─────────────────────────────────────────────────────────────

function TopPorts({ ports }: { ports: PortSummary[] }) {
  return (
    <div className="divide-y divide-gray-100 dark:divide-gray-700">
      {ports.map((port, i) => (
        <button
          key={port.id}
          onClick={() => navigate(`/ports/${encodeURIComponent(port.id)}`)}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 focus:outline-none focus:bg-gray-50 dark:focus:bg-gray-700/50 transition-colors text-left"
        >
          <span className="w-6 text-xs font-bold text-gray-400">#{i + 1}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
              {port.name}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{port.country}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {port.risk_score !== undefined && (
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                {port.risk_score.toFixed(1)}
              </span>
            )}
            <SeverityBadge severity={port.severity} />
          </div>
        </button>
      ))}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function OverviewView() {
  const [latestUpdatedAt, setLatestUpdatedAt] = useState<string | null>(null)

  // Ports
  const [ports, setPorts] = useState<PortSummary[]>([])
  const [portsLoading, setPortsLoading] = useState(true)
  const [portsError, setPortsError] = useState<string | null>(null)

  // Chokepoints
  const [chokepoints, setChokepoints] = useState<ChokepointSummary[]>([])
  const [chokepointsLoading, setChokepointsLoading] = useState(true)

  // Selected chokepoint for strip chart
  const [selectedCp, setSelectedCp] = useState<string | null>(null)

  // Indices
  const [indices, setIndices] = useState<IndexSummary[]>([])
  const [indicesLoading, setIndicesLoading] = useState(true)

  // Insights
  const [insights, setInsights] = useState<InsightItem[]>([])
  const [insightsLoading, setInsightsLoading] = useState(true)
  const [insightsFilter, setInsightsFilter] = useState<Severity | 'all'>('all')

  // Tracked set (for tie-breaking)
  const [trackedPortIds, setTrackedPortIds] = useState<Set<string>>(
    () => new Set(tracked.ports.getAll()),
  )

  useEffect(() => tracked.ports.subscribe(() => setTrackedPortIds(new Set(tracked.ports.getAll()))), [])

  // Fetch data
  useEffect(() => {
    fetchPorts({ limit: 200 })
      .then((res) => {
        setPorts(res.items)
        if (res.items.length) setLatestUpdatedAt(res.items[0].updated_at)
        setPortsLoading(false)
      })
      .catch((e: Error) => {
        setPortsError(e.message)
        setPortsLoading(false)
      })
  }, [])

  useEffect(() => {
    fetchChokepoints({ limit: 100 })
      .then((res) => {
        setChokepoints(res.items)
        if (res.items.length) setSelectedCp(res.items[0].id)
        setChokepointsLoading(false)
      })
      .catch(() => setChokepointsLoading(false))
  }, [])

  useEffect(() => {
    fetchIndices()
      .then((res) => {
        setIndices(res.items)
        setIndicesLoading(false)
      })
      .catch(() => setIndicesLoading(false))
  }, [])

  useEffect(() => {
    fetchInsights({ limit: 20 })
      .then((res) => {
        setInsights(res.items)
        setInsightsLoading(false)
      })
      .catch(() => setInsightsLoading(false))
  }, [])

  // KPI counts from all ports + chokepoints via risk scores
  const kpiCounts = { critical: 0, high: 0, moderate: 0, low: 0 }
  for (const p of ports) {
    kpiCounts[p.severity] = (kpiCounts[p.severity] ?? 0) + 1
  }
  for (const cp of chokepoints) {
    kpiCounts[cp.severity] = (kpiCounts[cp.severity] ?? 0) + 1
  }

  // Top-5 ports sorted by severity, then tracked-status
  const top5Ports = [...ports]
    .sort((a, b) =>
      compareSeverity(a.severity, b.severity, trackedPortIds.has(a.id), trackedPortIds.has(b.id)),
    )
    .slice(0, 5)

  // Filtered insights
  const filteredInsights =
    insightsFilter === 'all'
      ? insights
      : insights.filter((i) => i.attention_level === insightsFilter)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Overview</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Global supply chain risk at a glance
        </p>
      </div>

      {/* Freshness banner */}
      <FreshnessBanner updatedAt={latestUpdatedAt} />

      {/* KPI strip */}
      {portsLoading || chokepointsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} padding="sm">
              <DataState status="loading" />
            </Card>
          ))}
        </div>
      ) : (
        <KpiStrip {...kpiCounts} />
      )}

      {/* Indices strip */}
      <Card title="Macro Indices (click for full chart)">
        {indicesLoading ? (
          <DataState status="loading" />
        ) : indices.length === 0 ? (
          <DataState status="empty" emptyMessage="No indices data" />
        ) : (
          <IndicesStrip indices={indices} />
        )}
      </Card>

      {/* Chokepoint strip chart + selector */}
      <Card
        title="Chokepoint Activity — 50-day strip"
        actions={
          chokepoints.length > 0 ? (
            <select
              value={selectedCp ?? ''}
              onChange={(e) => setSelectedCp(e.target.value)}
              className="text-xs rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {chokepoints.map((cp) => (
                <option key={cp.id} value={cp.id}>
                  {cp.name}
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        {chokepointsLoading ? (
          <DataState status="loading" />
        ) : selectedCp ? (
          <ChokepointStripChart key={selectedCp} id={selectedCp} />
        ) : (
          <DataState status="empty" emptyMessage="No chokepoints available" />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decision Brief */}
        <Card
          title="Decision Brief"
          actions={
            <span className="text-xs text-gray-400 dark:text-gray-500">Auto-generated</span>
          }
        >
          {insightsLoading ? (
            <DataState status="loading" />
          ) : (
            <DecisionBrief insights={insights} />
          )}
        </Card>

        {/* Top-5 Ports by Severity */}
        <Card title="Top 5 Ports by Severity">
          {portsLoading ? (
            <DataState status="loading" />
          ) : portsError ? (
            <DataState status="error" error={portsError} />
          ) : top5Ports.length === 0 ? (
            <DataState status="empty" emptyMessage="No port data" />
          ) : (
            <TopPorts ports={top5Ports} />
          )}
        </Card>
      </div>

      {/* Insights feed */}
      <Card
        title="Insights Feed"
        actions={
          <select
            value={insightsFilter}
            onChange={(e) => setInsightsFilter(e.target.value as Severity | 'all')}
            className="text-xs rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="moderate">Moderate</option>
            <option value="low">Low</option>
          </select>
        }
      >
        {insightsLoading ? (
          <DataState status="loading" />
        ) : filteredInsights.length === 0 ? (
          <DataState status="empty" emptyMessage="No insights match filter" />
        ) : (
          <div>
            {filteredInsights.map((item) => (
              <InsightRow key={item.id} insight={item} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
