"use client"

import { useCallback, useEffect, useMemo, useRef } from "react"
import {
  AdminView,
  WorkstreamId,
  getWorkstreamById,
  getWorkstreamViews,
} from "@/components/admin/adminNavManifest"

interface ToolsDrawerProps {
  open: boolean
  workstreamId: WorkstreamId
  activeView: AdminView
  onToggle: () => void
  onNavigate: (view: AdminView) => void
  toggleButtonRef: React.RefObject<HTMLButtonElement | null>
}

const SOURCE_TEXT: Partial<Record<AdminView, string>> = {
  sessions: "Source: counsellor notes and uploads",
  knowledge: "Source: uploaded documents",
  update: "Source: counsellor note or file",
  employers: "Source: employer YAML",
  tracks: "Source: draft + publish history",
  broken: "Source: profile YAML",
  resume: "Source: student resume",
  observability: "Source: trace and retrieval logs",
  "student-insights": "Source: student chat",
}

export default function ToolsDrawer({
  open,
  workstreamId,
  activeView,
  onToggle,
  onNavigate,
  toggleButtonRef,
}: ToolsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null)
  const firstCardRef = useRef<HTMLButtonElement>(null)
  const workstream = getWorkstreamById(workstreamId)
  const drawerViews = useMemo(() => getWorkstreamViews(workstreamId, { forDrawer: true }), [workstreamId])

  useEffect(() => {
    if (open && firstCardRef.current) {
      firstCardRef.current.focus()
    }
  }, [open])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        e.preventDefault()
        onToggle()
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
      aria-label={`${workstream.label} pages`}
      className="relative mb-6"
    >
      <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--cl-muted)]">{workstream.label}</p>
          <p className="text-xs text-[var(--cl-muted)]">Choose a page</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {drawerViews.map((item, index) => {
            const isActive = activeView === item.id || (activeView === "careers" && item.id === "tracks")
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
                  {item.description}
                </span>
                <span className="mt-2 font-mono-display text-[12px] leading-5 text-[var(--cl-muted)]">
                  {SOURCE_TEXT[item.id] ?? "Source: workflow metadata"}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
