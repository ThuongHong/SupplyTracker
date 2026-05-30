import React from 'react'
import type { MacroCorrelation } from '../api/types'

interface Props {
  items?: MacroCorrelation[]
}

const EMPTY =
  'Not enough overlapping history to correlate with macro indices yet.'

function dirColor(r: number): string {
  return r < 0
    ? 'text-rose-600 dark:text-rose-400'
    : 'text-emerald-600 dark:text-emerald-400'
}

export function MacroSensitivity({ items }: Props) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">{EMPTY}</p>
  }

  return (
    <div className="space-y-2">
      {items.map((it) => {
        const weak = it.strength === 'weak'
        return (
          <div
            key={`${it.macro}-${it.metric}-${it.lag_days}`}
            className={[
              'flex items-baseline gap-2 text-sm',
              weak ? 'opacity-50' : '',
            ].join(' ')}
          >
            <span className={`font-mono font-medium ${dirColor(it.r)}`}>
              {it.r >= 0 ? '+' : ''}
              {it.r.toFixed(2)}
            </span>
            <span className="text-gray-700 dark:text-gray-300">{it.insight}</span>
            {weak && (
              <span className="text-[10px] uppercase tracking-wide text-gray-400 dark:text-gray-500">
                weak
              </span>
            )}
          </div>
        )
      })}
      <p className="text-[11px] text-gray-400 dark:text-gray-500 pt-1">
        Exploratory lead-lag correlation; small samples can mislead. n = overlapping days.
      </p>
    </div>
  )
}
