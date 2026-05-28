import React, { useState, useEffect, useMemo } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { AreaChart } from '../components/ui/AreaChart'
import { MiniMap } from '../components/ui/MiniMap'
import { InsightRow } from '../components/ui/InsightRow'
import { IconChevronLeft, IconStar, IconStarFilled } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPort, fetchPortMetrics } from '../api/ports'
import { fetchRiskForecast } from '../api/risk'
import { fetchStory } from '../api/story'
import { tracked } from '../data/tracked'
import type { PortDetail, RiskForecast, StoryEvent, MetricPoint } from '../api/types'

interface PortDetailViewProps {
  id: string
}

// ─── KPI Strip ───────────────────────────────────────────────────────────────

function KpiStrip({ port }: { port: PortDetail }) {
  const score = port.risk_snapshot?.composite_score ?? port.risk_score
  const trend = port.risk_snapshot?.trend

  const items = [
    { label: 'Risk Score', value: score != null ? score.toFixed(2) : '—' },
    { label: 'Trend', value: trend ?? '—' },
    { label: 'Severity', value: port.severity ?? '—' },
    { label: 'Locode', value: port.locode ?? '—' },
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

// ─── Metric Drill-down ────────────────────────────────────────────────────────

function MetricDrilldown({ portId }: { portId: number }) {
  const [allMetrics, setAllMetrics] = useState<Record<string, MetricPoint[]>>({})
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchPortMetrics(portId)
      .then((res) => {
        if (cancelled) return
        setAllMetrics(res.metrics)
        const keys = Object.keys(res.metrics)
        if (keys.length && !selected) setSelected(keys[0])
        setLoading(false)
      })
      .catch(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [portId]) // eslint-disable-line react-hooks/exhaustive-deps

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
          htmlFor="metric-picker"
          className="text-sm font-medium text-gray-700 dark:text-gray-300"
        >
          Metric
        </label>
        <select
          id="metric-picker"
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
  if (error) {
    return (
      <div className="py-6 text-center">
        <Badge variant="moderate">Insufficient history</Badge>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">{error}</p>
      </div>
    )
  }
  if (!forecast || !forecast.points.length) {
    return (
      <div className="py-6 text-center">
        <Badge variant="moderate">Insufficient history</Badge>
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

// ─── Event Log ───────────────────────────────────────────────────────────────

function EventLog({ entityId }: { entityId: string }) {
  const [events, setEvents] = useState<StoryEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchStory()
      .then((res) => {
        if (cancelled) return
        const filtered = res.events.filter((e) => !e.entity_id || e.entity_id === entityId)
        setEvents(filtered)
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
  }, [entityId])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!events.length) return <DataState status="empty" emptyMessage="No events recorded" />

  return (
    <div className="space-y-3">
      {events.map((ev) => (
        <div
          key={ev.id}
          className="flex gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-100 dark:border-gray-700"
        >
          <div className="flex-shrink-0 mt-0.5">
            <SeverityBadge severity={ev.severity} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{ev.title}</p>
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-0.5">{ev.narrative}</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {ev.timestamp ? ev.timestamp.slice(0, 16).replace('T', ' ') : ''}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function PortDetailView({ id }: PortDetailViewProps) {
  const [port, setPort] = useState<PortDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isTracked, setIsTracked] = useState(() => tracked.ports.has(id))

  useEffect(() => tracked.ports.subscribe(() => setIsTracked(tracked.ports.has(id))), [id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchPort(id)
      .then((p) => {
        if (cancelled) return
        setPort(p)
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
      tracked.ports.remove(id)
    } else {
      tracked.ports.add(id)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/ports')}
            className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
            aria-label="Back to Ports"
          >
            <IconChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Port Detail</h1>
        </div>
        <Card>
          <DataState status="loading" />
        </Card>
      </div>
    )
  }

  if (error || !port) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/ports')}
            className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Back to Ports"
          >
            <IconChevronLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Port Detail</h1>
        </div>
        <Card>
          <DataState status="error" error={error ?? 'Port not found'} onRetry={() => window.location.reload()} />
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => navigate('/ports')}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
          aria-label="Back to Ports"
        >
          <IconChevronLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{port.name}</h1>
            <SeverityBadge severity={port.severity} />
            {port.unlocode && (
              <Badge variant="info">{port.unlocode}</Badge>
            )}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {port.country}
            {port.region ? ` · ${port.region}` : ''}
            {port.updated_at ? ` · Updated ${port.updated_at.slice(0, 10)}` : ''}
          </p>
        </div>
        <button
          onClick={toggleTrack}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          aria-label={isTracked ? 'Untrack port' : 'Track port'}
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
      <KpiStrip port={port} />

      {/* Map */}
      {port.lon != null && port.lat != null && (
        <Card title="Location">
          <MiniMap
            center={[port.lon, port.lat]}
            zoom={6}
            height={240}
            showMarker
          />
        </Card>
      )}

      {/* Metric drill-down */}
      <Card title="Metric Breakdown">
        <MetricDrilldown portId={port.id} />
      </Card>

      {/* Forecast panel */}
      <Card title="14-Day Forecast">
        <ForecastPanel entityType="port" entityId={id} />
      </Card>

      {/* LLM Narrative */}
      {port.description && (
        <Card title="Narrative">
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {port.description}
          </p>
        </Card>
      )}

      {/* Insights */}
      {port.insights && port.insights.length > 0 && (
        <Card title="Insights">
          <div>
            {port.insights.map((item) => (
              <InsightRow key={item.id} insight={item} />
            ))}
          </div>
        </Card>
      )}

      {/* Event Log */}
      <Card title="Event Log">
        <EventLog entityId={id} />
      </Card>
    </div>
  )
}
