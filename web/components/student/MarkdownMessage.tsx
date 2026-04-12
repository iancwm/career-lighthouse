"use client"

import type { ReactNode } from "react"

function parseInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let index = 0

  while (index < text.length) {
    const boldStart = text.indexOf("**", index)
    const codeStart = text.indexOf("`", index)
    const linkStart = text.indexOf("[", index)

    const candidates = [boldStart, codeStart, linkStart].filter((value) => value !== -1)
    if (candidates.length === 0) {
      nodes.push(text.slice(index))
      break
    }

    const next = Math.min(...candidates)
    if (next > index) {
      nodes.push(text.slice(index, next))
      index = next
      continue
    }

    if (boldStart === next) {
      const end = text.indexOf("**", boldStart + 2)
      if (end !== -1) {
        nodes.push(<strong key={`${boldStart}-${end}`}>{text.slice(boldStart + 2, end)}</strong>)
        index = end + 2
        continue
      }
    }

    if (codeStart === next) {
      const end = text.indexOf("`", codeStart + 1)
      if (end !== -1) {
        nodes.push(
          <code key={`${codeStart}-${end}`} className="rounded bg-[var(--cl-surface-2)] px-1.5 py-0.5 font-mono-display text-[0.85em] text-[var(--cl-ink)]">
            {text.slice(codeStart + 1, end)}
          </code>
        )
        index = end + 1
        continue
      }
    }

    if (linkStart === next) {
      const closeBracket = text.indexOf("]", linkStart + 1)
      const openParen = closeBracket === -1 ? -1 : text.indexOf("(", closeBracket + 1)
      const closeParen = openParen === -1 ? -1 : text.indexOf(")", openParen + 1)
      if (closeBracket !== -1 && openParen === closeBracket + 1 && closeParen !== -1) {
        const label = text.slice(linkStart + 1, closeBracket)
        const href = text.slice(openParen + 1, closeParen)
        if (/^(https?:\/\/|mailto:)/i.test(href)) {
          nodes.push(
            <a
              key={`${linkStart}-${closeParen}`}
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-[var(--cl-accent)] underline decoration-[var(--cl-line)] underline-offset-2 hover:text-[var(--cl-accent-strong)]"
            >
              {label}
            </a>
          )
          index = closeParen + 1
          continue
        }
      }
    }

    nodes.push(text[index])
    index += 1
  }

  return nodes
}

function flushParagraphs(buffer: string[]): ReactNode[] {
  if (buffer.length === 0) return []
  return [
    <p key={buffer.join("\n")} className="whitespace-pre-wrap">
      {parseInline(buffer.join("\n"))}
    </p>,
  ]
}

export default function MarkdownMessage({ content }: { content: string }) {
  const lines = content.split(/\r?\n/)
  const blocks: ReactNode[] = []
  const paragraphBuffer: string[] = []

  function flushParagraphBuffer() {
    blocks.push(...flushParagraphs(paragraphBuffer.splice(0, paragraphBuffer.length)))
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      flushParagraphBuffer()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushParagraphBuffer()
      const level = headingMatch[1].length
      const HeadingTag = `h${level}` as "h1" | "h2" | "h3"
      const headingClass =
        level === 1
          ? "font-display text-xl text-[var(--cl-ink)]"
          : level === 2
            ? "font-display text-lg text-[var(--cl-ink)]"
            : "font-semibold text-[var(--cl-ink)]"
      blocks.push(
        <HeadingTag key={`${index}-${trimmed}`} className={headingClass}>
          {parseInline(headingMatch[2])}
        </HeadingTag>
      )
      continue
    }

    if (trimmed.startsWith("```")) {
      flushParagraphBuffer()
      const codeLines: string[] = []
      let foundEnd = false
      for (index += 1; index < lines.length; index += 1) {
        const codeLine = lines[index]
        if (codeLine.trim().startsWith("```")) {
          foundEnd = true
          break
        }
        codeLines.push(codeLine)
      }
      blocks.push(
        <pre
          key={`code-${index}`}
          className="overflow-x-auto rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4 text-sm text-[var(--cl-ink)]"
        >
          <code className="font-mono-display">{codeLines.join("\n")}</code>
        </pre>
      )
      if (!foundEnd) break
      continue
    }

    const listMatch = trimmed.match(/^[-*]\s+(.+)$/)
    if (listMatch) {
      flushParagraphBuffer()
      const items: string[] = [listMatch[1]]
      while (index + 1 < lines.length) {
        const nextLine = lines[index + 1].trim()
        const nextMatch = nextLine.match(/^[-*]\s+(.+)$/)
        if (!nextMatch) break
        items.push(nextMatch[1])
        index += 1
      }
      blocks.push(
        <ul key={`list-${index}`} className="list-disc space-y-2 pl-5">
          {items.map((item, itemIndex) => (
            <li key={`${item}-${itemIndex}`}>{parseInline(item)}</li>
          ))}
        </ul>
      )
      continue
    }

    paragraphBuffer.push(line)
  }

  flushParagraphBuffer()

  if (blocks.length === 0) {
    return <p className="whitespace-pre-wrap">{content}</p>
  }

  return <div className="space-y-3">{blocks}</div>
}
