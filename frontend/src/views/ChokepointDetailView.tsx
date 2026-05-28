import React, { useState, useEffect, useMemo } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { AreaChart } from '../components/ui/AreaChart'
import { MiniMap } from '../components/ui/MiniMap'
import { InsightRow } from '../components/ui/InsightRow'
import { IconChevronLeft, IconStar, IconStarFilled } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchChokepoint, fetchChokepointBreakdown, fetchChokepointMetrics } from '../api/chokepoints'
import { fetchRiskForecast } from '../api/risk'
import { tracked } from '../data/tracked'
import { EventLog } from '../components/EventLog'
import { SyncButton } from '../components/SyncButton'
import type { ChokepointDetail, RiskForecast, BreakdownDay, MetricPoint } from '../api/types'

interface ChokepointDetailViewProps {
  id: string
}

// ─── KPI Strip ───────────────────────────────────────────────────────────────

function KpiStrip({ cp, latestDay }: { cp: ChokepointDetail; latestDay?: BreakdownDay }) {
  const score = cp.risk_snapshot?.composite_score ?? cp.risk_score
  const trend = cp.risk_snapshot?.trend

  const items = [
    { label: 'Risk Score', value: score != null ? score.toFixed(2) : '—' },
    { label: 'Trend', value: trend ?? '—' },
    { label: 'Severity', value: cp.severity ?? '—' },
    {
      label: 'Latest Transit',
      value: latestDay ? latestDay.total.toFixed(0) : '—',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.map(({ label, value }) => (
        <div
          key={label}
          className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3"
        >
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
          <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
        </div>
      ))}
    </div>
  )
}

// ─── Breakdown Chart ─────────────────────────────────────────────────────────

