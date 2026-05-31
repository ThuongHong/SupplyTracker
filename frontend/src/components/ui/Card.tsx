import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  /** Optional title rendered above content */
  title?: string
  /** Optional actions rendered in the top-right corner */
  actions?: React.ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Flatter "inside page" variant for detail pages (hair border, transparent bg) */
  inside?: boolean
}

const paddingClasses: Record<NonNullable<CardProps['padding']>, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

export function Card({
  children,
  className = '',
  title,
  actions,
  padding = 'md',
  inside = false,
}: CardProps) {
  return (
    <div className={[inside ? 'card--inside' : 'card', className].join(' ')}>
      {(title || actions) && (
        <div className="card__head">
          {title && <h3 className="card__title">{title}</h3>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={paddingClasses[padding]}>{children}</div>
    </div>
  )
}
