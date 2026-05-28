import { apiGet } from './client'
import type { StoryResponse } from './types'

export interface StoryParams {
  since?: string
}

export function fetchStory(params: StoryParams = {}): Promise<StoryResponse> {
  return apiGet<unknown>('/api/v1/story', params).then((raw) => {
    const d = raw as Record<string, unknown>
    const items = (d.items as Array<Record<string, unknown>>) ?? []
    return {
      count: (d.count as number) ?? items.length,
      events: items.map((e) => ({
        id: (e.event_key as string) ?? String(e.id ?? ''),
        title: (e.event_type as string) ?? 'Event',
        narrative: (e.narrative as string) ?? '',
        entity_type: e.entity_type as string | undefined,
        entity_id: e.entity_id as string | undefined,
        entity_name: e.entity_name as string | undefined,
        severity: (e.severity as string) ?? 'unknown',
        timestamp: (e.event_time as string) ?? (e.timestamp as string) ?? '',
      })),
    } as StoryResponse
  })
}
