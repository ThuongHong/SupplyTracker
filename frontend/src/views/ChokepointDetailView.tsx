import React, { useState, useEffect } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { AreaChart } from '../components/ui/AreaChart'
import { MiniMap } from '../components/ui/MiniMap'
import { InsightRow } from '../components/ui/InsightRow'
import { WindowPicker } from '../components/ui/WindowPicker'
import { Tabs } from '../components/ui/Tabs'
import { IconChevronLeft, IconStarFilled, IconRefresh } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchChokepoint, fetchChokepointBreakdown } from '../api/chokepoints'
import { fetchEntityDashboard } from '../api/dashboard'
import { getSyncToken, syncChokepoint, untrackChokepoint } from '../api/sync'
import { EventLog } from '../components/EventLog'
import { VesselMixChart } from '../components/charts/VesselMixChart'
import { AnomalyCard } from '../components/charts/AnomalyCard'
import { EntitySummary } from '../components/charts/EntitySummary'
import { RiskScoreInfo } from '../components/RiskScoreInfo'
import { MacroSensitivity } from '../components/MacroSensitivity'
import type { ChokepointDetail, BreakdownDay, DashboardResponse } from '../api/types'

interface ChokepointDetailViewProps {
  id: string
}

// ─── KPI Strip ───────────────────────────────────────────────────────────────

function KpiStrip({ cp, latestDay }: { cp: ChokepointDetail; latestDay?: BreakdownDay }) {
  const score = cp.risk_snapshot?.composite_score ?? cp.risk_score
  const trend = cp.risk_snapshot?.trend

  const items = [
    { label: 'Risk Score', value: score != null ? score.toFixed(2) : '—', info: true },
    { label: 'Trend', value: trend ?? '—' },
    { label: 'Severity', value: cp.severity ?? '—' },
    {
      label: 'Latest Transit',
      value: latestDay ? latestDay.total.toFixed(0) : '—',
    },
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

// ─── Breakdown Chart ─────────────────────────────────────────────────────────

function BreakdownChart({
  id,
  onLatestDay,
}: {
  id: string
  onLatestDay?: (day: BreakdownDay) => void
}) {
  const [days, setDays] = useState<BreakdownDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchChokepointBreakdown(id)
      .then((bd) => {
        if (cancelled) return
        const slice = bd.days.slice(-50)
        setDays(slice)
        if (slice.length && onLatestDay) onLatestDay(slice[slice.length - 1])
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
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!days.length) return <DataState status="empty" emptyMessage="No breakdown data" />

  const chartData = days.map((d) => ({
    label: d.date.slice(5),
    value: d.total,
  }))

  return <AreaChart data={chartData} height={180} />
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function ChokepointDetailView({ id }: ChokepointDetailViewProps) {
  const [cp, setCp] = useState<ChokepointDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [untracking, setUntracking] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [tab, setTab] = useState<'overview' | 'events'>('overview')
  const [latestDay, setLatestDay] = useState<BreakdownDay | undefined>()

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
  }, [id, reloadKey])

  useEffect(() => {
    let cancelled = false
    setDashLoading(true)
    fetchEntityDashboard('chokepoint', id, window)
      .then((d) => { if (!cancelled) { setDashboard(d); setDashLoading(false) } })
      .catch(() => { if (!cancelled) setDashLoading(false) })
    return () => { cancelled = true }
  }, [id, window, reloadKey])

  const handleWindowChange = (w: '7d' | '30d' | '90d') => {
    setWindow(w)
    localStorage.setItem('entity_window', w)
  }

  const isTracked = cp?.is_tracked ?? false

  const handleSync = async () => {
    if (!cp || syncing) return
    setSyncing(true)
    try {
      await syncChokepoint(cp.chokepointid)
      setReloadKey((k) => k + 1)
    } finally {
      setSyncing(false)
    }
  }

  const handleUntrack = async () => {
    if (!cp || untracking) return
    setUntracking(true)
    try {
      await untrackChokepoint(cp.chokepointid)
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
            onRetry={() => globalThis.location.reload()}
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
        <WindowPicker value={window} onChange={handleWindowChange} />
        {canSync && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleSync}
              disabled={syncing || untracking}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed"
              aria-label={isTracked ? 'Re-sync chokepoint data' : 'Sync chokepoint data'}
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
                aria-label="Untrack chokepoint"
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
          <EventLog entityType="chokepoint" entityId={id} />
        </Card>
      )}

      {tab === 'overview' && <>

      {/* KPI Strip */}
      <KpiStrip cp={cp} latestDay={latestDay} />

      {/* AI Summary — grounded in transit, macro links, disruptions */}
      <EntitySummary entityType="chokepoint" entityId={id} window={window} reloadKey={reloadKey} />

      {/* Map */}
      {cp.lon != null && cp.lat != null && (
        <Card title="Location">
          <MiniMap center={[cp.lon, cp.lat]} zoom={5} height={240} showMarker />
        </Card>
      )}

      {/* 50-day breakdown chart — kept as-is (uses separate breakdown endpoint) */}
      <Card title="Transit Activity — 50-day strip">
        <BreakdownChart id={id} onLatestDay={setLatestDay} />
      </Card>

      {/* Throughput anomaly (z-score hypothesis) */}
      <Card title="Throughput anomaly (z-score)">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <AnomalyCard
            series={dashboard?.charts.transit_volume ?? []}
            stats={dashboard?.stats.anomaly}
          />
        )}
      </Card>

      {/* Macro sensitivity — lead-lag of transit volume vs macro indices */}
      <Card title="Macro sensitivity">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <MacroSensitivity items={dashboard?.macro_sensitivity} />
        )}
      </Card>

      {/* Transit mix by vessel type (PortWatch) */}
      <Card title="Transit Mix — by vessel type">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <VesselMixChart data={dashboard?.charts.vessel_mix ?? []} />
        )}
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

      </>}
    </div>
  )
}
