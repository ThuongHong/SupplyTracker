import React from 'react'

export type Severity = 'low' | 'moderate' | 'high' | 'critical'
export type BadgeVariant = Severity | 'default' | 'info'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  info: 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
  // Severity variants — WCAG AA contrast checked
  low: 'bg-green-50 dark:bg-green-900/40 text-green-700 dark:text-green-400',
  moderate: 'bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
  high: 'bg-orange-50 dark:bg-orange-900/40 text-orange-700 dark:text-orange-400',
  critical: 'bg-red-50 dark:bg-red-900/40 text-red-700 dark:text-red-400',
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5',
        'text-xs font-medium',
        variantClasses[variant],
        className,
      ].join(' ')}
    >
      {children}
    </span>
  )
}

/** Convenience: render a severity value as a labeled badge */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const labels: Record<Severity, string> = {
    low: 'Low',
    moderate: 'Moderate',
    high: 'High',
    critical: 'Critical',
  }
  return <Badge variant={severity}>{labels[severity]}</Badge>
}
