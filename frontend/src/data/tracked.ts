/**
 * localStorage helper for tracked ports and chokepoints.
 * Provides a consistent subscribe/notify pattern across all views.
 */

const KEYS = {
  ports: 'tracked_ports',
  chokepoints: 'tracked_chokepoints',
} as const

type EntityKind = keyof typeof KEYS

function readIds(kind: EntityKind): string[] {
  try {
    const raw = localStorage.getItem(KEYS[kind])
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed as string[]
    return []
  } catch {
    return []
  }
}

function writeIds(kind: EntityKind, ids: string[]): void {
  try {
    localStorage.setItem(KEYS[kind], JSON.stringify(ids))
  } catch {
    // storage quota exceeded — silently ignore
  }
}

// ─── Subscriber registry ───────────────────────────────────────────────────

const subscribers: Map<EntityKind, Set<() => void>> = new Map([
  ['ports', new Set()],
  ['chokepoints', new Set()],
])

function notify(kind: EntityKind): void {
  subscribers.get(kind)?.forEach((cb) => cb())
}

// ─── Entity-kind helper factory ─────────────────────────────────────────────

function makeHelper(kind: EntityKind) {
  return {
    getAll(): string[] {
      return readIds(kind)
    },

    add(id: string): void {
      const ids = readIds(kind)
      if (!ids.includes(id)) {
        writeIds(kind, [...ids, id])
        notify(kind)
      }
    },

    remove(id: string): void {
      const ids = readIds(kind)
      const next = ids.filter((x) => x !== id)
      if (next.length !== ids.length) {
        writeIds(kind, next)
        notify(kind)
      }
    },

    has(id: string): boolean {
      return readIds(kind).includes(id)
    },

    subscribe(cb: () => void): () => void {
      subscribers.get(kind)!.add(cb)
      return () => {
        subscribers.get(kind)!.delete(cb)
      }
    },
  }
}

// ─── Public API ─────────────────────────────────────────────────────────────

export const tracked = {
  ports: makeHelper('ports'),
  chokepoints: makeHelper('chokepoints'),
}
