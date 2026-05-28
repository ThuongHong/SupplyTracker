import React, { useState } from 'react'
import { getSyncToken, triggerSync } from '../api/sync'

export function SyncButton() {
  const [disabled, setDisabled] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [isError, setIsError] = useState(false)

  // Hidden when no sync token configured
  if (!getSyncToken()) return null

  const handleClick = async () => {
    if (disabled) return
    setDisabled(true)
    setStatus(null)
    try {
      const res = await triggerSync('all')
      setStatus(`Sync started (${res.task_id.slice(0, 8)})`)
      setIsError(false)
      setTimeout(() => setDisabled(false), 30_000)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Sync failed'
      setStatus(msg)
      setIsError(true)
      setDisabled(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleClick}
        disabled={disabled}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium transition-colors hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Sync
      </button>
      {status && (
        <span className={`text-xs ${isError ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
          {status}
        </span>
      )}
    </div>
  )
}
