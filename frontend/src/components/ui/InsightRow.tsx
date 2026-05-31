import React from 'react'
import { Badge, type Severity } from './Badge'
import { StatusDot } from './StatusDot'

export interface InsightItem {
  id: string
  title: string
  attention_level: Severity | string
  narrative?: string
  timestamp?: string
  entity_name?: string
}

interface InsightRowProps {
  insight: InsightItem
  onClick?: (insight: InsightItem) => void
}

function toSeverity(level: string): Severity {
  if (level === 'low' || level === 'moderate' || level === 'high' || level === 'critical') {
    return level
  }
  return 'low'
}

export function InsightRow({ insight, onClick }: InsightRowProps) {
  const severity = toSeverity(insight.attention_level)

  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={() => onClick?.(insight)}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onClick(insight)
        }
      }}
      className={[
        'flex items-start gap-3 px-4 py-3',
        'border-b border-[color:var(--rule-hair)] last:border-0',
        onClick
          ? 'cursor-pointer hover:bg-[color:var(--paper-2)] focus:outline-none focus:bg-[color:var(--paper-2)]'
          : '',
        'transition-colors duration-100',
      ].join(' ')}
    >
      {/* Severity indicator */}
      <div className="flex-shrink-0 mt-0.5">
        <StatusDot
          severity={severity}
          pulse={severity === 'critical'}
          label={severity}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-[color:var(--ink)] truncate">
            {insight.title}
          </span>
          <Badge variant={severity}>{insight.attention_level}</Badge>
          {insight.entity_name && (
            <span className="text-xs text-[color:var(--ink-3)]">
              {insight.entity_name}
            </span>
          )}
        </div>
        {insight.narrative && (
          <p className="mt-0.5 text-sm text-[color:var(--ink-2)] line-clamp-2">
            {insight.narrative}
          </p>
        )}
        {insight.timestamp && (
          <p className="mt-1 text-xs text-[color:var(--ink-4)]">
            {insight.timestamp}
          </p>
        )}
      </div>
    </div>
  )
}
