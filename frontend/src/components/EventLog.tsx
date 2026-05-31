import React, { useState, useEffect } from 'react'
import { DataState } from './ui/DataState'
import { fetchEntityNews } from '../api/news'
import type { NewsItem } from '../api/types'

interface EventLogProps {
  entityType: string
  entityId: string
}

function relativeTime(isoStr: string): string {
  const now = Date.now()
  const then = new Date(isoStr).getTime()
  const diffMs = now - then
  const diffSecs = Math.floor(diffMs / 1000)
  if (diffSecs < 60) return 'just now'
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  const diffMonths = Math.floor(diffDays / 30)
  if (diffMonths < 12) return `${diffMonths} month${diffMonths === 1 ? '' : 's'} ago`
  const diffYears = Math.floor(diffMonths / 12)
  return `${diffYears} year${diffYears === 1 ? '' : 's'} ago`
}

/** Relevant news for one entity. */
export function EventLog({ entityType, entityId }: EventLogProps) {
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadNews = () => {
    setLoading(true)
    setError(null)
    fetchEntityNews(entityType, entityId)
      .then((res) => {
        setNews(res.items)
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchEntityNews(entityType, entityId)
      .then((res) => {
        if (cancelled) return
        setNews(res.items)
        setLoading(false)
      })
      .catch((e: Error) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entityType, entityId])

  if (loading) return <DataState status="loading" />
  if (error) return <DataState status="error" error={error} onRetry={loadNews} />
  if (news.length === 0) {
    return <DataState status="empty" emptyMessage="No news available" />
  }

  return (
    <div className="space-y-3">
      {news.map((item) => (
        <div
          key={item.id}
          className="card--inside p-3"
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-[color:var(--accent)] hover:underline line-clamp-2"
          >
            {item.title}
          </a>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-[color:var(--ink-3)]">{item.source}</span>
            <span className="text-xs text-[color:var(--rule-thin)]">·</span>
            <span className="text-xs text-[color:var(--ink-4)]">
              {relativeTime(item.published_at)}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
