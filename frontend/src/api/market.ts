import { apiGet } from './client'

export interface TradeMetric {
  latest: number | null
  pct_change: number | null
  series: Array<{ time: string; value: number }>
}

export interface MarketInsights {
  window: string
  as_of: string | null
  tracked_count: number
  trade_growth: Record<string, TradeMetric>
  market: {
    indices: Array<{ time: string; fbx?: number; wci?: number }>
    bunker: Array<{ time: string; value: number }>
  }
  narrative: string
}

// In-memory cache keyed by window. The backend `as_of` lets us skip re-rendering
// when the underlying data hasn't advanced.
const _cache = new Map<string, MarketInsights>()

export function getCachedMarket(window: string): MarketInsights | null {
  return _cache.get(window) ?? null
}

export async function fetchMarketInsights(window: string): Promise<MarketInsights> {
  const data = await apiGet<MarketInsights>('/api/v1/market/insights', { window })
  _cache.set(window, data)
  return data
}
