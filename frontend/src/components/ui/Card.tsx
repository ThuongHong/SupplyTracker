import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  /** Optional title rendered above content */
  title?: string
  /** Optional actions rendered in the top-right corner */
  actions?: React.ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
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
}: CardProps) {
  return (
    <div
      className={[
        'rounded-xl border border-gray-200 dark:border-gray-700',
        'bg-white dark:bg-gray-800',
        'shadow-sm',
        className,
      ].join(' ')}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          {title && (
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {title}
            </h3>
          )}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={paddingClasses[padding]}>{children}</div>
    </div>
  )
}
