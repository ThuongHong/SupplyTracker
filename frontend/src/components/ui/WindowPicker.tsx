import React from 'react'

export type Window = '7d' | '30d' | '90d'

interface Props {
  value: Window
  onChange: (w: Window) => void
}

export function WindowPicker({ value, onChange }: Props) {
  const options: Window[] = ['7d', '30d', '90d']
  return (
    <div className="flex gap-1 rounded-lg border border-gray-200 dark:border-gray-700 p-0.5 bg-gray-50 dark:bg-gray-800">
      {options.map(opt => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={[
            'px-3 py-1 text-sm rounded-md font-medium transition-colors',
            opt === value
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
          ].join(' ')}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
