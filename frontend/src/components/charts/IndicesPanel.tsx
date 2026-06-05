import React, { useState } from 'react'
import { AreaChart } from '../ui/AreaChart'

interface Props {
  indices: Array<{ time: string; fbx?: number; wci?: number }>
  bunker: Array<{ time: string; value: number }>
}

const indexSeries = [
  { key: 'fbx', name: 'Freight cost proxy (rebased)', color: 'var(--caution)', fillOpacity: 0.15 },
  { key: 'wci', name: 'Ocean freight proxy (rebased)', color: 'var(--accent)', fillOpacity: 0.15 },
]

const bunkerSeries = [
  { key: 'value', name: 'Bunker price', color: 'var(--ink-4)', fillOpacity: 0.2 },
]

export function IndicesPanel({ indices, bunker }: Props) {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('indices_panel_collapsed') === 'true'
  })

  const toggle = () => {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem('indices_panel_collapsed', String(next))
  }

  // fbx (~3) and wci (~445) live on different scales, so rebase both to 100 at
  // their first point to share one Y-axis. The origin values are noted below the
  // chart so the absolute levels aren't lost.
  const firstFbxPoint = indices.find(d => d.fbx != null)
  const firstWciPoint = indices.find(d => d.wci != null)
  const firstFbx = firstFbxPoint?.fbx ?? 1
  const firstWci = firstWciPoint?.wci ?? 1
  const originDate = (firstFbxPoint ?? firstWciPoint)?.time.slice(0, 10)

  const indexData = indices.map(d => ({
    label: d.time.slice(0, 10),
    value: 0,
    fbx: d.fbx != null ? (d.fbx / firstFbx) * 100 : (NaN as number),
    wci: d.wci != null ? (d.wci / firstWci) * 100 : (NaN as number),
  }))

  const bunkerData = bunker.map(d => ({
    label: d.time.slice(0, 10),
    value: d.value,
  }))

  return (
    <div className="border border-[color:var(--rule-thin)] overflow-hidden">
      <div
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && toggle()}
        className="flex items-center justify-between px-4 py-3 cursor-pointer bg-[color:var(--paper-2)] hover:bg-[color:var(--card-2)] select-none"
      >
        <span className="text-sm font-medium text-[color:var(--ink-2)]">
          Macro Indices
        </span>
        <span className="text-[color:var(--ink-3)] text-xs">{collapsed ? '▸' : '▾'}</span>
      </div>

      {!collapsed && (
        <div className="p-4 space-y-4 bg-[color:var(--card)]">
          <AreaChart data={indexData} series={indexSeries} showLegend height={200} />
          {(firstFbxPoint || firstWciPoint) && (
            <p className="text-xs text-[color:var(--ink-4)]">
              Rebased to 100{originDate ? ` at ${originDate}` : ''} · origin:
              {firstFbxPoint ? ` freight ≈ ${firstFbx.toFixed(2)}` : ''}
              {firstFbxPoint && firstWciPoint ? ',' : ''}
              {firstWciPoint ? ` ocean ≈ ${firstWci.toFixed(2)}` : ''}
            </p>
          )}
          <div>
            <p className="text-xs text-[color:var(--ink-3)] mb-1">Bunker price</p>
            <AreaChart data={bunkerData} series={bunkerSeries} height={80} showLegend={false} />
          </div>
        </div>
      )}
    </div>
  )
}
