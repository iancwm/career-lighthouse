"use client"

import { useEffect, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import KnowledgeUpload from "@/components/admin/KnowledgeUpload"
import DocList from "@/components/admin/DocList"
import BriefGenerator from "@/components/admin/BriefGenerator"
import StatCards from "@/components/admin/StatCards"
import TestQueryBox from "@/components/admin/TestQueryBox"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"
import KnowledgeUpdateTab from "@/components/admin/KnowledgeUpdateTab"
import EmployerFactsTab from "@/components/admin/EmployerFactsTab"
import TrackBuilderTab from "@/components/admin/TrackBuilderTab"
import CareerTracksTab from "@/components/admin/CareerTracksTab"
import SessionInbox from "@/components/admin/SessionInbox"
import SmartCanvas from "@/components/admin/SmartCanvas"

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

type AdminView = "knowledge" | "update" | "careers" | "employers" | "tracks" | "sessions"

const VIEW_ORDER: { id: AdminView; label: string; description: string }[] = [
  { id: "sessions", label: "Sessions", description: "Review active counselor sessions first." },
  { id: "knowledge", label: "Documents", description: "Upload, inspect, and measure the KB." },
  { id: "update", label: "Review Updates", description: "Turn notes into reviewed changes." },
  { id: "careers", label: "Career Tracks", description: "See structured chat metadata." },
  { id: "employers", label: "Employer Facts", description: "Maintain employer-specific facts." },
  { id: "tracks", label: "Track Builder", description: "Draft, publish, and rollback career tracks." },
]

function isAdminView(value: string | null): value is AdminView {
  return value === "knowledge" || value === "update" || value === "careers" || value === "employers" || value === "tracks" || value === "sessions"
}

export default function AdminWorkspace() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
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

    if (next.view && next.view !== "sessions") {
      params.delete("sessionId")
    }
    if (next.view && next.view !== "tracks") {
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
    if (!apiUrl) return
    let cancelled = false
    setHealthLoading(true)
    setHealthError(false)
    fetch(`${apiUrl}/api/kb/health`)
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

  const currentSurface = VIEW_ORDER.find((item) => item.id === view) ?? VIEW_ORDER[0]

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
              Review sessions first, keep the knowledge base tidy, and publish career tracks with a clear working-copy trail.
            </p>
          </div>

          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-muted)]">Active surface</p>
            <p className="mt-1 font-display text-xl text-[var(--cl-ink)]">{currentSurface.label}</p>
            <p className="mt-1 text-sm text-[var(--cl-muted)]">{currentSurface.description}</p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {VIEW_ORDER.map((item) => {
            const active = item.id === view
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate({ view: item.id, sessionId: null, trackSlug: null })}
                className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                  active
                    ? "border-[var(--cl-accent)] bg-[var(--cl-accent)] text-white"
                    : "border-[var(--cl-line)] bg-white/70 text-[var(--cl-ink)] hover:border-[var(--cl-accent)]/60 hover:bg-white"
                }`}
              >
                {item.label}
              </button>
            )
          })}
        </div>
      </header>

      {view === "knowledge" && (
        <section className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="space-y-6">
              <KnowledgeUpload onUploaded={() => setRefreshKey((value) => value + 1)} />
              <DocList refreshKey={refreshKey} onDeleted={() => setRefreshKey((value) => value + 1)} />
            </div>
            <BriefGenerator />
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
                  <TestQueryBox apiUrl={apiUrl} />
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

      {view === "update" && (
        <KnowledgeUpdateTab
          onCommitted={() => setRefreshKey((value) => value + 1)}
          onNavigateToSession={() => navigate({ view: "sessions", sessionId: null })}
        />
      )}

      {view === "careers" && <CareerTracksTab />}

      {view === "employers" && <EmployerFactsTab />}

      {view === "tracks" && (
        <TrackBuilderTab
          selectedSlug={trackParam}
          onSelectedSlugChange={(slug) => navigate({ view: "tracks", trackSlug: slug })}
        />
      )}

      {view === "sessions" && (
        sessionParam ? (
          <SmartCanvas
            sessionId={sessionParam}
            onBack={() => navigate({ view: "sessions", sessionId: null })}
          />
        ) : (
          <SessionInbox
            onSelectSession={(id) => navigate({ view: "sessions", sessionId: id })}
          />
        )
      )}
    </div>
  )
}
