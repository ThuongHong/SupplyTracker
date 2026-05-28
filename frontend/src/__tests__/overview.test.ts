/**
 * Unit tests for Overview Decision Brief panel logic.
 *
 * We test the pure sorting/selection logic in isolation,
 * avoiding React rendering to keep tests fast and free of DOM side effects.
 */
import { describe, it, expect } from 'vitest'
import type { InsightItem, Severity } from '../api/types'

// ─── Replicate the Decision Brief selection logic ─────────────────────────────

function selectBriefInsights(insights: InsightItem[]): InsightItem[] {
  const critical = insights.filter((i) => i.attention_level === 'critical').slice(0, 3)
  return critical.length ? critical : insights.slice(0, 3)
}

// ─── Replicate severity comparator ────────────────────────────────────────────

const SEV_ORDER: Record<Severity, number> = {
  critical: 4,
  high: 3,
  moderate: 2,
  low: 1,
}

function compareSeverity(
  a: Severity,
  b: Severity,
  aTracked: boolean,
  bTracked: boolean,
): number {
  const sevDiff = SEV_ORDER[b] - SEV_ORDER[a]
  if (sevDiff !== 0) return sevDiff
  return (bTracked ? 1 : 0) - (aTracked ? 1 : 0)
}

function makeInsight(
  id: string,
  attention_level: Severity,
  title = '',
): InsightItem {
  return { id, title: title || id, attention_level }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Decision Brief — selectBriefInsights', () => {
  it('returns empty array for empty input', () => {
    expect(selectBriefInsights([])).toEqual([])
  })

  it('returns up to 3 critical insights when present', () => {
    const insights: InsightItem[] = [
      makeInsight('1', 'critical'),
      makeInsight('2', 'critical'),
      makeInsight('3', 'critical'),
      makeInsight('4', 'critical'),
      makeInsight('5', 'high'),
    ]
    const result = selectBriefInsights(insights)
    expect(result).toHaveLength(3)
    expect(result.every((i) => i.attention_level === 'critical')).toBe(true)
  })

  it('falls back to first 3 items when no critical insights', () => {
    const insights: InsightItem[] = [
      makeInsight('1', 'high'),
      makeInsight('2', 'high'),
      makeInsight('3', 'moderate'),
      makeInsight('4', 'low'),
    ]
    const result = selectBriefInsights(insights)
    expect(result).toHaveLength(3)
    expect(result.map((i) => i.id)).toEqual(['1', '2', '3'])
  })

  it('returns fewer than 3 items when list is short', () => {
    const insights: InsightItem[] = [
      makeInsight('1', 'high'),
    ]
    expect(selectBriefInsights(insights)).toHaveLength(1)
  })

  it('prefers critical even if there is only one', () => {
    const insights: InsightItem[] = [
      makeInsight('a', 'high'),
      makeInsight('b', 'critical'),
      makeInsight('c', 'moderate'),
    ]
    const result = selectBriefInsights(insights)
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('b')
  })
})

describe('Severity comparator for top-5 ports', () => {
  it('orders critical before high', () => {
    expect(compareSeverity('critical', 'high', false, false)).toBeLessThan(0)
    expect(compareSeverity('high', 'critical', false, false)).toBeGreaterThan(0)
  })

  it('all severity levels ordered correctly', () => {
    const sevs: Severity[] = ['low', 'moderate', 'high', 'critical']
    const sorted = [...sevs].sort((a, b) => compareSeverity(a, b, false, false))
    expect(sorted).toEqual(['critical', 'high', 'moderate', 'low'])
  })

  it('tracked entity wins tie-break', () => {
    // Same severity; tracked should come before untracked
    const result = compareSeverity('high', 'high', false, true)
    expect(result).toBeGreaterThan(0) // b (tracked) sorts first → comparator returns positive
  })

  it('equal severity and equal tracked status returns 0', () => {
    expect(compareSeverity('moderate', 'moderate', false, false)).toBe(0)
    expect(compareSeverity('moderate', 'moderate', true, true)).toBe(0)
  })
})
