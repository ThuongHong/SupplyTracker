import React from 'react'
import { InfoTooltip } from './ui/InfoTooltip'

/** ⓘ tooltip explaining how the composite risk score is computed. */
export function RiskScoreInfo() {
  return (
    <InfoTooltip label="How this risk score is computed">
      <span className="block font-semibold text-[color:var(--ink-2)]">
        How this risk score is computed
      </span>
      <span className="mt-1 block">
        Each signal is turned into a robust z-score (median &amp; MAD) versus its own
        30-day baseline, clipped to ±3 and mapped to 0–1. Signals are then combined
        as a weighted average.
      </span>
      <span className="mt-1 block">
        Signals: throughput &amp; trade volumes (PortWatch), recent news pressure, and
        a global freight-index stress overlay. Higher = more disruption risk.
      </span>
      <span className="mt-1 block mono">
        0–0.3 low · 0.3–0.6 elevated · 0.6–0.8 high · ≥0.8 critical
      </span>
    </InfoTooltip>
  )
}
