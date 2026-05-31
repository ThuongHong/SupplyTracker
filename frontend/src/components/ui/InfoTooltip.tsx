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
        className="rounded-full text-[color:var(--ink-4)] hover:text-[color:var(--ink-2)] focus-ring"
      >
        <IconInfo className="w-3.5 h-3.5" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden w-64 border border-[color:var(--rule-thin)] bg-[color:var(--card)] p-3 text-xs font-normal leading-relaxed text-[color:var(--ink-2)] group-hover:block group-focus-within:block"
      >
        {children}
      </span>
    </span>
  )
}
