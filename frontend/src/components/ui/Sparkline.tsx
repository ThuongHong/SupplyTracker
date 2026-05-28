import React, { useMemo } from 'react'

interface SparklineProps {
  /** Array of numeric data points */
  data: number[]
  width?: number
  height?: number
  /** Stroke color — defaults to indigo */
  color?: string
  className?: string
}

/**
 * Tiny inline SVG line chart — no axes, no labels.
 * Renders purely via SVG path for minimal bundle size.
 */
export function Sparkline({
  data,
  width = 80,
  height = 28,
  color = '#6366f1',
  className = '',
}: SparklineProps) {
  const path = useMemo(() => {
    if (!data.length) return ''
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1

    const xs = data.map((_, i) => (i / (data.length - 1)) * width)
    const ys = data.map((v) => height - ((v - min) / range) * (height - 4) - 2)

    const points = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[i].toFixed(1)}`)
    return points.join(' ')
  }, [data, width, height])

  if (!data.length) return null

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden="true"
      role="img"
    >
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
