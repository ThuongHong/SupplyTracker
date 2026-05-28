import { describe, it, expect } from 'vitest'
import { parseHash } from '../router'

describe('parseHash', () => {
  it('returns overview for empty hash', () => {
    expect(parseHash('')).toEqual({ name: 'overview' })
    expect(parseHash('#')).toEqual({ name: 'overview' })
    expect(parseHash('#/')).toEqual({ name: 'overview' })
  })

  it('returns overview for #/overview', () => {
    expect(parseHash('#/overview')).toEqual({ name: 'overview' })
  })

  it('returns ports for #/ports', () => {
    expect(parseHash('#/ports')).toEqual({ name: 'ports' })
  })

  it('returns ports.detail for #/ports/{id}', () => {
    expect(parseHash('#/ports/SGSIN')).toEqual({ name: 'ports.detail', id: 'SGSIN' })
  })

  it('returns chokepoints for #/chokepoints', () => {
    expect(parseHash('#/chokepoints')).toEqual({ name: 'chokepoints' })
  })

  it('returns chokepoints.detail for #/chokepoints/{id}', () => {
    expect(parseHash('#/chokepoints/suez-canal')).toEqual({
      name: 'chokepoints.detail',
      id: 'suez-canal',
    })
  })

  it('redirects legacy hashes to overview', () => {
    const legacyHashes = [
      '#/dashboard',
      '#/indices',
      '#/map',
      '#/analytics',
      '#/insights',
      '#/vessels',
    ]
    for (const hash of legacyHashes) {
      expect(parseHash(hash)).toEqual({ name: 'overview' }, `failed for ${hash}`)
    }
  })

  it('redirects unknown paths to overview', () => {
    expect(parseHash('#/unknown-route')).toEqual({ name: 'overview' })
  })

  it('URL-decodes ids', () => {
    expect(parseHash('#/ports/Port%20Said')).toEqual({
      name: 'ports.detail',
      id: 'Port Said',
    })
  })
})
