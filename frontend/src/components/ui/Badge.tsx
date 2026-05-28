import React from 'react'

export type Severity = 'low' | 'moderate' | 'elevated' | 'high' | 'critical' | 'unknown'
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
  elevated: 'bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
  moderate: 'bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
  high: 'bg-orange-50 dark:bg-orange-900/40 text-orange-700 dark:text-orange-400',
  critical: 'bg-red-50 dark:bg-red-900/40 text-red-700 dark:text-red-400',
  unknown: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
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
export function normalizeSeverity(severity: string | null | undefined): Severity {
  if (severity === 'critical' || severity === 'high' || severity === 'moderate' || severity === 'elevated' || severity === 'low') {
    return severity
  }
  return 'unknown'
}

export function SeverityBadge({ severity }: { severity: string | null | undefined }) {
  const normalized = normalizeSeverity(severity)
  const labels: Record<Severity, string> = {
    low: 'Low',
    elevated: 'Elevated',
    moderate: 'Moderate',
    high: 'High',
    critical: 'Critical',
    unknown: 'Unknown',
  }
  return <Badge variant={normalized}>{labels[normalized]}</Badge>
}
