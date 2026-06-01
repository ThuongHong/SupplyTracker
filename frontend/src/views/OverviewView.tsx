import React, { useEffect, useMemo, useState } from 'react'
import { AreaChart } from '../components/ui/AreaChart'
import { DataState } from '../components/ui/DataState'
import { MarketBrief } from '../components/MarketBrief'
import { ChatMarkdown } from '../components/ChatMarkdown'
import { SeverityBadge, normalizeSeverity } from '../components/ui/Badge'
import { StatusDot } from '../components/ui/StatusDot'
import { navigate } from '../router'
import { fetchBrief, getCachedBrief } from '../api/brief'
import { fetchChokepoints } from '../api/chokepoints'
import { fetchIndices, fetchIndexTimeseries } from '../api/indices'
import { fetchInsights } from '../api/insights'
import { fetchPorts } from '../api/ports'
import { tracked } from '../data/tracked'
import { buildFallbackBrief } from '../lib/briefFallback'
import type { ChokepointSummary, IndexSummary, InsightItem, PortSummary } from '../api/types'

type Range = 7 | 30 | 90

const RANGE_OPTIONS: Range[] = [7, 30, 90]
const SEVERITY_RANK: Record<string, number> = {
  critical: 5,
  high: 4,
  elevated: 3,
  moderate: 3,
  low: 2,
  unknown: 1,
}

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value == null || Number.isNaN(value)) return '-'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function formatPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function severityColor(severity: string | null | undefined) {
  const normalized = normalizeSeverity(severity)
  if (normalized === 'critical' || normalized === 'high') return 'var(--negative)'
  if (normalized === 'elevated' || normalized === 'moderate') return 'var(--caution)'
  if (normalized === 'low') return 'var(--positive)'
  return 'var(--ink-4)'
}

function riskPercent(value: number | null | undefined) {
  if (value == null) return null
  return value <= 1 ? value * 100 : value
}

function scoreOf(item: { risk_score?: number | null; severity?: string | null }) {
  return riskPercent(item.risk_score) ?? SEVERITY_RANK[normalizeSeverity(item.severity)] * 20
}

function indexByName(indices: IndexSummary[], names: string[]) {
  return indices.find((idx) => names.some((name) => idx.index_name.toLowerCase().includes(name)))
}

function buildHeadline(insights: InsightItem[], indices: IndexSummary[]) {
  const lead = insights.find((item) => item.attention_level === 'critical' || item.attention_level === 'high')
  if (lead) return lead.title
  const freight = indexByName(indices, ['fbx', 'bdi', 'baltic'])
  if (freight) {
    return `Freight tape ${freight.change_pct_7d >= 0 ? 'firms' : 'softens'} as port risk remains under watch`
  }
  return 'Global supply chain risk opens steady with watchpoints across ports and arteries'
}

