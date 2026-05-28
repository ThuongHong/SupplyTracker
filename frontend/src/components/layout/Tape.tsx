import React, { useEffect, useMemo, useState } from 'react'
import { fetchIndices } from '../../api/indices'
import type { IndexSummary } from '../../api/types'

const FALLBACK_ITEMS: IndexSummary[] = [
  { index_name: 'BDI', latest_value: 1842, change_pct_7d: 2.4, change_pct_30d: 6.8, unit: 'pts' },
  { index_name: 'FBX', latest_value: 2391, change_pct_7d: -1.2, change_pct_30d: 4.1, unit: 'USD' },
  { index_name: 'WCI', latest_value: 1755, change_pct_7d: 0.8, change_pct_30d: -3.6, unit: 'USD' },
]

function formatValue(value: number, unit?: string) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}${unit ? ` ${unit}` : ''}`
}

function TapeItem({ item }: { item: IndexSummary }) {
  const positive = item.change_pct_7d >= 0
  return (
    <span className="inline-flex items-center gap-2 px-5 py-2 mono text-[0.72rem] uppercase">
      <strong className="font-semibold text-[color:var(--paper)]">{item.index_name}</strong>
      <span className="text-[color:var(--ink-4)]">{formatValue(item.latest_value, item.unit)}</span>
      <span style={{ color: positive ? 'var(--positive)' : 'var(--negative)' }}>
        {positive ? '+' : ''}{item.change_pct_7d.toFixed(1)}%
      </span>
    </span>
  )
}

export default function Tape() {
  const [items, setItems] = useState<IndexSummary[]>(FALLBACK_ITEMS)

  useEffect(() => {
    let cancelled = false
    fetchIndices()
      .then((res) => {
        if (!cancelled && res.items.length) setItems(res.items)
      })
      .catch(() => {
        if (!cancelled) setItems(FALLBACK_ITEMS)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loop = useMemo(() => [...items, ...items, ...items], [items])

  return (
    <div className="tape" aria-label="Market tape">
      <div className="tape-track">
        {loop.map((item, index) => (
          <TapeItem key={`${item.index_name}-${index}`} item={item} />
        ))}
      </div>
    </div>
  )
}
