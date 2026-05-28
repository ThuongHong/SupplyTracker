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
      <svg
        className="animate-spin h-8 w-8 text-indigo-500 mb-3"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
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
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-red-50 dark:bg-red-900/30 mb-3">
        <svg
          className="h-6 w-6 text-red-600 dark:text-red-400"
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
      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
        Something went wrong
      </p>
      {message && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 max-w-xs">{message}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded"
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
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 mb-3">
        <svg
          className="h-6 w-6 text-gray-400 dark:text-gray-500"
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
      <p className="text-sm text-gray-500 dark:text-gray-400">{message}</p>
    </>
  )
}
