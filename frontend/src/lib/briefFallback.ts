export interface FallbackInputs {
  topRiskTitle: string | null
  bdiChangePct7d: number | null
  congestedPorts: number
}

/**
 * Deterministic markdown brief built from live Overview metrics.
 * Used when the LLM brief endpoint fails.
 */
export function buildFallbackBrief({
  topRiskTitle,
  bdiChangePct7d,
  congestedPorts,
}: FallbackInputs): string {
  if (!topRiskTitle && bdiChangePct7d == null && congestedPorts === 0) {
    return 'Global supply chain risk opens **steady**, with no critical watchpoints across ports and arteries this session.'
  }

  const parts: string[] = []
  if (topRiskTitle) parts.push(`Lead signal: **${topRiskTitle}**.`)
  if (bdiChangePct7d != null) {
    const direction = bdiChangePct7d >= 0 ? 'firms' : 'softens'
    parts.push(`Freight tape ${direction} ${Math.abs(bdiChangePct7d).toFixed(1)}% over 7 days.`)
  }
  parts.push(`${congestedPorts} port${congestedPorts === 1 ? '' : 's'} under congestion watch.`)
  return parts.join(' ')
}
