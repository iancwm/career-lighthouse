"use client"

import type { RefObject } from "react"
import { ADMIN_WORKSTREAMS, type AdminView, type AdminViewDefinition, type WorkstreamDefinition } from "@/components/admin/adminNavManifest"

interface AdminWorkspaceHeaderProps {
  view: AdminView
  currentSurface: AdminViewDefinition
  activeWorkstream: WorkstreamDefinition
  workstreamViews: AdminViewDefinition[]
  activeSurfaceId: AdminView
  drawerOpen: boolean
  toggleButtonRef: RefObject<HTMLButtonElement>
  onToggleDrawer: () => void
  onNavigate: (next: { view?: AdminView | null; sessionId?: string | null; trackSlug?: string | null }) => void
  onSelectWorkstream: (viewId: AdminView) => void
}

export default function AdminWorkspaceHeader({
  view,
  currentSurface,
  activeWorkstream,
  workstreamViews,
  activeSurfaceId,
  drawerOpen,
  toggleButtonRef,
  onToggleDrawer,
  onNavigate,
  onSelectWorkstream,
}: AdminWorkspaceHeaderProps) {
  return (
    <header className="mb-4 rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] shadow-[0_4px_16px_rgba(31,41,55,0.06)]">
      {/* Row 1: wordmark + active page + shortcuts */}
      <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-[var(--cl-line)]">
        <div className="flex items-center gap-3 min-w-0">
          <span className="shrink-0 font-display text-sm font-medium text-[var(--cl-ink)]">Career Lighthouse</span>
          <span className="text-[var(--cl-line)]" aria-hidden="true">·</span>
          <div className="min-w-0">
            <span className="block text-sm font-medium text-[var(--cl-ink)] truncate">{currentSurface.label}</span>
            <span className="block text-xs text-[var(--cl-muted)] truncate max-w-sm">{currentSurface.description}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {view !== "sessions" && (
            <button
              type="button"
              onClick={() => onNavigate({ view: "sessions", sessionId: null, trackSlug: null })}
              className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--cl-accent-strong)] transition-colors"
            >
              ← Staging Area
            </button>
          )}
          {(activeWorkstream.id === "smart-counsellor" || activeWorkstream.id === "admin-room") && view !== "traces" && (
            <button
              type="button"
              onClick={() => onNavigate({ view: "traces", sessionId: null })}
              className="rounded-full border border-[var(--cl-line)] bg-transparent px-3 py-1.5 text-xs text-[var(--cl-ink)] hover:border-[var(--cl-accent)]/60 transition-colors"
            >
              Traces
            </button>
          )}
          <button
            ref={toggleButtonRef}
            type="button"
            onClick={onToggleDrawer}
            aria-expanded={drawerOpen}
            className="rounded-full border border-[var(--cl-line)] bg-transparent px-3 py-1.5 text-xs text-[var(--cl-ink)] hover:border-[var(--cl-accent)]/60 transition-colors"
          >
            {drawerOpen ? "✕ Close" : `⚙ Browse ${activeWorkstream.label}`}
          </button>
        </div>
      </div>

      {/* Row 2: compact workstream tabs */}
      <div role="tablist" aria-label="Workstreams" className="flex border-b border-[var(--cl-line)] px-4">
        {ADMIN_WORKSTREAMS.map((workstream) => {
          const isActive = workstream.id === activeWorkstream.id
          return (
            <button
              key={workstream.id}
              role="tab"
              aria-selected={isActive}
              type="button"
              onClick={() => onSelectWorkstream(workstream.defaultView)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? "border-[var(--cl-accent)] text-[var(--cl-accent)]"
                  : "border-transparent text-[var(--cl-muted)] hover:text-[var(--cl-ink)]"
              }`}
            >
              {workstream.label}
            </button>
          )
        })}
      </div>

      {/* Row 3: view pills for active workstream */}
      <div className="flex flex-wrap gap-1.5 px-4 py-2.5">
        {workstreamViews.map((item) => {
          const isActive = activeSurfaceId === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate({ view: item.id })}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                isActive
                  ? "border-[var(--cl-accent)] bg-[var(--cl-accent)] text-white"
                  : "border-[var(--cl-line)] bg-[var(--cl-surface)] text-[var(--cl-ink)] hover:border-[var(--cl-accent)]/50"
              }`}
            >
              {item.label}
            </button>
          )
        })}
      </div>
    </header>
  )
}
