import { apiStream, ApiError, AuthError, RateLimitError } from './client'
import type { ChatRequest, ChatChunk } from './types'

/**
 * Send a chat message and stream back chunks.
 *
 * Usage:
 *   for await (const chunk of sendChatMessage({ message: 'Hello' })) {
 *     if (chunk.type === 'text') appendText(chunk.content ?? '')
 *   }
 *
 * Re-throws AuthError and RateLimitError — callers should handle these.
 */
export async function* sendChatMessage(
  request: ChatRequest,
): AsyncGenerator<ChatChunk> {
  for await (const raw of apiStream('/api/v1/chat', request)) {
    // Attempt to coerce raw chunk to ChatChunk shape
    if (typeof raw === 'object' && raw !== null) {
      yield raw as ChatChunk
    } else if (typeof raw === 'string') {
      yield { type: 'text', content: raw }
    }
  }
}

export { ApiError, AuthError, RateLimitError }
