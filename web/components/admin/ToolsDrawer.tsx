"use client"

import { useEffect, useRef, useCallback } from "react"

export type DrawerSurface = "observability" | "traces" | "knowledge" | "update" | "careers" | "employers" | "tracks" | "resume" | "broken"

interface ToolsDrawerProps {
  open: boolean
  activeSurface: DrawerSurface | null
  onToggle: () => void
  onNavigate: (view: DrawerSurface) => void
  toggleButtonRef: React.RefObject<HTMLButtonElement | null>
}

const DRAWER_ITEMS: { id: DrawerSurface; label: string; purpose: string; provenance: string }[] = [
  { id: "observability", label: "LLM Observability", purpose: "Inspect traces, latency, and retrieval health.", provenance: "Source: trace log · Last updated: live" },
  { id: "traces", label: "Trace Explorer", purpose: "Inspect a session's LLM runs, failures, and live starts.", provenance: "Source: session traces · Last updated: live" },
  { id: "knowledge", label: "Documents", purpose: "Upload, inspect, and measure the KB.", provenance: "Source: uploaded documents · Last updated: after ingest" },
  { id: "update", label: "Review Updates", purpose: "Review a note or file before it changes the KB.", provenance: "Source: counsellor note or file · Last updated: after review" },
  { id: "resume", label: "Resume Review", purpose: "Generate prep briefs from student resumes.", provenance: "Source: student resume · Last updated: on request" },
  { id: "broken", label: "⚠ Broken Profiles", purpose: "Fix career profiles with missing fields.", provenance: "Source: profile YAML · Last updated: after save" },
  { id: "employers", label: "Employer Facts", purpose: "Maintain employer-specific facts and retain retired ones for audit.", provenance: "Source: employer YAML · Last updated: after save" },
  { id: "tracks", label: "Track Builder", purpose: "Draft, publish, and rollback career tracks.", provenance: "Source: draft + publish history · Last updated: after publish" },
  { id: "careers", label: "Career Tracks", purpose: "See structured chat metadata and published track state.", provenance: "Source: career profile YAML · Last updated: after save" },
]

export default function ToolsDrawer({ open, activeSurface, onToggle, onNavigate, toggleButtonRef }: ToolsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null)
  const firstCardRef = useRef<HTMLButtonElement>(null)

  // Focus management: on open, focus first card
  useEffect(() => {
    if (open && firstCardRef.current) {
      firstCardRef.current.focus()
    }
  }, [open])

  // Escape key closes drawer
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        e.preventDefault()
        onToggle()
        // Return focus to toggle button
        setTimeout(() => toggleButtonRef.current?.focus(), 0)
      }
    },
    [open, onToggle, toggleButtonRef]
  )

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKeyDown)
      return () => document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open, handleKeyDown])

  if (!open) return null

  return (
    <div
      ref={drawerRef}
      role="region"
      aria-label="Knowledge management tools"
      className="relative mb-6"
    >
      <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {DRAWER_ITEMS.map((item, index) => {
            const isActive = activeSurface === item.id
            return (
              <button
                key={item.id}
                ref={index === 0 ? firstCardRef : undefined}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={`group flex flex-col items-start rounded-xl border px-4 py-3 text-left transition-colors ${
                  isActive
                    ? "border-l-[3px] border-l-[var(--cl-accent)] border-[var(--cl-line)] bg-[var(--cl-surface-2)]"
                  : "border-[var(--cl-line)] bg-[var(--cl-surface)] hover:bg-[var(--cl-surface-2)]"
                }`}
              >
                <div className="flex w-full items-start justify-between gap-3">
                  <span className="font-display text-[var(--cl-ink)]" style={{ fontSize: "22px", lineHeight: "1.15" }}>
                    {item.label}
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      isActive
                        ? "border-[var(--cl-accent)]/20 bg-[var(--cl-accent)]/10 text-[var(--cl-accent)]"
                        : "border-[var(--cl-line)] bg-[var(--cl-surface-2)] text-[var(--cl-muted)]"
                    }`}
                  >
                    {isActive ? "Active" : "Ready"}
                  </span>
                </div>
                <span className="mt-1 text-sm text-[var(--cl-muted)]" style={{ fontSize: "14px", lineHeight: "1.5" }}>
                  {item.purpose}
                </span>
                <span className="mt-2 font-mono-display text-[12px] leading-5 text-[var(--cl-muted)]">
                  {item.provenance}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
