import React, { useState, useRef, useEffect, useCallback } from 'react'
import { IconX } from './ui/icons'
import { ChatMarkdown } from './ChatMarkdown'
import { sendChatMessage } from '../api/chat'
import type { ChatRequest } from '../api/types'

// ─── Entity context derivation ───────────────────────────────────────────────

function deriveEntityContext(
  hash: string,
): ChatRequest['entity_context'] | undefined {
  if (!hash) return undefined
  const path = hash.startsWith('#') ? hash.slice(1) : hash

  const portMatch = path.match(/^\/ports\/(.+)$/)
  if (portMatch) {
    return [{ entity_type: 'port', entity_id: decodeURIComponent(portMatch[1]) }]
  }

  const cpMatch = path.match(/^\/chokepoints\/(.+)$/)
  if (cpMatch) {
    return [{ entity_type: 'chokepoint', entity_id: decodeURIComponent(cpMatch[1]) }]
  }

  return undefined
}

// ─── External API ────────────────────────────────────────────────────────────

type EntityContextItem = { entity_type: string; entity_id: string; entity_name?: string }

export function openChatWithPrompt(
  prompt: string,
  entityContext: EntityContextItem[],
): void {
  window.dispatchEvent(
    new CustomEvent('supplytracker:open-chat', { detail: { prompt, entityContext } }),
  )
}

// ─── Message types ───────────────────────────────────────────────────────────

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

// ─── ChatbotWidget ───────────────────────────────────────────────────────────

export default function ChatbotWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<boolean>(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const pendingContextRef = useRef<EntityContextItem[] | null>(null)

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus textarea when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }, [open])

  // Listen for external open-chat events
  useEffect(() => {
    const handler = (e: Event) => {
      const { prompt, entityContext } = (e as CustomEvent<{ prompt: string; entityContext: EntityContextItem[] }>).detail
      setOpen(true)
      setInput(prompt)
      pendingContextRef.current = entityContext
    }
    window.addEventListener('supplytracker:open-chat', handler)
    return () => window.removeEventListener('supplytracker:open-chat', handler)
  }, [])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || streaming) return

    const entityContext = pendingContextRef.current ?? deriveEntityContext(window.location.hash)
    pendingContextRef.current = null

    const userMsg: Message = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setError(null)
    setStreaming(true)
    abortRef.current = false

    // Add placeholder assistant message
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', streaming: true },
    ])

    try {
      const request: ChatRequest = {
        message: text,
        entity_context: entityContext ?? [],
      }

      let assembled = ''
      for await (const chunk of sendChatMessage(request)) {
        if (abortRef.current) break
        if (chunk.type === 'text' && chunk.content) {
          assembled += chunk.content
          const captured = assembled
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: captured, streaming: true }
            }
            return next
          })
        }
        if (chunk.type === 'done') break
        if (chunk.type === 'error') {
          setError(chunk.error ?? 'Unknown error from assistant')
          break
        }
      }

      // Finalize: drop an empty assistant placeholder (e.g. after an error),
      // otherwise just clear the streaming flag.
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last && last.role === 'assistant') {
          if (!last.content) return next.slice(0, -1)
          next[next.length - 1] = { ...last, streaming: false }
        }
        return next
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to send message')
      // Remove the empty assistant placeholder
      setMessages((prev) => {
        const next = [...prev]
        if (next[next.length - 1]?.role === 'assistant' && !next[next.length - 1].content) {
          return next.slice(0, -1)
        }
        return next
      })
    } finally {
      setStreaming(false)
    }
  }, [input, streaming])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-40 flex items-center justify-center w-14 h-14 rounded-full bg-[color:var(--accent)] text-white focus-ring transition-colors"
        aria-label={open ? 'Close chat assistant' : 'Open chat assistant'}
      >
        {open ? (
          <IconX className="w-6 h-6" />
        ) : (
          // Chat bubble icon
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-6 h-6"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.804 21.644A6.707 6.707 0 006 21.75a6.721 6.721 0 003.583-1.029c.774.182 1.584.279 2.417.279 5.322 0 9.75-3.97 9.75-9 0-5.03-4.428-9-9.75-9s-9.75 3.97-9.75 9c0 2.409 1.025 4.587 2.674 6.192.232.226.277.428.254.543a3.73 3.73 0 01-.814 1.686.75.75 0 00.44 1.223 3.4 3.4 0 002.25-.478z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="card fixed bottom-24 right-6 z-40 flex flex-col w-80 sm:w-96 overflow-hidden"
          style={{ maxHeight: 'calc(100vh - 120px)' }}
          role="dialog"
          aria-label="Chat assistant"
        >
          {/* Panel header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--rule-thin)] bg-[color:var(--accent)] text-white">
            <div>
              <h2 className="text-sm font-semibold">Supply Assistant</h2>
              <p className="text-xs text-white/80">Ask about ports, chokepoints, or risk</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 hover:bg-[color:color-mix(in_srgb,var(--paper)_20%,transparent)] focus-ring"
              aria-label="Close chat"
            >
              <IconX className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
            {messages.length === 0 && (
              <p className="text-sm text-[color:var(--ink-4)] text-center py-8">
                Ask me about supply chain risks, ports, or disruptions.
              </p>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={[
                  'max-w-[85%] px-3 py-2 rounded-xl text-sm',
                  msg.role === 'user'
                    ? 'ml-auto bg-[color:var(--accent)] text-white rounded-br-sm'
                    : 'mr-auto bg-[color:var(--paper-2)] text-[color:var(--ink)] rounded-bl-sm',
                ].join(' ')}
              >
                {msg.content ? (
                  msg.role === 'assistant' ? (
                    <ChatMarkdown content={msg.content} />
                  ) : (
                    <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                  )
                ) : msg.streaming ? (
                  <StreamingDots />
                ) : null}
              </div>
            ))}
            {error && (
              <p className="text-xs text-[color:var(--negative)] text-center">{error}</p>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-[color:var(--rule-thin)] p-3">
            <div className="flex gap-2">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message… (Enter to send)"
                rows={2}
                className="flex-1 resize-none text-sm border border-[color:var(--rule-thin)] bg-[color:var(--paper)] text-[color:var(--ink)] placeholder:text-[color:var(--ink-4)] px-3 py-2 focus-ring"
                disabled={streaming}
              />
              <button
                onClick={handleSend}
                disabled={streaming || !input.trim()}
                className="self-end px-3 py-2 bg-[color:var(--accent)] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium focus-ring transition-colors"
              >
                Send
              </button>
            </div>
            <p className="text-xs text-[color:var(--ink-4)] mt-1.5">
              Shift+Enter for newline
            </p>
          </div>
        </div>
      )}
    </>
  )
}

function StreamingDots() {
  return (
    <span className="inline-flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-current opacity-60 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}
