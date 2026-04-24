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
    <header className="mb-6 rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)]/92 p-6 shadow-[0_18px_60px_rgba(31,41,55,0.08)] backdrop-blur">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Counsellor workspace</p>
          <h1 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)] sm:text-4xl">
            Career Lighthouse
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
            Workstream-first navigation keeps intake, student prep, and machine-room operations in separate lanes.
          </p>
        </div>

        <div className="flex flex-col items-end gap-3">
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-muted)]">Active page</p>
            <p className="mt-1 font-display text-xl text-[var(--cl-ink)]">{currentSurface.label}</p>
            <p className="mt-1 text-sm text-[var(--cl-muted)]">{currentSurface.description}</p>
          </div>
          <div className="flex items-center gap-2">
            {view !== "sessions" && (
              <button
                type="button"
                onClick={() => onNavigate({ view: "sessions", sessionId: null, trackSlug: null })}
                className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90"
              >
                ← Staging Area
              </button>
            )}
            {(activeWorkstream.id === "smart-counsellor" || activeWorkstream.id === "admin-room") && view !== "traces" && (
              <button
                type="button"
                onClick={() => onNavigate({ view: "traces", sessionId: null })}
                className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
              >
                Open Trace Explorer
              </button>
            )}
            <button
              ref={toggleButtonRef}
              type="button"
              onClick={onToggleDrawer}
              aria-expanded={drawerOpen}
              className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
            >
              {drawerOpen ? "\u2715 Close" : `\u2699 Browse ${activeWorkstream.label}`}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        {ADMIN_WORKSTREAMS.map((workstream) => {
          const isActive = workstream.id === activeWorkstream.id
          return (
            <button
              key={workstream.id}
              type="button"
              onClick={() => onSelectWorkstream(workstream.defaultView)}
              className={`rounded-2xl border px-4 py-4 text-left transition-colors ${
                isActive
                  ? "border-[var(--cl-accent)] bg-[var(--cl-accent)]/8"
                  : "border-[var(--cl-line)] bg-[var(--cl-surface)] hover:border-[var(--cl-accent)]/40"
              }`}
            >
              <p className="font-display text-xl text-[var(--cl-ink)]">{workstream.label}</p>
              <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">{workstream.description}</p>
              <span
                className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                  isActive
                    ? "bg-[var(--cl-accent)] text-white"
                    : "bg-[var(--cl-surface-2)] text-[var(--cl-muted)]"
                }`}
              >
                {isActive ? "Current lane" : "Switch lane"}
              </span>
            </button>
          )
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {workstreamViews.map((item) => {
          const isActive = activeSurfaceId === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate({ view: item.id })}
              className={`rounded-full border px-4 py-2 text-sm transition-colors ${
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
