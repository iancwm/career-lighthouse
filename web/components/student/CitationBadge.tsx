"use client"

import { useId, useState } from "react"

interface Props {
  filename: string
  excerpt: string
  sourceName?: string | null
  updatedAt?: string | null
  sourceLifecycle?: string | null
}

function formatDate(value?: string | null): string {
  const clean = typeof value === "string" ? value.trim() : ""
  if (!clean) return "Unknown"
  const parsed = new Date(clean)
  if (Number.isNaN(parsed.getTime())) return clean
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function formatUnknown(value?: string | null): string {
  const clean = typeof value === "string" ? value.trim() : ""
  return clean || "Unknown"
}

export default function CitationBadge({
  filename,
  excerpt,
  sourceName,
  updatedAt,
  sourceLifecycle,
}: Props) {
  const [open, setOpen] = useState(false)
  const detailId = useId()
  const resolvedSourceName = formatUnknown(sourceName || filename)
  const resolvedDate = formatDate(updatedAt)
  const lifecycleLabel = sourceLifecycle?.trim()
    ? sourceLifecycle.replace(/_/g, " ")
    : null

  return (
    <div className="inline-flex max-w-full flex-col items-start gap-1">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            setOpen((value) => !value)
          }
        }}
        className="inline-flex min-h-10 max-w-full items-center gap-2 rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-3 py-2 text-left text-xs text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
        title={formatUnknown(excerpt)}
      >
        <span className="max-w-[14rem] truncate font-medium">{resolvedSourceName}</span>
        <span className="shrink-0 font-mono-display text-[11px] text-[var(--cl-muted)]">
          {open ? "Hide details" : "Details"}
        </span>
      </button>

      {open && (
        <div
          id={detailId}
          className="w-full max-w-[22rem] rounded-[14px] border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-[11px] leading-5 text-[var(--cl-muted)] shadow-sm"
        >
          <div className="grid grid-cols-[5.5rem,1fr] gap-2">
            <div className="font-mono-display uppercase tracking-[0.16em]">Source</div>
            <div className="text-[var(--cl-ink)]">{resolvedSourceName}</div>
          </div>
          <div className="mt-1 grid grid-cols-[5.5rem,1fr] gap-2">
            <div className="font-mono-display uppercase tracking-[0.16em]">Updated</div>
            <div className="text-[var(--cl-ink)]">{resolvedDate}</div>
          </div>
          {lifecycleLabel && (
            <div className="mt-1 grid grid-cols-[5.5rem,1fr] gap-2">
              <div className="font-mono-display uppercase tracking-[0.16em]">State</div>
              <div className="text-[var(--cl-ink)]">{lifecycleLabel}</div>
            </div>
          )}
          <div className="mt-2 border-t border-[var(--cl-line)] pt-2">
            <div className="font-mono-display uppercase tracking-[0.16em]">Excerpt</div>
            <p className="mt-1 text-[var(--cl-ink)]">{formatUnknown(excerpt)}</p>
          </div>
        </div>
      )}
    </div>
  )
}
