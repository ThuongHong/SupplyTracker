import React from 'react'

export interface TabItem {
  key: string
  label: string
}

interface Props {
  tabs: TabItem[]
  active: string
  onChange: (key: string) => void
}

/** Minimal underline tab strip for detail views. */
export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div
      role="tablist"
      className="flex gap-1 border-b border-[color:var(--rule-thin)]"
    >
      {tabs.map((t) => {
        const selected = t.key === active
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={['tab focus-ring', selected ? 'tab--active' : ''].join(' ')}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}
