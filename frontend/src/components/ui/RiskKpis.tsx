import React from 'react'
import { RiskScoreInfo } from '../RiskScoreInfo'
import { InfoTooltip } from './InfoTooltip'
import {
  riskSeverity,
  computeRiskTrend,
  severityTextClass,
  trendDisplay,
  type Severity,
} from '../../lib/risk'

export function KpiCard({
  label,
  info,
  children,
}: {
  label: string
  info?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3">
      <p className="flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400">
        {label}
        {info}
      </p>
      <p className="mt-1">{children}</p>
    </div>
  )
}

function RiskTrendInfo() {
  return (
    <InfoTooltip label="How the risk trend is computed">
      <span className="block font-semibold text-gray-700 dark:text-gray-200">
        Risk trend
      </span>
      <span className="mt-1 block">
        Direction of the composite risk score across the selected window — the
        latest daily snapshot versus the first. The number is the change in score.
      </span>
      <span className="mt-1 block mono">
        ↑ rising (more risk) · ↓ falling (less risk) · → flat · — too little history
      </span>
    </InfoTooltip>
  )
}

/** Risk score with its severity band folded in (color + label). */
export function RiskScoreKpi({ score }: { score?: number | null }) {
  const severity: Severity = riskSeverity(score)
  return (
    <KpiCard label="Risk Score" info={<RiskScoreInfo />}>
      <span className={`text-xl font-bold ${severityTextClass(severity)}`}>
        {score != null ? score.toFixed(2) : '—'}
      </span>
      <span className={`ml-2 text-xs font-semibold uppercase ${severityTextClass(severity)}`}>
        {severity}
      </span>
    </KpiCard>
  )
}

/** Risk trend over the window (rising risk is bad → red). */
export function TrendKpi({ riskSeries }: { riskSeries: number[] }) {
  const trend = computeRiskTrend(riskSeries)
  const { arrow, cls } = trendDisplay(trend.direction)
  const delta =
    trend.delta != null ? `${trend.delta >= 0 ? '+' : ''}${trend.delta.toFixed(2)}` : ''
  return (
    <KpiCard label="Risk Trend" info={<RiskTrendInfo />}>
      <span className={`text-xl font-bold ${cls}`}>
        {arrow} {trend.direction === 'unknown' ? '' : delta}
      </span>
    </KpiCard>
  )
}

export function SimpleKpi({ label, value }: { label: string; value: string }) {
  return (
    <KpiCard label={label}>
      <span className="text-xl font-bold text-gray-900 dark:text-gray-100">{value}</span>
    </KpiCard>
  )
}
