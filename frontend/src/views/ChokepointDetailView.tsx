import React, { useState, useEffect } from 'react'
import { Card } from '../components/ui/Card'
import { Badge, SeverityBadge } from '../components/ui/Badge'
import { DataState } from '../components/ui/DataState'
import { AreaChart } from '../components/ui/AreaChart'
import { MiniMap } from '../components/ui/MiniMap'
import { InsightRow } from '../components/ui/InsightRow'
import { WindowPicker } from '../components/ui/WindowPicker'
import { IconChevronLeft, IconStar, IconStarFilled } from '../components/ui/icons'
import { navigate } from '../router'
import { fetchChokepoint, fetchChokepointBreakdown } from '../api/chokepoints'
import { fetchEntityDashboard } from '../api/dashboard'
import { tracked } from '../data/tracked'
import { EventLog } from '../components/EventLog'
import { SyncButton } from '../components/SyncButton'
import { VesselCountChart } from '../components/charts/VesselCountChart'
import { MedianSpeedChart } from '../components/charts/MedianSpeedChart'
import { RiskForecastChart } from '../components/charts/RiskForecastChart'
import { IndicesPanel } from '../components/charts/IndicesPanel'
import type { ChokepointDetail, BreakdownDay, DashboardResponse } from '../api/types'

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
  const [isTracked, setIsTracked] = useState(() => tracked.chokepoints.has(id))
  const [latestDay, setLatestDay] = useState<BreakdownDay | undefined>()

  const [window, setWindow] = useState<'7d' | '30d' | '90d'>(() => {
    return (localStorage.getItem('entity_window') as '7d' | '30d' | '90d') || '30d'
  })
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [dashLoading, setDashLoading] = useState(true)

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

  useEffect(() => {
    let cancelled = false
    setDashLoading(true)
    fetchEntityDashboard('chokepoint', id, window)
      .then((d) => { if (!cancelled) { setDashboard(d); setDashLoading(false) } })
      .catch(() => { if (!cancelled) setDashLoading(false) })
    return () => { cancelled = true }
  }, [id, window])

  const handleWindowChange = (w: '7d' | '30d' | '90d') => {
    setWindow(w)
    localStorage.setItem('entity_window', w)
  }

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
      <KpiStrip cp={cp} latestDay={latestDay} />

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

      {/* Risk & Forecast from dashboard bundle */}
      <Card title="Risk & Forecast">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <RiskForecastChart
            riskTrend={dashboard?.charts.risk_trend ?? []}
            forecast={dashboard?.charts.forecast ?? []}
          />
        )}
      </Card>

      {/* Vessel Count */}
      <Card title="Vessel Count">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <VesselCountChart data={dashboard?.charts.vessel_count ?? []} />
        )}
      </Card>

      {/* Median Speed */}
      <Card title="Median Speed">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <MedianSpeedChart data={dashboard?.charts.median_speed ?? []} />
        )}
      </Card>

      {/* Macro Indices */}
      <Card title="Macro Indices">
        {dashLoading ? (
          <DataState status="loading" />
        ) : (
          <IndicesPanel
            indices={dashboard?.charts.indices ?? []}
            bunker={dashboard?.charts.bunker ?? []}
          />
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

      {/* Event Log */}
      <Card title="Event Log">
        <EventLog entityType="chokepoint" entityId={id} />
      </Card>
    </div>
  )
}
