/**
 * Unit tests for PortDetail drivers/components math helpers.
 */
import { describe, it, expect } from 'vitest'

// ─── Replicate the drivers bar-chart math from PortDetailView ─────────────────

function computeBarWidths(components: Record<string, number>): Record<string, number> {
  const keys = Object.keys(components)
  if (!keys.length) return {}
  const maxVal = Math.max(...Object.values(components))
  const result: Record<string, number> = {}
  for (const k of keys) {
    result[k] = maxVal > 0 ? (components[k] / maxVal) * 100 : 0
  }
  return result
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('computeBarWidths', () => {
  it('returns empty object for empty input', () => {
    expect(computeBarWidths({})).toEqual({})
  })

  it('the highest value always gets 100%', () => {
    const comps = { congestion: 0.8, delay: 0.4, weather: 0.2 }
    const widths = computeBarWidths(comps)
    expect(widths['congestion']).toBeCloseTo(100, 1)
  })

  it('other values scale proportionally', () => {
    const comps = { a: 1.0, b: 0.5, c: 0.25 }
    const widths = computeBarWidths(comps)
    expect(widths['a']).toBeCloseTo(100, 1)
    expect(widths['b']).toBeCloseTo(50, 1)
    expect(widths['c']).toBeCloseTo(25, 1)
  })

  it('all zeros → all 0%', () => {
    const comps = { a: 0, b: 0 }
    const widths = computeBarWidths(comps)
    expect(widths['a']).toBe(0)
    expect(widths['b']).toBe(0)
  })

  it('single entry → 100%', () => {
    const widths = computeBarWidths({ only: 42 })
    expect(widths['only']).toBeCloseTo(100, 1)
  })

  it('negative values handled (max still governs scale)', () => {
    // Negative component scores shouldn't crash
    const comps = { a: -0.1, b: 0.5 }
    const widths = computeBarWidths(comps)
    expect(widths['b']).toBeCloseTo(100, 1)
    // a is negative so its pct is negative (no clamp in helper — just verify no throw)
    expect(typeof widths['a']).toBe('number')
  })
})

describe('baseline band computation (proxy ±10%)', () => {
  function computeBandForValue(value: number): { lower: number; upper: number } {
    return { lower: value * 0.9, upper: value * 1.1 }
  }

  it('upper is 10% above value', () => {
    const { upper } = computeBandForValue(1.0)
    expect(upper).toBeCloseTo(1.1, 5)
  })

  it('lower is 10% below value', () => {
    const { lower } = computeBandForValue(1.0)
    expect(lower).toBeCloseTo(0.9, 5)
  })

  it('works with zero value', () => {
    const { lower, upper } = computeBandForValue(0)
    expect(lower).toBe(0)
    expect(upper).toBe(0)
  })
})
