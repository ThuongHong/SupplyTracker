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
      className="flex gap-1 border-b border-gray-200 dark:border-gray-700"
    >
      {tabs.map((t) => {
        const selected = t.key === active
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={[
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500',
              selected
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200',
            ].join(' ')}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}
