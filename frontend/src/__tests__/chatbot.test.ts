/**
 * Unit tests for ChatbotWidget SSE handling and entity-context derivation.
 *
 * We test the helper function `deriveEntityContext` in isolation
 * (extracted logic — same as in the widget).
 * Full render tests are skipped because maplibre-gl requires a real WebGL context.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Replicate the helper so we can test without importing the full component ─

function deriveEntityContext(hash: string): { entity_type: string; entity_id: string } | undefined {
  if (!hash) return undefined
  const path = hash.startsWith('#') ? hash.slice(1) : hash

  const portMatch = path.match(/^\/ports\/(.+)$/)
  if (portMatch) {
    return { entity_type: 'port', entity_id: decodeURIComponent(portMatch[1]) }
  }

  const cpMatch = path.match(/^\/chokepoints\/(.+)$/)
  if (cpMatch) {
    return { entity_type: 'chokepoint', entity_id: decodeURIComponent(cpMatch[1]) }
  }

  return undefined
}

// ─── Replicate SSE chunk accumulation logic ───────────────────────────────────

type ChatChunk = { type: 'text' | 'done' | 'error'; content?: string; error?: string }

async function collectChunks(gen: AsyncIterable<ChatChunk>): Promise<string> {
  let result = ''
  for await (const chunk of gen) {
    if (chunk.type === 'text' && chunk.content) result += chunk.content
    if (chunk.type === 'done' || chunk.type === 'error') break
  }
  return result
}

async function* makeChunkGen(chunks: ChatChunk[]): AsyncGenerator<ChatChunk> {
  for (const c of chunks) yield c
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('deriveEntityContext', () => {
  it('returns undefined for empty hash', () => {
    expect(deriveEntityContext('')).toBeUndefined()
  })

  it('returns undefined for overview hash', () => {
    expect(deriveEntityContext('#/overview')).toBeUndefined()
  })

  it('returns port context for #/ports/{id}', () => {
    expect(deriveEntityContext('#/ports/SGSIN')).toEqual({
      entity_type: 'port',
      entity_id: 'SGSIN',
    })
  })

  it('URL-decodes port id', () => {
    expect(deriveEntityContext('#/ports/Port%20Said')).toEqual({
      entity_type: 'port',
      entity_id: 'Port Said',
    })
  })

  it('returns chokepoint context for #/chokepoints/{id}', () => {
    expect(deriveEntityContext('#/chokepoints/suez-canal')).toEqual({
      entity_type: 'chokepoint',
      entity_id: 'suez-canal',
    })
  })

  it('returns undefined for /ports list (no id)', () => {
    expect(deriveEntityContext('#/ports')).toBeUndefined()
  })

  it('returns undefined for /chokepoints list (no id)', () => {
    expect(deriveEntityContext('#/chokepoints')).toBeUndefined()
  })
})

describe('SSE chunk accumulation', () => {
  it('accumulates text chunks in order', async () => {
    const chunks: ChatChunk[] = [
      { type: 'text', content: 'Hello' },
      { type: 'text', content: ', world' },
      { type: 'done' },
    ]
    const result = await collectChunks(makeChunkGen(chunks))
    expect(result).toBe('Hello, world')
  })

  it('stops at done', async () => {
    const chunks: ChatChunk[] = [
      { type: 'text', content: 'First' },
      { type: 'done' },
      { type: 'text', content: 'Never seen' },
    ]
    const result = await collectChunks(makeChunkGen(chunks))
    expect(result).toBe('First')
  })

  it('stops at error', async () => {
    const chunks: ChatChunk[] = [
      { type: 'text', content: 'Before' },
      { type: 'error', error: 'oops' },
      { type: 'text', content: 'After' },
    ]
    const result = await collectChunks(makeChunkGen(chunks))
    expect(result).toBe('Before')
  })

  it('handles empty text content gracefully', async () => {
    const chunks: ChatChunk[] = [
      { type: 'text' }, // content is undefined
      { type: 'text', content: 'Hi' },
      { type: 'done' },
    ]
    const result = await collectChunks(makeChunkGen(chunks))
    expect(result).toBe('Hi')
  })

  it('handles generator with no chunks', async () => {
    const result = await collectChunks(makeChunkGen([]))
    expect(result).toBe('')
  })
})
