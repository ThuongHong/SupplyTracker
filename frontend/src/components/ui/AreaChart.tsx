import React from 'react'
import {
  AreaChart as RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

export interface AreaChartDataPoint {
  /** X-axis label (e.g. date string) */
  label: string
  value: number
  [key: string]: string | number
}

interface AreaChartSeries {
  key: string
  name: string
  color: string
  fillOpacity?: number
}

interface AreaChartProps {
  data: AreaChartDataPoint[]
  series?: AreaChartSeries[]
  /** X-axis data key — defaults to 'label' */
  xKey?: string
  height?: number
  className?: string
  showLegend?: boolean
  /** Stack all series into a single cumulative area (e.g. cargo-type mix). */
  stacked?: boolean
  yTickFormatter?: (value: number) => string
  tooltipFormatter?: (value: number, name: string) => [string, string]
}

const DEFAULT_SERIES: AreaChartSeries[] = [
  { key: 'value', name: 'Value', color: '#6366f1', fillOpacity: 0.15 },
]

export function AreaChart({
  data,
  series = DEFAULT_SERIES,
  xKey = 'label',
  height = 200,
  className = '',
  showLegend = false,
  stacked = false,
  yTickFormatter,
  tooltipFormatter,
}: AreaChartProps) {
  return (
    <div className={['w-full', className].join(' ')} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsAreaChart
          data={data}
          margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
        >
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={s.color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="currentColor"
            className="text-gray-200 dark:text-gray-700"
            strokeOpacity={0.6}
          />

          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11, fill: 'currentColor' }}
            className="text-gray-500 dark:text-gray-400"
            tickLine={false}
            axisLine={false}
          />

          <YAxis
            tick={{ fontSize: 11, fill: 'currentColor' }}
            className="text-gray-500 dark:text-gray-400"
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={yTickFormatter}
          />

          <Tooltip
            contentStyle={{
              borderRadius: '0.5rem',
              border: '1px solid',
              borderColor: 'rgb(229 231 235)',
              backgroundColor: 'rgb(255 255 255)',
              fontSize: 12,
            }}
            formatter={tooltipFormatter}
          />

          {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}

          {series.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stackId={stacked ? 'stack' : undefined}
              stroke={s.color}
              strokeWidth={1.5}
              fill={stacked ? s.color : `url(#grad-${s.key})`}
              fillOpacity={stacked ? (s.fillOpacity ?? 0.5) : 1}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  )
}
