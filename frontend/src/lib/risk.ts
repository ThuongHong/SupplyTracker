export type Severity = 'low' | 'elevated' | 'high' | 'critical' | 'unknown'
export type TrendDir = 'rising' | 'falling' | 'flat' | 'unknown'

/** Map a [0,1] risk score to a severity band (mirrors backend thresholds). */
export function riskSeverity(score?: number | null): Severity {
  if (score == null) return 'unknown'
  if (score < 0.3) return 'low'
  if (score < 0.6) return 'elevated'
  if (score < 0.8) return 'high'
  return 'critical'
}

/** Direction of the risk score over a history window (first → last). */
export function computeRiskTrend(
  values: number[],
  eps = 0.03,
): { direction: TrendDir; delta: number | null } {
  if (values.length < 2) return { direction: 'unknown', delta: null }
  const delta = values[values.length - 1] - values[0]
  const direction: TrendDir =
    delta > eps ? 'rising' : delta < -eps ? 'falling' : 'flat'
  return { direction, delta }
}

/** Tailwind text color for a severity band. */
export function severityTextClass(sev: Severity): string {
  switch (sev) {
    case 'low':
      return 'text-emerald-600 dark:text-emerald-400'
    case 'elevated':
      return 'text-amber-600 dark:text-amber-400'
    case 'high':
      return 'text-orange-600 dark:text-orange-400'
    case 'critical':
      return 'text-red-600 dark:text-red-400'
    default:
      return 'text-gray-500 dark:text-gray-400'
  }
}

/** Arrow glyph + color for a risk trend (rising risk is bad → red). */
export function trendDisplay(dir: TrendDir): { arrow: string; cls: string } {
  switch (dir) {
    case 'rising':
      return { arrow: '↑', cls: 'text-red-600 dark:text-red-400' }
    case 'falling':
      return { arrow: '↓', cls: 'text-emerald-600 dark:text-emerald-400' }
    case 'flat':
      return { arrow: '→', cls: 'text-gray-500 dark:text-gray-400' }
    default:
      return { arrow: '—', cls: 'text-gray-400 dark:text-gray-500' }
  }
}
