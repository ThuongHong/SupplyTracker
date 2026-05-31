import React from 'react'
import { normalizeSeverity, type Severity } from './Badge'

interface StatusDotProps {
  severity: string | null | undefined
  size?: 'sm' | 'md' | 'lg'
  pulse?: boolean
  label?: string
  className?: string
}

const colorClasses: Record<Severity, string> = {
  low: 'bg-[color:var(--positive)]',
  elevated: 'bg-[color:var(--caution)]',
  moderate: 'bg-[color:var(--caution)]',
  high: 'bg-[color:var(--negative)]',
  critical: 'bg-[color:var(--negative)]',
  unknown: 'bg-[color:var(--ink-4)]',
}

const sizeClasses: Record<NonNullable<StatusDotProps['size']>, string> = {
  sm: 'w-1.5 h-1.5',
  md: 'w-2.5 h-2.5',
  lg: 'w-3.5 h-3.5',
}

export function StatusDot({
  severity,
  size = 'md',
  pulse = false,
  label,
  className = '',
}: StatusDotProps) {
  const normalized = normalizeSeverity(severity)
  const color = colorClasses[normalized]
  const sz = sizeClasses[size]
  const accessibleLabel = label ?? normalized

  return (
    <span
      className={['relative inline-flex items-center justify-center', className].join(' ')}
      aria-label={accessibleLabel}
      title={accessibleLabel}
    >
      {pulse && (
        <span
          className={[
            'absolute inline-flex rounded-full opacity-75 animate-ping',
            color,
            sz,
          ].join(' ')}
        />
      )}
      <span className={['relative inline-flex rounded-full flex-shrink-0', color, sz].join(' ')} />
    </span>
  )
}
