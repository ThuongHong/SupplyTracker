import React from 'react'
import type { Severity } from './Badge'

interface StatusDotProps {
  severity: Severity | 'unknown'
  size?: 'sm' | 'md' | 'lg'
  pulse?: boolean
  label?: string
  className?: string
}

const colorClasses: Record<Severity | 'unknown', string> = {
  low: 'bg-green-500 dark:bg-green-400',
  moderate: 'bg-amber-500 dark:bg-amber-400',
  high: 'bg-orange-500 dark:bg-orange-400',
  critical: 'bg-red-500 dark:bg-red-400',
  unknown: 'bg-gray-400 dark:bg-gray-500',
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
  const color = colorClasses[severity]
  const sz = sizeClasses[size]

  return (
    <span
      className={['relative inline-flex items-center justify-center', className].join(' ')}
      aria-label={label ?? severity}
      title={label ?? severity}
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
