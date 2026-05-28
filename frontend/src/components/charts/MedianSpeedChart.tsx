import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

interface Props {
  data: Array<{ time: string; value: number }>
}

const series = [
  { key: 'value', name: 'Median speed (kts)', color: '#22c55e', fillOpacity: 0.2 },
]

export function MedianSpeedChart({ data }: Props) {
  if (data.length === 0) {
    return <DataState status="empty" emptyMessage="No speed data" />
  }

  const chartData = data.map(d => ({
    label: d.time.slice(0, 10),
    value: d.value,
  }))

  return <AreaChart data={chartData} series={series} />
}