function MarketPanel({ indices, loading }: { indices: IndexSummary[]; loading: boolean }) {
  const [selected, setSelected] = useState('')
  const [range, setRange] = useState<Range>(30)
  const [points, setPoints] = useState<{ label: string; value: number }[]>([])
  const [chartLoading, setChartLoading] = useState(false)

  useEffect(() => {
    if (!selected && indices.length) setSelected(indices[0].index_name)
  }, [indices, selected])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    setChartLoading(true)
    fetchIndexTimeseries(selected)
      .then((series) => {
        if (cancelled) return
        const next = series.points.slice(-range).map((point) => ({
          label: point.time.slice(5, 10),
          value: point.value,
        }))
        setPoints(next)
        setChartLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          const fallback = indices.find((idx) => idx.index_name === selected)
          setPoints(fallback ? [{ label: 'Latest', value: fallback.latest_value }] : [])
          setChartLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [indices, range, selected])

  if (loading) return <DataState status="loading" />
  if (!indices.length) return <DataState status="empty" emptyMessage="No indices data" />

  return (
    <section className="space-y-5">
      <div className="section__head">
        <div>
          <p className="label-cap">Markets</p>
          <h2 className="text-4xl">Indices board</h2>
        </div>
        <div className="flex gap-2">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setRange(option)}
              className={[
                'ui border px-3 py-1.5 text-xs font-semibold',
                range === option
                  ? 'border-[color:var(--ink)] bg-[color:var(--ink)] text-[color:var(--paper)]'
                  : 'border-[color:var(--rule-thin)] bg-[color:var(--card)] text-[color:var(--ink-2)]',
              ].join(' ')}
            >
              {option}D
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_0.85fr]">
        <div className="border border-[color:var(--rule-thin)] bg-[color:var(--card)] p-4">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {indices.map((idx) => {
              const active = selected === idx.index_name
              return (
                <button
                  key={idx.index_name}
                  type="button"
                  onClick={() => setSelected(idx.index_name)}
                  className={[
                    'border p-3 text-left',
                    active
                      ? 'border-[color:var(--ink)] bg-[color:var(--paper)]'
                      : 'border-[color:var(--rule-hair)] bg-transparent hover:bg-[color:var(--paper)]',
                  ].join(' ')}
                >
                  <p className="label-cap">{idx.index_name}</p>
                  <p className="mono mt-2 text-lg font-semibold text-[color:var(--ink)]">
                    {formatNumber(idx.latest_value, 2)}
                  </p>
                  <p
                    className="mono mt-1 text-xs"
                    style={{ color: idx.change_pct_7d >= 0 ? 'var(--positive)' : 'var(--negative)' }}
                  >
                    7D {formatPct(idx.change_pct_7d)}
                  </p>
                </button>
              )
            })}
          </div>
          <div className="mt-5">
            {chartLoading ? <DataState status="loading" /> : <AreaChart data={points} height={260} />}
          </div>
        </div>

        <aside className="border-l border-[color:var(--rule-thin)] pl-5">
          <p className="label-cap">Watchlist</p>
          <div className="mt-3 divide-y divide-[color:var(--rule-hair)]">
            {indices.slice(0, 6).map((idx) => (
              <button
                key={idx.index_name}
                type="button"
                onClick={() => setSelected(idx.index_name)}
                className="grid w-full grid-cols-[1fr_auto] gap-3 py-3 text-left"
              >
                <span className="font-semibold text-[color:var(--ink)]">{idx.index_name}</span>
                <span className="mono text-[color:var(--ink-2)]">{formatNumber(idx.latest_value, 1)}</span>
                <span className="text-xs text-[color:var(--ink-3)]">{idx.description ?? 'Global freight index'}</span>
                <span
                  className="mono text-xs"
                  style={{ color: idx.change_pct_30d >= 0 ? 'var(--positive)' : 'var(--negative)' }}
                >
                  30D {formatPct(idx.change_pct_30d)}
                </span>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </section>
  )
}

function ArteriesTable({ chokepoints, loading }: { chokepoints: ChokepointSummary[]; loading: boolean }) {
  if (loading) return <DataState status="loading" />
  if (!chokepoints.length) return <DataState status="empty" emptyMessage="No chokepoint data" />

  return (
    <section className="space-y-4">
      <div className="section__head">
        <div>
          <p className="label-cap">Arteries</p>
          <h2 className="text-4xl">Chokepoint atlas</h2>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="dtable">
          <thead>
            <tr>
              <th>Chokepoint</th>
              <th>Status</th>
              <th>Transit time</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {chokepoints.slice(0, 8).map((cp) => {
              const transit = cp.transit_time_hours ?? cp.transit_count
              const delta = cp.transit_delta_pct ?? (scoreOf(cp) - 50) / 5
              return (
                <tr key={cp.id} onClick={() => navigate(`/chokepoints/${encodeURIComponent(cp.id)}`)}>
                  <td>
                    <p className="font-semibold text-[color:var(--ink)]">{cp.name}</p>
                    <p className="mt-1 text-xs text-[color:var(--ink-3)]">{cp.region ?? 'Global artery'}</p>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-2">
                      <StatusDot severity={cp.severity} />
                      <SeverityBadge severity={cp.severity} />
                    </span>
                  </td>
                  <td className="mono">{transit != null ? `${formatNumber(transit, 1)} h` : '-'}</td>
                  <td
                    className="mono"
                    style={{ color: delta > 0 ? 'var(--negative)' : 'var(--positive)' }}
                  >
                    {formatPct(delta)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function PortsDigest({ ports, loading }: { ports: PortSummary[]; loading: boolean }) {
  if (loading) return <DataState status="loading" />
  if (!ports.length) return <DataState status="empty" emptyMessage="No port data" />

  return (
    <section className="space-y-4">
      <div className="section__head">
        <div>
          <p className="label-cap">Ports</p>
          <h2 className="text-4xl">Terminal digest</h2>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="dtable">
          <thead>
            <tr>
              <th>Port</th>
              <th>Vessels</th>
              <th>Dwell</th>
              <th>Congestion</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {ports.slice(0, 8).map((port) => {
              const score = Math.min(Math.max(riskPercent(port.congestion_score) ?? scoreOf(port), 0), 100)
              return (
                <tr key={port.id} onClick={() => navigate(`/ports/${encodeURIComponent(port.id)}`)}>
                  <td>
                    <p className="font-semibold text-[color:var(--ink)]">{port.name}</p>
                    <p className="mt-1 text-xs text-[color:var(--ink-3)]">{port.country}</p>
                  </td>
                  <td className="mono">{formatNumber(port.vessel_count ?? score / 2, 0)}</td>
                  <td className="mono">{port.dwell_time_hours != null ? `${formatNumber(port.dwell_time_hours, 1)} h` : '-'}</td>
                  <td>
                    <span className="bar-cell" aria-label={`Congestion ${formatNumber(score, 0)} percent`}>
                      <span style={{ width: `${score}%` }} />
                    </span>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-2">
                      <StatusDot severity={port.severity} />
                      <SeverityBadge severity={port.severity} />
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function OverviewView() {
  const [ports, setPorts] = useState<PortSummary[]>([])
  const [portsLoading, setPortsLoading] = useState(true)
  const [portsError, setPortsError] = useState<string | null>(null)
  const [chokepoints, setChokepoints] = useState<ChokepointSummary[]>([])
  const [chokepointsLoading, setChokepointsLoading] = useState(true)
  const [indices, setIndices] = useState<IndexSummary[]>([])
  const [indicesLoading, setIndicesLoading] = useState(true)
  const [insights, setInsights] = useState<InsightItem[]>([])
  const [insightsLoading, setInsightsLoading] = useState(true)
  const [trackedPortIds, setTrackedPortIds] = useState<Set<string>>(() => new Set(tracked.ports.getAll()))
  const marketWindow = (localStorage.getItem('entity_window') as '7d' | '30d' | '90d') || '30d'
  const cachedBrief = getCachedBrief()
  const [brief, setBrief] = useState<string | null>(() => cachedBrief?.brief ?? null)
  const [briefAsOf, setBriefAsOf] = useState<string | null>(() => cachedBrief?.as_of ?? null)
  const [briefLoading, setBriefLoading] = useState(!cachedBrief)
  const [briefFailed, setBriefFailed] = useState(false)

  useEffect(() => tracked.ports.subscribe(() => setTrackedPortIds(new Set(tracked.ports.getAll()))), [])

  useEffect(() => {
    // Overview is the user's tracked dashboard: scope ports to what they track,
    // so the "Ports monitored" count, congestion, and digest match the brief.
    fetchPorts({ tracked: true, limit: 200 })
      .then((res) => setPorts(res.items))
      .catch((e: Error) => setPortsError(e.message))
      .finally(() => setPortsLoading(false))

    fetchChokepoints({ limit: 100 })
      .then((res) => setChokepoints(res.items))
      .catch(() => undefined)
      .finally(() => setChokepointsLoading(false))

    fetchIndices()
      .then((res) => setIndices(res.items))
      .catch(() => undefined)
      .finally(() => setIndicesLoading(false))

    fetchInsights({ limit: 20 })
      .then((res) => setInsights(res.items))
      .catch(() => undefined)
      .finally(() => setInsightsLoading(false))
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchBrief()
      .then((res) => {
        if (cancelled) return
        setBrief(res.brief)
        setBriefAsOf(res.as_of)
        setBriefLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setBriefFailed(true)
        setBriefLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const sortedPorts = useMemo(() => {
    return [...ports].sort((a, b) => {
      const pinned = Number(trackedPortIds.has(String(b.id))) - Number(trackedPortIds.has(String(a.id)))
      if (pinned !== 0) return pinned
      return scoreOf(b) - scoreOf(a)
    })
  }, [ports, trackedPortIds])

  const sortedChokepoints = useMemo(
    () => [...chokepoints].sort((a, b) => scoreOf(b) - scoreOf(a)),
    [chokepoints],
  )

  // Scope insights to tracked entities so the hero headline/fallback match the
  // tracked-scoped brief. Ports key off portid; chokepoints off a name slug
  // (collector convention), matching the insight's affected_entities ids.
  const trackedEntityIds = useMemo(() => {
    const ids = new Set<string>(ports.map((port) => port.portid))
    chokepoints
      .filter((cp) => cp.is_tracked)
      .forEach((cp) => ids.add(cp.name.toLowerCase().replace(/ /g, '_')))
    return ids
  }, [ports, chokepoints])

  const scopedInsights = useMemo(
    () =>
      insights.filter((item) =>
        (item.affected_entities ?? []).some((entity) => trackedEntityIds.has(entity.id)),
      ),
    [insights, trackedEntityIds],
  )

  // FBX (Freightos Baltic Index) is the freight tape actually collected; there is
  // no separate "BDI" series in the data.
  const freight = indexByName(indices, ['fbx', 'bdi', 'baltic'])
  const anomalyCount = scopedInsights.filter((item) => item.attention_level === 'critical' || item.attention_level === 'high').length
  const congestedPorts = ports.filter((port) => scoreOf(port) >= 60).length

  return (
    <div className="space-y-10">
      <section className="grid gap-8 border-b border-[color:var(--rule-thin)] pb-8 lg:grid-cols-[2.4fr_1fr]">
        <article>
          <p className="label-cap">Morning Brief</p>
          <h1 className="serif mt-3 text-5xl font-semibold leading-[0.96] text-[color:var(--ink)] md:text-7xl">
            {buildHeadline(scopedInsights, indices)}
          </h1>
          <p className="label-cap mt-5">By SupplyTracker risk desk{briefAsOf ? ` · as of ${briefAsOf}` : ''}</p>
          <div className="mt-6 max-w-3xl text-[color:var(--ink-2)]">
            {briefLoading ? (
              <div className="space-y-3" aria-hidden="true">
                <div className="h-4 w-full bg-[color:var(--paper-2)]" />
                <div className="h-4 w-11/12 bg-[color:var(--paper-2)]" />
                <div className="h-4 w-9/12 bg-[color:var(--paper-2)]" />
              </div>
            ) : (
              <ChatMarkdown
                content={
                  briefFailed || !brief
                    ? buildFallbackBrief({
                        topRiskTitle:
                          scopedInsights.find(
                            (item) => item.attention_level === 'critical' || item.attention_level === 'high',
                          )?.title ?? null,
                        bdiChangePct7d: freight?.change_pct_7d ?? null,
                        congestedPorts,
                      })
                    : brief
                }
              />
            )}
          </div>
        </article>

        <aside className="border-l border-[color:var(--rule-thin)] pl-6">
          <p className="label-cap">Evidence</p>
          <div className="mt-4 divide-y divide-[color:var(--rule-hair)]">
            {[
              { label: 'FBX', value: freight ? formatNumber(freight.latest_value, 0) : '-', delta: freight ? formatPct(freight.change_pct_7d) : '-' },
              { label: 'Ports monitored', value: formatNumber(ports.length, 0), delta: `${congestedPorts} congested` },
              { label: 'Chokepoints', value: formatNumber(chokepoints.length, 0), delta: `${sortedChokepoints.slice(0, 3).length} lead watch` },
              { label: 'Open anomalies', value: formatNumber(anomalyCount, 0), delta: insightsLoading ? 'Loading' : 'High+ severity' },
            ].map((row) => (
              <div key={row.label} className="grid grid-cols-[1fr_auto] gap-3 py-4">
                <span className="text-sm text-[color:var(--ink-3)]">{row.label}</span>
                <strong className="mono text-xl text-[color:var(--ink)]">{row.value}</strong>
                <span className="mono col-span-2 text-xs text-[color:var(--ink-4)]">{row.delta}</span>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <MarketBrief window={marketWindow} />

      <MarketPanel indices={indices} loading={indicesLoading} />

      <div className="space-y-10">
        <ArteriesTable chokepoints={sortedChokepoints} loading={chokepointsLoading} />
        {portsError ? (
          <DataState status="error" error={portsError} />
        ) : (
          <PortsDigest ports={sortedPorts} loading={portsLoading} />
        )}
      </div>
    </div>
  )
}
