import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Renders assistant chat text as Markdown (GFM): paragraphs, lists, bold,
 * inline/blocked code, tables, links. react-markdown does not render raw HTML
 * by default, so this is XSS-safe for untrusted model output.
 */
export function ChatMarkdown({ content }: { content: string }) {
  return (
    <div className="space-y-2 break-words leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc pl-5 space-y-0.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 space-y-0.5">{children}</ol>
          ),
          li: ({ children }) => <li className="marker:text-[color:var(--ink-4)]">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[color:var(--accent)] underline"
            >
              {children}
            </a>
          ),
          code: ({ className, children }) => {
            const inline = !className
            return inline ? (
              <code className="px-1 py-0.5 bg-[color:var(--paper-2)] font-mono text-[0.85em]">
                {children}
              </code>
            ) : (
              <code className={`${className ?? ''} font-mono text-[0.85em]`}>
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="overflow-x-auto bg-[color:var(--paper-2)] p-2 text-[0.85em]">
              {children}
            </pre>
          ),
          h1: ({ children }) => <h3 className="font-semibold text-base">{children}</h3>,
          h2: ({ children }) => <h3 className="font-semibold text-base">{children}</h3>,
          h3: ({ children }) => <h3 className="font-semibold">{children}</h3>,
          table: ({ children }) => (
            <table className="w-full text-xs border-collapse">{children}</table>
          ),
          th: ({ children }) => (
            <th className="border border-[color:var(--rule-thin)] px-1.5 py-0.5 text-left">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[color:var(--rule-thin)] px-1.5 py-0.5">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
