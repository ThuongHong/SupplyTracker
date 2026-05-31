import React from 'react'

export type Severity = 'low' | 'moderate' | 'elevated' | 'high' | 'critical' | 'unknown'
export type BadgeVariant = Severity | 'default' | 'info'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClass: Record<BadgeVariant, string> = {
  default: 'pill--default',
  info: 'pill--info',
  low: 'pill--low',
  elevated: 'pill--elevated',
  moderate: 'pill--moderate',
  high: 'pill--high',
  critical: 'pill--critical',
  unknown: 'pill--unknown',
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return <span className={['pill', variantClass[variant], className].join(' ')}>{children}</span>
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