function BreakdownChart({ id }: { id: string }) {
  const [days, setDays] = useState<BreakdownDay[]>([])
  const [latestDay, setLatestDay] = useState<BreakdownDay | undefined>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchChokepointBreakdown(id)
      .then((bd) => {
        if (cancelled) return
        const slice = bd.days.slice(-50)
        setDays(slice)
        setLatestDay(slice[slice.length - 1])
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
  if (!days.length) return <DataState status="empty" emptyMessage="No breakdown data" />

  const chartData = days.map((d) => ({
    label: d.date.slice(5),
    value: d.total,
  }))

  return <AreaChart data={chartData} height={180} />
}

// ─── Metric Drill-down ────────────────────────────────────────────────────────

function MetricDrilldown({ cpId }: { cpId: number }) {
  const [allMetrics, setAllMetrics] = useState<Record<string, MetricPoint[]>>({})
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchChokepointMetrics(cpId)
      .then((res) => {
        if (cancelled) return
        setAllMetrics(res.metrics)
        const keys = Object.keys(res.metrics)
        if (keys.length && !selected) setSelected(keys[0])
        setLoading(false)
      })
      .catch(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [cpId]) // eslint-disable-line react-hooks/exhaustive-deps

  const keys = Object.keys(allMetrics)

  const chartData = useMemo(() => {
    const pts = allMetrics[selected] ?? []
    return pts.map((p) => ({ label: p.time.slice(0, 10), value: p.value }))
  }, [selected, allMetrics])

  const currentVal = useMemo(() => {
    const pts = allMetrics[selected] ?? []
    return pts.length ? pts[pts.length - 1].value : null
  }, [selected, allMetrics])

  if (loading) return <DataState status="loading" />
  if (!keys.length) {
    return <DataState status="empty" emptyMessage="No metric data available" />
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <label
          htmlFor="cp-metric-picker"
          className="text-sm font-medium text-gray-700 dark:text-gray-300"
        >
          Metric
        </label>
        <select
          id="cp-metric-picker"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {keys.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        {currentVal !== null && (
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Latest: {currentVal.toFixed(2)}
          </span>
        )}
      </div>
      {chartData.length > 0 && (
        <AreaChart
          data={chartData}
          height={180}
          series={[{ key: 'value', name: selected, color: '#6366f1', fillOpacity: 0.15 }]}
          showLegend
        />
      )}
    </div>
  )
}

// ─── Forecast Panel ──────────────────────────────────────────────────────────

function ForecastPanel({ entityType, entityId }: { entityType: string; entityId: string }) {
  const [forecast, setForecast] = useState<RiskForecast | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchRiskForecast(entityType, entityId)
      .then((f) => {
        if (cancelled) return
        setForecast(f)
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
  }, [entityType, entityId])

  if (loading) return <DataState status="loading" />
  if (error || !forecast || !forecast.points.length) {
    return (
      <div className="py-6 text-center">
        <Badge variant="moderate">Insufficient history</Badge>
        {error && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">{error}</p>
        )}
      </div>
    )
  }

  const chartData = forecast.points.map((pt) => ({
    label: pt.time.slice(0, 10),
    value: pt.value,
    lower: pt.lower ?? pt.value,
    upper: pt.upper ?? pt.value,
  }))

  return (
    <AreaChart
      data={chartData}
      height={180}
      series={[
        { key: 'upper', name: 'Upper bound', color: '#f97316', fillOpacity: 0.15 },
        { key: 'lower', name: 'Lower bound', color: '#6366f1', fillOpacity: 0.15 },
        { key: 'value', name: 'Forecast', color: '#6366f1', fillOpacity: 0 },
      ]}
      showLegend
    />
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function ChokepointDetailView({ id }: ChokepointDetailViewProps) {
  const [cp, setCp] = useState<ChokepointDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isTracked, setIsTracked] = useState(() => tracked.chokepoints.has(id))

  useEffect(() => {
    return tracked.chokepoints.subscribe(() => setIsTracked(tracked.chokepoints.has(id)))
  }, [id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchChokepoint(id)
      .then((data) => {
        if (cancelled) return
        setCp(data)
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

  const toggleTrack = () => {
    if (isTracked) {
      tracked.chokepoints.remove(id)
    } else {
      tracked.chokepoints.add(id)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/chokepoints')}
            className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Back to Chokepoints"
          >
            <IconChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Chokepoint Detail
          </h1>
        </div>
        <Card>
          <DataState status="loading" />
        </Card>
      </div>
    )
  }

  if (error || !cp) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/chokepoints')}
            className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Back to Chokepoints"
          >
            <IconChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Chokepoint Detail
          </h1>
        </div>
        <Card>
          <DataState
            status="error"
            error={error ?? 'Chokepoint not found'}
            onRetry={() => window.location.reload()}
          />
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => navigate('/chokepoints')}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
          aria-label="Back to Chokepoints"
        >
          <IconChevronLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{cp.name}</h1>
            <SeverityBadge severity={cp.severity} />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {cp.updated_at ? `Updated ${cp.updated_at.slice(0, 10)}` : ''}
          </p>
        </div>
        <SyncButton />
        <button
          onClick={toggleTrack}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          aria-label={isTracked ? 'Untrack chokepoint' : 'Track chokepoint'}
        >
          {isTracked ? (
            <IconStarFilled className="w-4 h-4 text-amber-500" />
          ) : (
            <IconStar className="w-4 h-4 text-gray-400" />
          )}
          {isTracked ? 'Tracked' : 'Track'}
        </button>
      </div>

      {/* KPI Strip */}
      <KpiStrip cp={cp} />

      {/* Map */}
      {cp.lon != null && cp.lat != null && (
        <Card title="Location">
          <MiniMap center={[cp.lon, cp.lat]} zoom={5} height={240} showMarker />
        </Card>
      )}

      {/* 50-day breakdown chart */}
      <Card title="Transit Activity — 50-day strip">
        <BreakdownChart id={id} />
      </Card>

      {/* Metric drill-down */}
      <Card title="Metric Breakdown">
        <MetricDrilldown cpId={cp.id} />
      </Card>

      {/* Forecast panel */}
      <Card title="14-Day Forecast">
        <ForecastPanel entityType="chokepoint" entityId={id} />
      </Card>

      {/* LLM Narrative */}
      {cp.description && (
        <Card title="Narrative">
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {cp.description}
          </p>
        </Card>
      )}

      {/* Insights */}
      {cp.insights && cp.insights.length > 0 && (
        <Card title="Insights">
          <div>
            {cp.insights.map((item) => (
              <InsightRow key={item.id} insight={item} />
            ))}
          </div>
        </Card>
      )}

      {/* Event Log */}
      <Card title="Event Log">
        <EventLog entityType="chokepoint" entityId={id} />
      </Card>
    </div>
  )
}
