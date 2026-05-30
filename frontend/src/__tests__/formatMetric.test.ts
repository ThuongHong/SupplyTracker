import { describe, it, expect } from 'vitest'
import { formatMetric } from '../lib/format'

describe('formatMetric', () => {
  it('underscores to spaced Title Case', () => {
    expect(formatMetric('port_calls')).toBe('Port Calls')
    expect(formatMetric('import_volume')).toBe('Import Volume')
    expect(formatMetric('transit_calls')).toBe('Transit Calls')
  })

  it('single word capitalized', () => {
    expect(formatMetric('throughput')).toBe('Throughput')
  })

  it('handles empty / nullish', () => {
    expect(formatMetric('')).toBe('—')
    expect(formatMetric(null)).toBe('—')
    expect(formatMetric(undefined)).toBe('—')
  })
})
