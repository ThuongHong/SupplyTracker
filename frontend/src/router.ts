/**
 * Minimal hash-based router state.
 * Parses window.location.hash into a Route object.
 */

export type Route =
  | { name: 'overview' }
  | { name: 'ports' }
  | { name: 'ports.detail'; id: string }
  | { name: 'chokepoints' }
  | { name: 'chokepoints.detail'; id: string }

/** Legacy hashes that should redirect to #/overview */
const LEGACY_HASHES = new Set([
  '#/dashboard',
  '#/indices',
  '#/map',
  '#/analytics',
  '#/insights',
  '#/vessels',
  '#/market',
])

/** Parse raw hash string (e.g. "#/ports/123") into a Route. */
export function parseHash(hash: string): Route {
  // Normalize empty / bare hashes
  if (!hash || hash === '#' || hash === '#/') {
    return { name: 'overview' }
  }

  // Legacy redirect check
  const base = hash.split('?')[0].split('#')[1] ? `#${hash.split('#')[1].split('?')[0]}` : hash
  if (LEGACY_HASHES.has(base)) {
    return { name: 'overview' }
  }

  // Strip leading '#'
  const path = hash.startsWith('#') ? hash.slice(1) : hash

  // /overview
  if (path === '/overview' || path === '/') {
    return { name: 'overview' }
  }

  // /ports/{id}
  const portsDetailMatch = path.match(/^\/ports\/(.+)$/)
  if (portsDetailMatch) {
    return { name: 'ports.detail', id: decodeURIComponent(portsDetailMatch[1]) }
  }

  // /ports
  if (path === '/ports') {
    return { name: 'ports' }
  }

  // /chokepoints/{id}
  const chokepointsDetailMatch = path.match(/^\/chokepoints\/(.+)$/)
  if (chokepointsDetailMatch) {
    return { name: 'chokepoints.detail', id: decodeURIComponent(chokepointsDetailMatch[1]) }
  }

  // /chokepoints
  if (path === '/chokepoints') {
    return { name: 'chokepoints' }
  }

  // Unknown → overview
  return { name: 'overview' }
}

/** Navigate to a new hash path */
export function navigate(path: string): void {
  window.location.hash = path
}

/** Get current route */
export function currentRoute(): Route {
  return parseHash(window.location.hash)
}
