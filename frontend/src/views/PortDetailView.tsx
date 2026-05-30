import React, { useState, useEffect, useMemo } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { computeAnomaly } from '../lib/anomaly'
import { formatMetric } from '../lib/format'
import { MiniMap } from '../components/ui/MiniMap'
import { InsightRow } from '../components/ui/InsightRow'
import { WindowPicker } from '../components/ui/WindowPicker'
import { Tabs } from '../components/ui/Tabs'
import { IconChevronLeft, IconStarFilled, IconRefresh } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchPort, fetchPortMetrics } from '../api/ports'
import { fetchEntityDashboard } from '../api/dashboard'
import { getSyncToken, syncPort, untrackPort } from '../api/sync'
import { EventLog } from '../components/EventLog'
import { VesselMixChart } from '../components/charts/VesselMixChart'
import { AnomalyCard } from '../components/charts/AnomalyCard'
import { EntitySummary } from '../components/charts/EntitySummary'
import { RiskScoreInfo } from '../components/RiskScoreInfo'
import { MacroSensitivity } from '../components/MacroSensitivity'
import type { PortDetail, MetricPoint, DashboardResponse } from '../api/types'

interface PortDetailViewProps {
  id: string
}

// ─── KPI Strip ───────────────────────────────────────────────────────────────

function KpiStrip({ port }: { port: PortDetail }) {
  const score = port.risk_snapshot?.composite_score ?? port.risk_score
  const trend = port.risk_snapshot?.trend

  const items = [
    { label: 'Risk Score', value: score != null ? score.toFixed(2) : '—', info: true },
    { label: 'Trend', value: trend ?? '—' },
    { label: 'Severity', value: port.severity ?? '—' },
    { label: 'Locode', value: port.locode ?? '—' },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.map(({ label, value, info }) => (
        <div
          key={label}
          className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3"
        >
          <p className="flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400">
            {label}
            {info && <RiskScoreInfo />}
          </p>
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

  const series = useMemo(() => allMetrics[selected] ?? [], [selected, allMetrics])

  const anomaly = useMemo(
    () => computeAnomaly(series.map((p) => p.value), selected),
    [series, selected],
  )

  const currentVal = series.length ? series[series.length - 1].value : null

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
            <option key={k} value={k}>{formatMetric(k)}</option>
          ))}
        </select>
        {currentVal !== null && (
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Latest: {currentVal.toFixed(2)}
          </span>
        )}
      </div>
      {series.length > 0 && <AnomalyCard series={series} stats={anomaly} />}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function PortDetailView({ id }: PortDetailViewProps) {
  const [port, setPort] = useState<PortDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [untracking, setUntracking] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [tab, setTab] = useState<'overview' | 'events'>('overview')

  const [window, setWindow] = useState<'7d' | '30d' | '90d'>(() => {
    return (localStorage.getItem('entity_window') as '7d' | '30d' | '90d') || '30d'
  })
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [dashLoading, setDashLoading] = useState(true)

  const canSync = getSyncToken() !== null

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
  }, [id, reloadKey])

  useEffect(() => {
    let cancelled = false
    setDashLoading(true)
    fetchEntityDashboard('port', id, window)
      .then((d) => { if (!cancelled) { setDashboard(d); setDashLoading(false) } })
      .catch(() => { if (!cancelled) setDashLoading(false) })
    return () => { cancelled = true }
  }, [id, window, reloadKey])

  const handleWindowChange = (w: '7d' | '30d' | '90d') => {
    setWindow(w)
    localStorage.setItem('entity_window', w)
  }

  const isTracked = port?.is_tracked ?? false

  // Sync = fetch latest 90 days + track, then auto-refresh all charts.
  const handleSync = async () => {
    if (!port || syncing) return
    setSyncing(true)
    try {
      await syncPort(port.portid)
      setReloadKey((k) => k + 1)
    } finally {
      setSyncing(false)
    }
  }

  const handleUntrack = async () => {
    if (!port || untracking) return
    setUntracking(true)
    try {
      await untrackPort(port.portid)
      setReloadKey((k) => k + 1)
    } finally {
      setUntracking(false)
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
          <DataState status="error" error={error ?? 'Port not found'} onRetry={() => globalThis.location.reload()} />
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
        <WindowPicker value={window} onChange={handleWindowChange} />
        {canSync && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleSync}
              disabled={syncing || untracking}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed"
              aria-label={isTracked ? 'Re-sync port data' : 'Sync port data'}
            >
              {syncing ? (
                <>
                  <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Syncing…
                </>
              ) : (
                <>
                  <IconRefresh className="w-4 h-4 text-gray-400" />
                  {isTracked ? 'Re-sync' : 'Sync data'}
                </>
              )}
            </button>
            {isTracked && (
              <button
                onClick={handleUntrack}
                disabled={syncing || untracking}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed"
                aria-label="Untrack port"
                title="Untrack"
              >
                {untracking ? (
                  <>
                    <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Untracking…
                  </>
                ) : (
                  <>
                    <IconStarFilled className="w-4 h-4 text-amber-500" />
                    Untrack
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { key: 'overview', label: 'Overview' },
          { key: 'events', label: 'News' },
        ]}
        active={tab}
        onChange={(k) => setTab(k as 'overview' | 'events')}
      />

      {tab === 'events' && (
        <Card title="Related News">
          <EventLog entityType="port" entityId={id} />
        </Card>
      )}

      {tab === 'overview' && <>

      {/* KPI Strip */}
      <KpiStrip port={port} />

      {/* AI Summary — grounded in throughput, macro links, disruptions */}
      <EntitySummary entityType="port" entityId={id} window={window} reloadKey={reloadKey} />

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

      {/* Metric drill-down — each metric with its own z-score anomaly plot */}
      <Card title="Metric Breakdown — z-score anomaly">
        <MetricDrilldown portId={port.id} />
      </Card>

      {/* Macro sensitivity — lead-lag of this port's trade vs macro indices */}
      <Card title="Macro sensitivity">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <MacroSensitivity items={dashboard?.macro_sensitivity} />
        )}
      </Card>

      {/* Vessel mix by cargo type (PortWatch port calls) */}
      <Card title="Vessel Mix — port calls by cargo type">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <VesselMixChart data={dashboard?.charts.vessel_mix ?? []} />
        )}
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

      </>}
    </div>
  )
}
