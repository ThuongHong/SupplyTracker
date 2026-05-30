import { describe, it, expect } from 'vitest'
import { computeAnomaly } from '../lib/anomaly'

describe('computeAnomaly', () => {
  it('returns nulls with too little history', () => {
    const s = computeAnomaly([1, 2, 3], 'port_calls')
    expect(s.z_score == null).toBe(true)
    expect(s.metric).toBe('port_calls')
    expect(s.baseline_n).toBe(2)
  })

  it('zero-variance baseline → std 0, low, no z', () => {
    const s = computeAnomaly([50, 50, 50, 50, 50, 50, 50, 50, 50, 50])
    expect(s.std).toBe(0)
    expect(s.z_score == null).toBe(true)
    expect(s.anomaly_level).toBe('low')
  })

  it('latest far above baseline → high anomaly, positive z', () => {
    const baseline = [100, 102, 98, 101, 99, 100, 103, 97, 100]
    const s = computeAnomaly([...baseline, 140])
    expect(s.z_score).not.toBeNull()
    expect(s.z_score!).toBeGreaterThan(2.5)
    expect(s.anomaly_level).toBe('high')
    expect(s.p_value!).toBeGreaterThanOrEqual(0)
    expect(s.p_value!).toBeLessThan(0.05)
    expect(s.baseline_n).toBe(9)
    expect(s.latest).toBeCloseTo(140, 5)
  })

  it('latest within range → low', () => {
    const s = computeAnomaly([100, 102, 98, 101, 99, 100, 103, 97, 100, 100])
    expect(s.anomaly_level).toBe('low')
  })
})
