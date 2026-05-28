import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

interface Props {
  data: Array<{ time: string; value: number }>
}

const series = [
  { key: 'value', name: 'Vessel count', color: '#6366f1', fillOpacity: 0.2 },
]

export function VesselCountChart({ data }: Props) {
  if (data.length === 0) {
    return <DataState status="empty" emptyMessage="No vessel count data" />
  }

  const chartData = data.map(d => ({
    label: d.time.slice(0, 10),
    value: d.value,
  }))

  return <AreaChart data={chartData} series={series} />
}
