import { apiGet } from './client'
import type { StoryResponse } from './types'

export interface StoryParams {
  /** ISO date string — returns events since this date */
  since?: string
}

export function fetchStory(params: StoryParams = {}): Promise<StoryResponse> {
  return apiGet<StoryResponse>('/api/v1/story', params)
}
