import { apiGet } from './client'
import type { IndicesResponse, IndexTimeseries } from './types'

export function fetchIndices(): Promise<IndicesResponse> {
  return apiGet<IndicesResponse>('/api/v1/indices')
}

export function fetchIndexTimeseries(name: string): Promise<IndexTimeseries> {
  return apiGet<IndexTimeseries>(
    `/api/v1/indices/${encodeURIComponent(name)}/timeseries`,
  )
}
