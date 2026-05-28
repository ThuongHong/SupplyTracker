import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import { Badge, SeverityBadge } from '../components/ui/Badge'

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Test</Badge>)
    expect(screen.getByText('Test')).toBeTruthy()
  })

  it('renders severity badges', () => {
    const severities = ['low', 'moderate', 'high', 'critical'] as const
    for (const s of severities) {
      const { unmount } = render(<SeverityBadge severity={s} />)
      expect(screen.getByText(s.charAt(0).toUpperCase() + s.slice(1))).toBeTruthy()
      unmount()
    }
  })
})

describe('StatusDot', () => {
  it('renders without crashing', async () => {
    const { StatusDot } = await import('../components/ui/StatusDot')
    render(<StatusDot severity="high" />)
  })
})
