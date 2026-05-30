import React from 'react'
import { IconInfo } from './icons'

interface InfoTooltipProps {
  /** Accessible label for the trigger button. */
  label?: string
  /** Tooltip body — shown on hover/focus. */
  children: React.ReactNode
}

/** Small info (ⓘ) trigger that reveals an explanatory popover on hover/focus. */
export function InfoTooltip({ label = 'More information', children }: InfoTooltipProps) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        className="rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        <IconInfo className="w-3.5 h-3.5" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden w-64 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 text-xs font-normal leading-relaxed text-gray-600 dark:text-gray-300 shadow-lg group-hover:block group-focus-within:block"
      >
        {children}
      </span>
    </span>
  )
}
