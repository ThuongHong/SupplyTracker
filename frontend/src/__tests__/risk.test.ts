import { describe, it, expect } from 'vitest'
import { riskSeverity, computeRiskTrend } from '../lib/risk'

describe('riskSeverity', () => {
  it('mirrors backend thresholds 0.3/0.6/0.8', () => {
    expect(riskSeverity(0.1)).toBe('low')
    expect(riskSeverity(0.29)).toBe('low')
    expect(riskSeverity(0.3)).toBe('elevated')
    expect(riskSeverity(0.59)).toBe('elevated')
    expect(riskSeverity(0.6)).toBe('high')
    expect(riskSeverity(0.79)).toBe('high')
    expect(riskSeverity(0.8)).toBe('critical')
  })

  it('null/undefined → unknown', () => {
    expect(riskSeverity(null)).toBe('unknown')
    expect(riskSeverity(undefined)).toBe('unknown')
  })
})

describe('computeRiskTrend', () => {
  it('rising when last clearly above first', () => {
    const t = computeRiskTrend([0.2, 0.3, 0.45])
    expect(t.direction).toBe('rising')
    expect(t.delta).toBeCloseTo(0.25, 5)
  })

  it('falling when last clearly below first', () => {
    expect(computeRiskTrend([0.6, 0.5, 0.4]).direction).toBe('falling')
  })

  it('flat within epsilon', () => {
    expect(computeRiskTrend([0.50, 0.51, 0.49]).direction).toBe('flat')
  })

  it('unknown with <2 points', () => {
    expect(computeRiskTrend([]).direction).toBe('unknown')
    expect(computeRiskTrend([0.4]).direction).toBe('unknown')
  })
})
