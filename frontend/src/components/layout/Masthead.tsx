import React, { useMemo } from 'react'

function formatDate(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export default function Masthead() {
  const dateLabel = useMemo(() => formatDate(new Date()), [])

  return (
    <header className="masthead grid grid-cols-1 items-end gap-5 pb-5 md:grid-cols-[1fr_auto_1fr]">
      <div className="ui text-center md:text-left">
        <p className="label-cap">Pacific Edition</p>
        <p className="mt-1 text-sm text-[color:var(--ink-2)]">{dateLabel}</p>
      </div>

      <div className="text-center">
        <p className="label-cap">The Daily</p>
        <h1 className="serif mt-1 text-5xl font-semibold leading-none text-[color:var(--ink)] md:text-7xl">
          SupplyTracker
        </h1>
      </div>

      <div className="ui text-center md:text-right">
        <p className="label-cap">Live Desk</p>
        <p className="mt-1 inline-flex items-center justify-center gap-2 text-sm text-[color:var(--ink-2)] md:justify-end">
          <span className="h-2 w-2 rounded-full bg-[color:var(--positive)]" />
          Monitoring global flows
        </p>
      </div>
    </header>
  )
}
