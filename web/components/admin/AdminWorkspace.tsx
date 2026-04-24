"use client"

import { useEffect, useRef, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { adminFetch } from "@/lib/admin-api"
import KnowledgeUpload from "@/components/admin/KnowledgeUpload"
import DocList from "@/components/admin/DocList"
import StatCards from "@/components/admin/StatCards"
import TestQueryBox from "@/components/admin/TestQueryBox"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"
import KnowledgeUpdateTab from "@/components/admin/KnowledgeUpdateTab"
import EmployerFactsTab from "@/components/admin/EmployerFactsTab"
import AlumniFactsTab from "@/components/admin/AlumniFactsTab"
import TrackBuilderTab from "@/components/admin/TrackBuilderTab"
import SessionInbox from "@/components/admin/SessionInbox"
import SmartCanvas from "@/components/admin/SmartCanvas"
import LLMObservabilityTab from "@/components/admin/LLMObservabilityTab"
import StudentInsightsTab from "@/components/admin/StudentInsightsTab"
import FactsDashboardTab from "@/components/admin/FactsDashboardTab"
import TraceExplorerTab from "@/components/admin/TraceExplorerTab"
import ResumeReviewTab from "@/components/admin/ResumeReviewTab"
import BrokenProfilesTab from "@/components/admin/BrokenProfilesTab"
import ToolsDrawer from "@/components/admin/ToolsDrawer"
import DirectiveBanner from "@/components/admin/DirectiveBanner"
import {
  ADMIN_WORKSTREAMS,
  AdminView,
  getViewDefinition,
  getWorkstreamForView,
  getWorkstreamViews,
  isAdminView,
} from "@/components/admin/adminNavManifest"

interface KBHealth {
  total_docs: number
  total_chunks: number
  avg_match_score: number | null
  retrieval_diversity_score: number | null
  low_confidence_queries: {
    ts: string
    query_text: string
    max_score: number
    doc_matched: string | null
  }[]
  doc_coverage: {
    filename: string
    chunk_count: number
    coverage_status: "good" | "thin"
    has_overlap_warning: boolean
  }[]
  high_overlap_pairs: {
    doc_a: string
    doc_b: string
    overlap_pct: number
    recommendation: string
  }[]
}

export default function AdminWorkspace() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const viewParam = searchParams.get("view")
  const sessionParam = searchParams.get("sessionId")
  const trackParam = searchParams.get("trackSlug")
  const view: AdminView = isAdminView(viewParam) ? viewParam : "sessions"

  const [refreshKey, setRefreshKey] = useState(0)
  const [health, setHealth] = useState<KBHealth | null>(null)
  const [healthError, setHealthError] = useState(false)
  const [healthLoading, setHealthLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const toggleButtonRef = useRef<HTMLButtonElement>(null)

  function buildUrl(next: {
    view?: AdminView | null
    sessionId?: string | null
    trackSlug?: string | null
  }) {
    const params = new URLSearchParams(searchParams.toString())

    if (next.view !== undefined) {
      if (next.view) params.set("view", next.view)
      else params.delete("view")
    } else if (!params.get("view")) {
      params.set("view", "sessions")
    }

    if (next.sessionId !== undefined) {
      if (next.sessionId) params.set("sessionId", next.sessionId)
      else params.delete("sessionId")
    }

    if (next.trackSlug !== undefined) {
      if (next.trackSlug) params.set("trackSlug", next.trackSlug)
      else params.delete("trackSlug")
    }

    if (next.view && next.view !== "sessions" && next.view !== "traces") {
      params.delete("sessionId")
    }
    if (next.view && next.view !== "tracks" && next.view !== "careers") {
      params.delete("trackSlug")
    }

    if (params.size === 0) return pathname
    return `${pathname}?${params.toString()}`
  }

  function navigate(next: {
    view?: AdminView | null
    sessionId?: string | null
    trackSlug?: string | null
  }) {
    router.push(buildUrl(next), { scroll: false })
  }

  useEffect(() => {
    if (!isAdminView(viewParam)) {
      const fallback = viewParam === null ? "sessions" : view
      if (fallback !== viewParam) {
        router.replace(buildUrl({ view: fallback }), { scroll: false })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewParam])

  useEffect(() => {
    if (view !== "knowledge") return
    let cancelled = false
    setHealthLoading(true)
    setHealthError(false)
    adminFetch("/api/kb/health")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((data: KBHealth) => {
        if (!cancelled) setHealth(data)
      })
      .catch(() => {
        if (!cancelled) setHealthError(true)
      })
      .finally(() => {
        if (!cancelled) setHealthLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [view, refreshKey])

  const currentSurface = getViewDefinition(view)
  const activeWorkstream = getWorkstreamForView(view)
  const workstreamViews = getWorkstreamViews(activeWorkstream.id)
  const activeSurfaceId = view === "careers" ? "tracks" : view

  function toggleDrawer() {
    setDrawerOpen((value) => !value)
  }

  function handleDrawerNavigate(nextView: AdminView) {
    setDrawerOpen(false)
    navigate({
      view: nextView,
      sessionId: nextView === "traces" ? sessionParam : null,
      trackSlug: nextView === "tracks" || nextView === "careers" ? trackParam : null,
    })
  }

  function selectWorkstream(viewId: AdminView) {
    setDrawerOpen(false)
    navigate({ view: viewId, sessionId: null, trackSlug: null })
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
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
                  onClick={() => navigate({ view: "sessions", sessionId: null, trackSlug: null })}
                  className="rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90"
                >
                  ← Staging Area
                </button>
              )}
              {(activeWorkstream.id === "smart-counsellor" || activeWorkstream.id === "admin-room") && view !== "traces" && (
                <button
                  type="button"
                  onClick={() => navigate({ view: "traces", sessionId: null })}
                  className="rounded-full border border-[var(--cl-line)] bg-white/70 px-4 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
                >
                  Open Trace Explorer
                </button>
              )}
              <button
                ref={toggleButtonRef}
                type="button"
                onClick={toggleDrawer}
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
                onClick={() => selectWorkstream(workstream.defaultView)}
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
                onClick={() => handleDrawerNavigate(item.id)}
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

      <ToolsDrawer
        open={drawerOpen}
        workstreamId={activeWorkstream.id}
        activeView={view}
        onToggle={toggleDrawer}
        onNavigate={handleDrawerNavigate}
        toggleButtonRef={toggleButtonRef}
      />

      <DirectiveBanner
        label={currentSurface.directive.label}
        whatYouDo={currentSurface.directive.whatYouDo}
        whatHappens={currentSurface.directive.whatHappens}
      />

      {view === "knowledge" && (
        <section className="space-y-6">
          <div className="space-y-6">
            <KnowledgeUpload onUploaded={() => setRefreshKey((value) => value + 1)} />
            <DocList refreshKey={refreshKey} onDeleted={() => setRefreshKey((value) => value + 1)} />
          </div>

          <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl text-[var(--cl-ink)]">KB Health</h2>
                <p className="mt-1 text-sm text-[var(--cl-muted)]">Document coverage, retrieval quality, and overlap signals.</p>
              </div>
              <button
                type="button"
                onClick={() => setRefreshKey((value) => value + 1)}
                className="rounded-full border border-[var(--cl-line)] px-4 py-2 text-xs font-medium text-[var(--cl-ink)] hover:border-[var(--cl-accent)]"
              >
                Refresh
              </button>
            </div>

            {healthLoading && <p className="text-sm text-[var(--cl-muted)]">Loading KB health…</p>}
            {healthError && (
              <div className="mb-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
                Knowledge base unavailable - check that Qdrant is running.
              </div>
            )}

            {health && (
              <>
                <StatCards
                  totalDocs={health.total_docs}
                  totalChunks={health.total_chunks}
                  lowConfidenceCount={health.low_confidence_queries.length}
                  avgMatchScore={health.avg_match_score}
                  diversityScore={health.retrieval_diversity_score}
                />

                <div className="mt-4">
                  <TestQueryBox />
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <DocCoverageList docs={health.doc_coverage} />
                  <LowConfidenceLog
                    avgMatchScore={health.avg_match_score}
                    queries={health.low_confidence_queries}
                  />
                </div>

                {health.high_overlap_pairs.length > 0 && (
                  <div className="mt-6">
                    <RedundancyPanel pairs={health.high_overlap_pairs} />
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      )}

      {view === "observability" && <LLMObservabilityTab />}

      {view === "student-insights" && <StudentInsightsTab />}

      {view === "facts" && <FactsDashboardTab />}

      {view === "traces" && <TraceExplorerTab initialSessionId={sessionParam} />}

      {view === "update" && (
        <KnowledgeUpdateTab
          onCommitted={() => setRefreshKey((value) => value + 1)}
          onNavigateToSession={() => navigate({ view: "sessions", sessionId: null })}
        />
      )}

      {view === "resume" && <ResumeReviewTab />}

      {view === "broken" && <BrokenProfilesTab />}

      {view === "employers" && <EmployerFactsTab />}

      {view === "alumni" && <AlumniFactsTab />}

      {(view === "tracks" || view === "careers") && (
        <TrackBuilderTab
          selectedSlug={trackParam}
          onSelectedSlugChange={(slug) => navigate({ view, trackSlug: slug })}
        />
      )}

      {view === "sessions" && (
        sessionParam ? (
          <SmartCanvas
            sessionId={sessionParam}
            onBack={() => navigate({ view: "sessions", sessionId: null })}
            onOpenTraces={(id) => navigate({ view: "traces", sessionId: id })}
          />
        ) : (
          <SessionInbox
            onSelectSession={(id) => navigate({ view: "sessions", sessionId: id })}
            onOpenTraces={(id) => navigate({ view: "traces", sessionId: id })}
            onOpenAlumni={() => navigate({ view: "alumni" })}
          />
        )
      )}
    </div>
  )
}
