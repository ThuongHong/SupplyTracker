import React, { useState } from 'react'
import { AreaChart } from '../ui/AreaChart'

interface Props {
  indices: Array<{ time: string; fbx?: number; wci?: number }>
  bunker: Array<{ time: string; value: number }>
}

const indexSeries = [
  { key: 'fbx', name: 'FBX (rebased)', color: '#f97316', fillOpacity: 0.15 },
  { key: 'wci', name: 'WCI (rebased)', color: '#6366f1', fillOpacity: 0.15 },
]

const bunkerSeries = [
  { key: 'value', name: 'Bunker price', color: '#64748b', fillOpacity: 0.2 },
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

  const firstFbx = indices.find(d => d.fbx != null)?.fbx ?? 1
  const firstWci = indices.find(d => d.wci != null)?.wci ?? 1

  const rebasedData = indices.map(d => ({
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
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && toggle()}
        className="flex items-center justify-between px-4 py-3 cursor-pointer bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 select-none"
      >
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Macro Indices
        </span>
        <span className="text-gray-500 dark:text-gray-400 text-xs">{collapsed ? '▸' : '▾'}</span>
      </div>

      {!collapsed && (
        <div className="p-4 space-y-4 bg-white dark:bg-gray-900">
          <AreaChart data={rebasedData} series={indexSeries} showLegend height={200} />
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Bunker price</p>
            <AreaChart data={bunkerData} series={bunkerSeries} height={80} showLegend={false} />
          </div>
        </div>
      )}
    </div>
  )
}
