import React from 'react'

export type DataStatus = 'loading' | 'error' | 'empty' | 'success'

interface DataStateProps {
  status: DataStatus
  /** Error message shown when status='error' */
  error?: string
  /** Custom empty message */
  emptyMessage?: string
  /** Optional retry callback shown on error */
  onRetry?: () => void
  /** Rendered when status='success' */
  children?: React.ReactNode
  className?: string
}

export function DataState({
  status,
  error,
  emptyMessage = 'No data available',
  onRetry,
  children,
  className = '',
}: DataStateProps) {
  if (status === 'success') {
    return <>{children}</>
  }

  return (
    <div
      className={[
        'flex flex-col items-center justify-center py-12 px-4 text-center',
        className,
      ].join(' ')}
      role={status === 'error' ? 'alert' : undefined}
      aria-live={status === 'loading' ? 'polite' : undefined}
    >
      {status === 'loading' && <LoadingSpinner />}
      {status === 'error' && <ErrorState message={error} onRetry={onRetry} />}
      {status === 'empty' && <EmptyState message={emptyMessage} />}
    </div>
  )
}

function LoadingSpinner() {
  return (
    <>
      <span className="spinner h-8 w-8 mb-3" aria-hidden="true" />
      <p className="text-sm text-[color:var(--ink-3)]">Loading…</p>
    </>
  )
}

function ErrorState({
  message,
  onRetry,
}: {
  message?: string
  onRetry?: () => void
}) {
  return (
    <>
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-[color:var(--card)] mb-3">
        <svg
          className="h-6 w-6 text-[color:var(--negative)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          />
        </svg>
      </div>
      <p className="text-sm font-medium text-[color:var(--ink)] mb-1">
        Something went wrong
      </p>
      {message && (
        <p className="text-sm text-[color:var(--ink-3)] mb-3 max-w-xs">{message}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-[color:var(--accent)] hover:underline focus-ring"
        >
          Try again
        </button>
      )}
    </>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <>
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-[color:var(--paper-2)] mb-3">
        <svg
          className="h-6 w-6 text-[color:var(--ink-4)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
          />
        </svg>
      </div>
      <p className="text-sm text-[color:var(--ink-3)]">{message}</p>
    </>
  )
}
