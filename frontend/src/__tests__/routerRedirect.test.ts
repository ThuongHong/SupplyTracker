/**
 * Tests for route redirect logic in src/router.ts.
 * Specifically covers legacy-hash redirects and unknown-path fallback.
 *
 * These supplement the existing router.test.ts with more redirect-focused cases.
 */
import { describe, it, expect } from 'vitest'
import { parseHash } from '../router'

const LEGACY_HASHES = [
  '#/dashboard',
  '#/indices',
  '#/map',
  '#/analytics',
  '#/insights',
  '#/vessels',
]

describe('legacy hash redirects', () => {
  it.each(LEGACY_HASHES)('"%s" redirects to overview', (hash) => {
    expect(parseHash(hash)).toEqual({ name: 'overview' })
  })

  it('redirects #/dashboard even with a query string', () => {
    // Query strings after legacy paths should still redirect
    expect(parseHash('#/dashboard?foo=bar')).toEqual({ name: 'overview' })
  })
})

describe('unknown-path fallback', () => {
  it('returns overview for completely unknown paths', () => {
    expect(parseHash('#/some-unknown-path')).toEqual({ name: 'overview' })
  })

  it('returns overview for deeply nested unknown paths', () => {
    expect(parseHash('#/a/b/c/d')).toEqual({ name: 'overview' })
  })
})

describe('valid route parsing (regression)', () => {
  it('parses #/overview', () => {
    expect(parseHash('#/overview')).toEqual({ name: 'overview' })
  })

  it('parses #/ports', () => {
    expect(parseHash('#/ports')).toEqual({ name: 'ports' })
  })

  it('parses #/ports/{id} with special chars', () => {
    expect(parseHash('#/ports/NEW%20YORK')).toEqual({
      name: 'ports.detail',
      id: 'NEW YORK',
    })
  })

  it('parses #/chokepoints', () => {
    expect(parseHash('#/chokepoints')).toEqual({ name: 'chokepoints' })
  })

  it('parses #/chokepoints/{id}', () => {
    expect(parseHash('#/chokepoints/malacca-strait')).toEqual({
      name: 'chokepoints.detail',
      id: 'malacca-strait',
    })
  })

  it('empty hash returns overview', () => {
    expect(parseHash('')).toEqual({ name: 'overview' })
    expect(parseHash('#')).toEqual({ name: 'overview' })
    expect(parseHash('#/')).toEqual({ name: 'overview' })
  })
})
