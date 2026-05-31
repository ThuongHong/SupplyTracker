import { describe, it, expect } from 'vitest'
import { buildFallbackBrief } from '../lib/briefFallback'

describe('buildFallbackBrief', () => {
  it('summarizes top risk + bdi move + congestion when data present', () => {
    const md = buildFallbackBrief({
      topRiskTitle: 'Suez transit disruption',
      bdiChangePct7d: -3.2,
      congestedPorts: 4,
    })

    expect(md).toContain('Suez transit disruption')
    expect(md).toContain('softens')
    expect(md).toContain('4')
  })

  it('falls back to a steady-state line when nothing notable', () => {
    const md = buildFallbackBrief({
      topRiskTitle: null,
      bdiChangePct7d: null,
      congestedPorts: 0,
    })

    expect(md.toLowerCase()).toContain('steady')
  })
})
