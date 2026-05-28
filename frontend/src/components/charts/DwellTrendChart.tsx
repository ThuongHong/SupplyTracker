import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

interface Props {
  data: Array<{ time: string; value: number }>
}

const series = [
  { key: 'value', name: 'Avg dwell (hrs)', color: '#8b5cf6', fillOpacity: 0.2 },
]

export function DwellTrendChart({ data }: Props) {
  if (data.length === 0) {
    return <DataState status="empty" emptyMessage="No dwell data" />
  }

  const chartData = data.map(d => ({
    label: d.time.slice(0, 10),
    value: d.value,
  }))

  return <AreaChart data={chartData} series={series} />
}
