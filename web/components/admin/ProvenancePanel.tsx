"use client"

import { useState } from "react"
import { formatUnknown } from "@/types/facts"

interface HistoryItem {
  label: string
  date?: string | null
  note?: string | null
}

interface ProvenancePanelProps {
  source?: string | null
  sourceDate?: string | null
  lastUpdated?: string | null
  supersededBy?: string | null
  auditHref?: string | null
  historyItems?: HistoryItem[]
  historyHref?: string | null
  historyLabel?: string
}

function formatDate(value?: string | null): string {
  if (!value) return "Unknown"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export default function ProvenancePanel({
  source,
  sourceDate,
  lastUpdated,
  supersededBy,
  auditHref,
  historyItems,
  historyHref,
  historyLabel = "View history",
}: ProvenancePanelProps) {
  const [open, setOpen] = useState(false)
  const recentHistory = historyItems?.slice(0, 3) ?? []
  const hasMoreHistory = Boolean(historyItems && historyItems.length > recentHistory.length)
  const summarySourceDate = formatDate(sourceDate)
  const summaryLastUpdated = formatDate(lastUpdated)

  return (
    <div className="rounded-[14px] border border-[#D8D0C4] bg-[#FFFDFC] px-3 py-2.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 text-left text-sm font-medium text-[#5F6B76] focus:outline-none focus:ring-2 focus:ring-[#0F766E] focus:ring-offset-2 focus:ring-offset-[#FFFDFC] rounded-md"
      >
        <span>{open ? "▾ Provenance" : "▸ Provenance"}</span>
        <span className="font-mono-display text-[12px] text-[#5F6B76]">
          {summarySourceDate} · {summaryLastUpdated}
        </span>
      </button>

      {open && (
        <div className="mt-3 space-y-2 font-mono-display text-[12px] leading-5 text-[#5F6B76]">
          <div className="grid grid-cols-[7rem,1fr] gap-2">
            <div>Source</div>
            <div className="text-[#1F2937]">{formatUnknown(source)}</div>
          </div>
          <div className="grid grid-cols-[7rem,1fr] gap-2">
            <div>Source date</div>
            <div className="text-[#1F2937]">{formatDate(sourceDate)}</div>
          </div>
          <div className="grid grid-cols-[7rem,1fr] gap-2">
            <div>Last updated</div>
            <div className="text-[#1F2937]">{formatDate(lastUpdated)}</div>
          </div>
          <div className="grid grid-cols-[7rem,1fr] gap-2">
            <div>Superseded by</div>
            <div className="text-[#1F2937]">{formatUnknown(supersededBy)}</div>
          </div>
          {auditHref && (
            <div className="pt-1">
              <a
                href={auditHref}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-sm font-medium text-[#0F766E] hover:underline"
              >
                Audit link
                <span aria-hidden="true">→</span>
              </a>
            </div>
          )}
          {recentHistory.length > 0 && (
            <div className="pt-2 border-t border-[#D8D0C4]">
              <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-[#5F6B76]">Recent history</div>
              <ul className="space-y-1">
                {recentHistory.map((item) => (
                  <li key={`${item.label}-${item.date ?? ""}`} className="flex items-start justify-between gap-3">
                    <span className="text-[#1F2937]">{item.label}</span>
                    <span className="shrink-0">{formatDate(item.date)}</span>
                  </li>
                ))}
              </ul>
              {hasMoreHistory && historyHref && (
                <div className="mt-2">
                  <a
                    href={historyHref}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-[#0F766E] hover:underline"
                  >
                    {historyLabel}
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
