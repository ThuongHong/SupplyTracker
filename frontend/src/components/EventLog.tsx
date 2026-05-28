import React, { useState, useEffect } from 'react'
import { SeverityBadge } from './ui/Badge'
import { DataState } from './ui/DataState'
import { fetchStory } from '../api/story'
import { fetchEntityNews } from '../api/news'
import type { StoryEvent, NewsItem } from '../api/types'

interface EventLogProps {
  entityType: string
  entityId: string
}

type Tab = 'system' | 'news'

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

export function EventLog({ entityType, entityId }: EventLogProps) {
  const [tab, setTab] = useState<Tab>('system')
  const [newsActivated, setNewsActivated] = useState(false)

  // System events state
  const [events, setEvents] = useState<StoryEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(true)
  const [eventsError, setEventsError] = useState<string | null>(null)

  // News state
  const [news, setNews] = useState<NewsItem[]>([])
  const [newsLoading, setNewsLoading] = useState(false)
  const [newsError, setNewsError] = useState<string | null>(null)

  // Fetch system events on mount
  useEffect(() => {
    let cancelled = false
    setEventsLoading(true)
    setEventsError(null)
    fetchStory()
      .then((res) => {
        if (cancelled) return
        const filtered = res.events.filter((e) => !e.entity_id || e.entity_id === entityId)
        setEvents(filtered)
        setEventsLoading(false)
      })
      .catch((e: Error) => {
        if (cancelled) return
        setEventsError(e.message)
        setEventsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entityId])

  const loadNews = () => {
    setNewsLoading(true)
    setNewsError(null)
    fetchEntityNews(entityType, entityId)
      .then((res) => {
        setNews(res.items)
        setNewsLoading(false)
      })
      .catch((e: Error) => {
        setNewsError(e.message)
        setNewsLoading(false)
      })
  }

  const handleTabClick = (t: Tab) => {
    setTab(t)
    if (t === 'news' && !newsActivated) {
      setNewsActivated(true)
      loadNews()
    }
  }

  const handleRetryNews = () => {
    loadNews()
  }

  return (
    <div>
      {/* Tab bar */}
      <div className="flex gap-0 mb-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => handleTabClick('system')}
          className={[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors focus:outline-none',
            tab === 'system'
              ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
          ].join(' ')}
        >
          System events
        </button>
        <button
          onClick={() => handleTabClick('news')}
          className={[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors focus:outline-none',
            tab === 'news'
              ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
          ].join(' ')}
        >
          News
        </button>
      </div>

      {/* System events tab */}
      {tab === 'system' && (
        <>
          {eventsLoading && <DataState status="loading" />}
          {!eventsLoading && eventsError && <DataState status="error" error={eventsError} />}
          {!eventsLoading && !eventsError && events.length === 0 && (
            <DataState status="empty" emptyMessage="No events recorded" />
          )}
          {!eventsLoading && !eventsError && events.length > 0 && (
            <div className="space-y-3">
              {events.map((ev) => (
                <div
                  key={ev.id}
                  className="flex gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-100 dark:border-gray-700"
                >
                  <div className="flex-shrink-0 mt-0.5">
                    <SeverityBadge severity={ev.severity} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{ev.title}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-0.5">{ev.narrative}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {ev.timestamp ? ev.timestamp.slice(0, 16).replace('T', ' ') : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* News tab */}
      {tab === 'news' && (
        <>
          {newsLoading && <DataState status="loading" />}
          {!newsLoading && newsError && (
            <DataState status="error" error={newsError} onRetry={handleRetryNews} />
          )}
          {!newsLoading && !newsError && news.length === 0 && (
            <DataState status="empty" emptyMessage="No news available" />
          )}
          {!newsLoading && !newsError && news.length > 0 && (
            <div className="space-y-3">
              {news.map((item) => (
                <div
                  key={item.id}
                  className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-100 dark:border-gray-700"
                >
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline line-clamp-2"
                  >
                    {item.title}
                  </a>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-500 dark:text-gray-400">{item.source}</span>
                    <span className="text-xs text-gray-300 dark:text-gray-600">·</span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {relativeTime(item.published_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
