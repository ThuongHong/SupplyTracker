import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

interface Props {
  data: Array<{ time: string; anchored: number; moored: number; underway: number }>
}

const series = [
  { key: 'anchored', name: 'Anchored', color: '#f97316', fillOpacity: 0.5 },
  { key: 'moored', name: 'Moored', color: '#6366f1', fillOpacity: 0.5 },
  { key: 'underway', name: 'Underway', color: '#22c55e', fillOpacity: 0.5 },
]

export function VesselMixChart({ data }: Props) {
  if (data.length === 0) {
    return <DataState status="empty" emptyMessage="No vessel data" />
  }

  const chartData = data.map(d => ({
    label: d.time.slice(0, 10),
    anchored: d.anchored,
    moored: d.moored,
    underway: d.underway,
    value: 0,
  }))

  return <AreaChart data={chartData} series={series} showLegend />
}
