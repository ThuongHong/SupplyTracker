import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

interface Props {
  riskTrend: Array<{ time: string; value: number }>
  forecast: Array<{ time: string; value: number; lo?: number; hi?: number }>
}

const series = [
  { key: 'hi', name: 'Upper band', color: '#f97316', fillOpacity: 0.15 },
  { key: 'lo', name: 'Lower band', color: '#6366f1', fillOpacity: 0.15 },
  { key: 'value', name: 'Risk score', color: '#6366f1', fillOpacity: 0 },
]

export function RiskForecastChart({ riskTrend, forecast }: Props) {
  if (riskTrend.length === 0 && forecast.length === 0) {
    return <DataState status="empty" emptyMessage="No risk data" />
  }

  const combined = [
    ...riskTrend.map(d => ({
      label: d.time.slice(0, 10),
      value: d.value,
      lo: NaN as number,
      hi: NaN as number,
    })),
    ...forecast.map(d => ({
      label: d.time.slice(0, 10),
      value: d.value,
      lo: d.lo ?? d.value,
      hi: d.hi ?? d.value,
    })),
  ]

  return <AreaChart data={combined} series={series} showLegend />
}
