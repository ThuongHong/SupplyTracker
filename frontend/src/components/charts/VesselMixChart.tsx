import React from 'react'
import { AreaChart } from '../ui/AreaChart'
import { DataState } from '../ui/DataState'

/** PortWatch per-category port calls (vessel mix by cargo type). */
interface MixPoint {
  time: string
  container?: number
  dry_bulk?: number
  general_cargo?: number
  roro?: number
  tanker?: number
}

interface Props {
  data: MixPoint[]
}

const series = [
  { key: 'container', name: 'Container', color: 'var(--accent)', fillOpacity: 0.5 },
  { key: 'dry_bulk', name: 'Dry bulk', color: 'var(--caution)', fillOpacity: 0.5 },
  { key: 'tanker', name: 'Tanker', color: 'var(--negative)', fillOpacity: 0.5 },
  { key: 'general_cargo', name: 'General cargo', color: 'var(--positive)', fillOpacity: 0.5 },
  { key: 'roro', name: 'RoRo', color: 'var(--highlight)', fillOpacity: 0.5 },
]

export function VesselMixChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <DataState
        status="empty"
        emptyMessage="No vessel-type breakdown yet — re-sync this entity"
      />
    )
  }

  const chartData = data.map((d) => ({
    label: d.time.slice(0, 10),
    container: d.container ?? 0,
    dry_bulk: d.dry_bulk ?? 0,
    tanker: d.tanker ?? 0,
    general_cargo: d.general_cargo ?? 0,
    roro: d.roro ?? 0,
    value: 0,
  }))

  return <AreaChart data={chartData} series={series} stacked showLegend />
}
