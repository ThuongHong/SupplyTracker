import React, { useEffect, useMemo, useState } from 'react'
import { Card } from './ui/Card'
import { DataState } from './ui/DataState'
import { AreaChart } from './ui/AreaChart'
import { IndicesPanel } from './charts/IndicesPanel'
import { fetchMarketInsights, getCachedMarket } from '../api/market'
import type { MarketInsights } from '../api/market'

const TRADE_LABELS: Record<string, string> = {
  port_calls: 'Port calls',
  import_volume: 'Import volume',
  export_volume: 'Export volume',
}

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toFixed(0)
}

interface Props {
  window: '7d' | '30d' | '90d'
}

/**
 * Growth & Market Insights, folded into the Overview page. Shows the market-desk
 * AI summary, trade-growth KPIs, the import/export trend, and the freight/bunker
 * panel. (The page's Morning Brief hero is a separate, dedicated decision brief.)
 */
export function MarketBrief({ window }: Props) {
  const [data, setData] = useState<MarketInsights | null>(() => getCachedMarket(window))
  const [loading, setLoading] = useState(!data)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const cached = getCachedMarket(window)
    setData(cached)
    setLoading(!cached)
    fetchMarketInsights(window)
      .then((res) => {
        if (cancelled) return
        setData((prev) => (prev && prev.as_of === res.as_of && prev.window === res.window ? prev : res))
        setLoading(false)
      })
      .catch((e: Error) => {
        if (cancelled) return
        if (!cached) setError(e.message)
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [window])

  const tradeChart = useMemo(() => {
    if (!data) return []
    const imp = data.trade_growth.import_volume?.series ?? []
    const exp = data.trade_growth.export_volume?.series ?? []
    const byTime = new Map<string, { label: string; value: number; import: number; export: number }>()
    for (const p of imp) {
      byTime.set(p.time, { label: p.time.slice(0, 10), value: 0, import: p.value, export: 0 })
    }
    for (const p of exp) {
      const row = byTime.get(p.time) ?? { label: p.time.slice(0, 10), value: 0, import: 0, export: 0 }
      row.export = p.value
      byTime.set(p.time, row)
    }
    return Array.from(byTime.values())
  }, [data])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} />
  if (!data) return <DataState status="empty" emptyMessage="No market data" />

  return (
    <section className="space-y-5">
      <div className="section__head">
        <div>
          <p className="label-cap">Market desk</p>
          <h2 className="text-4xl">Growth &amp; Market Insights</h2>
        </div>
      </div>

      {/* AI narrative — the morning brief */}
      <Card title="AI summary">
        <p className="text-sm leading-relaxed text-[color:var(--ink-2)]">{data.narrative}</p>
        <p className="mt-2 mono text-xs text-[color:var(--ink-4)]">
          {data.tracked_count} tracked ports · as of {data.as_of?.slice(0, 10) ?? '—'}
        </p>
      </Card>

      {/* Trade growth KPI cards */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {Object.entries(TRADE_LABELS).map(([key, label]) => {
          const m = data.trade_growth[key]
          const pct = m?.pct_change
          const up = (pct ?? 0) >= 0
          return (
            <div
              key={key}
              className="card px-4 py-3"
            >
              <p className="text-xs font-medium text-[color:var(--ink-4)]">{label}</p>
              <p className="mt-1 text-2xl font-bold text-[color:var(--ink)]">{fmt(m?.latest)}</p>
              <p
                className="mono text-xs"
                style={{ color: pct == null ? 'var(--ink-4)' : up ? 'var(--positive)' : 'var(--negative)' }}
              >
                {pct == null ? 'no trend' : `${up ? '▲' : '▼'} ${Math.abs(pct).toFixed(1)}% / ${window}`}
              </p>
            </div>
          )
        })}
      </div>

      {/* Trade volume trend */}
      <Card title="Trade volume — tracked ports (import vs export)">
        {tradeChart.length === 0 ? (
          <DataState status="empty" emptyMessage="Sync some ports to see trade trends" />
        ) : (
          <AreaChart
            data={tradeChart}
            height={220}
            showLegend
            series={[
              { key: 'import', name: 'Import', color: 'var(--accent)', fillOpacity: 0.15 },
              { key: 'export', name: 'Export', color: 'var(--positive)', fillOpacity: 0.15 },
            ]}
          />
        )}
      </Card>

      {/* Freight & bunker market */}
      <Card title="Macro Freight Indicators">
        <IndicesPanel indices={data.market.indices} bunker={data.market.bunker} />
      </Card>
    </section>
  )
}
