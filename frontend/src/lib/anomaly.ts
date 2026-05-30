import type { AnomalyStats } from '../api/types'

const MIN_BASELINE = 8

/** Abramowitz-Stegun 7.1.26 erf approximation (max error ~1.5e-7). */
function erf(x: number): number {
  const sign = x < 0 ? -1 : 1
  const ax = Math.abs(x)
  const t = 1 / (1 + 0.3275911 * ax)
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp(-ax * ax)
  return sign * y
}

function normCdf(x: number): number {
  return 0.5 * (1 + erf(x / Math.SQRT2))
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length
}

/** Sample standard deviation (n-1). */
function sampleStd(xs: number[]): number {
  const m = mean(xs)
  const variance = xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1)
  return Math.sqrt(variance)
}

const round = (v: number, d: number) => {
  const f = 10 ** d
  return Math.round(v * f) / f
}

/**
 * Z-score hypothesis test of the latest value against its trailing baseline.
 * Mirrors the backend `_anomaly_stats`: latest excluded from baseline, sample
 * std, ±1.5σ/±2.5σ level thresholds. Returns null fields when history is too
 * short or the baseline has zero variance.
 */
export function computeAnomaly(values: number[], metric?: string): AnomalyStats {
  if (values.length < MIN_BASELINE + 1) {
    return { metric: metric ?? null, baseline_n: Math.max(values.length - 1, 0) }
  }

  const latest = values[values.length - 1]
  const baseline = values.slice(0, -1)
  const m = mean(baseline)
  const std = sampleStd(baseline)

  if (std <= 0) {
    return {
      metric: metric ?? null,
      latest: round(latest, 2),
      mean: round(m, 2),
      std: 0,
      baseline_n: baseline.length,
      anomaly_level: 'low',
    }
  }

  const z = (latest - m) / std
  const p = 2 * (1 - normCdf(Math.abs(z)))
  const az = Math.abs(z)
  const level = az >= 2.5 ? 'high' : az >= 1.5 ? 'elevated' : 'low'

  return {
    metric: metric ?? null,
    latest: round(latest, 2),
    mean: round(m, 2),
    std: round(std, 4),
    z_score: round(z, 3),
    p_value: round(p, 4),
    anomaly_level: level,
    baseline_n: baseline.length,
  }
}
