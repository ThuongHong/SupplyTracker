/** Humanize a snake_case metric name: "port_calls" → "Port Calls". */
export function formatMetric(name?: string | null): string {
  if (!name) return '—'
  return name
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}
