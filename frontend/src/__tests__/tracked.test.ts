/**
 * Unit tests for src/data/tracked.ts
 *
 * We mock localStorage via vi.stubGlobal so these tests work in any
 * vitest environment (node or jsdom).
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// ─── localStorage mock ────────────────────────────────────────────────────────

function makeLocalStorageMock() {
  const store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { for (const k of Object.keys(store)) delete store[k] },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
}

const localStorageMock = makeLocalStorageMock()

vi.stubGlobal('localStorage', localStorageMock)

// ─── Import the module AFTER stubbing ─────────────────────────────────────────

import { tracked } from '../data/tracked'

describe('tracked helper', () => {
  beforeEach(() => {
    localStorageMock.clear()
  })

  it('getAll returns [] when nothing stored', () => {
    expect(tracked.ports.getAll()).toEqual([])
    expect(tracked.chokepoints.getAll()).toEqual([])
  })

  it('add inserts an id and has() returns true', () => {
    tracked.ports.add('SGSIN')
    expect(tracked.ports.has('SGSIN')).toBe(true)
    expect(tracked.ports.getAll()).toContain('SGSIN')
  })

  it('add is idempotent', () => {
    tracked.ports.add('SGSIN')
    tracked.ports.add('SGSIN')
    expect(tracked.ports.getAll().filter((x) => x === 'SGSIN')).toHaveLength(1)
  })

  it('remove deletes an id', () => {
    tracked.ports.add('SGSIN')
    tracked.ports.add('MYPKG')
    tracked.ports.remove('SGSIN')
    expect(tracked.ports.has('SGSIN')).toBe(false)
    expect(tracked.ports.has('MYPKG')).toBe(true)
  })

  it('remove on non-existent id is a no-op', () => {
    expect(() => tracked.ports.remove('NONEXISTENT')).not.toThrow()
  })

  it('chokepoints helper is independent from ports', () => {
    tracked.ports.add('SGSIN')
    expect(tracked.chokepoints.has('SGSIN')).toBe(false)
  })

  it('subscribe calls callback on add', () => {
    const cb = vi.fn()
    const unsub = tracked.ports.subscribe(cb)
    tracked.ports.add('MYPKG')
    expect(cb).toHaveBeenCalledTimes(1)
    unsub()
    tracked.ports.remove('MYPKG')
  })

  it('subscribe calls callback on remove', () => {
    tracked.ports.add('MYPKG')
    const cb = vi.fn()
    const unsub = tracked.ports.subscribe(cb)
    tracked.ports.remove('MYPKG')
    expect(cb).toHaveBeenCalledTimes(1)
    unsub()
  })

  it('subscribe returns unsubscribe that stops notifications', () => {
    const cb = vi.fn()
    const unsub = tracked.ports.subscribe(cb)
    unsub()
    tracked.ports.add('MYPKG')
    expect(cb).not.toHaveBeenCalled()
    tracked.ports.remove('MYPKG')
  })

  it('add does not notify when id already present', () => {
    tracked.ports.add('SGSIN')
    const cb = vi.fn()
    const unsub = tracked.ports.subscribe(cb)
    tracked.ports.add('SGSIN') // already there — no-op
    expect(cb).not.toHaveBeenCalled()
    unsub()
  })

  it('persists to localStorage with correct key', () => {
    tracked.ports.add('PERSIST')
    const raw = localStorageMock.getItem('tracked_ports')
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw!)
    expect(parsed).toContain('PERSIST')
  })

  it('chokepoints use separate localStorage key', () => {
    tracked.chokepoints.add('suez-canal')
    const cpRaw = localStorageMock.getItem('tracked_chokepoints')
    expect(cpRaw).not.toBeNull()
    const parsed = JSON.parse(cpRaw!)
    expect(parsed).toContain('suez-canal')
    // ports key should be unaffected
    expect(localStorageMock.getItem('tracked_ports')).toBeNull()
  })

  it('multiple ids can be tracked simultaneously', () => {
    tracked.ports.add('A')
    tracked.ports.add('B')
    tracked.ports.add('C')
    const all = tracked.ports.getAll()
    expect(all).toContain('A')
    expect(all).toContain('B')
    expect(all).toContain('C')
  })
})
