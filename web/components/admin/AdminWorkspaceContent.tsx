"use client"

import type { RefObject } from "react"
import ToolsDrawer from "@/components/admin/ToolsDrawer"
import DirectiveBanner from "@/components/admin/DirectiveBanner"
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
import { ActionStatus } from "@/components/admin/ui/ActionStatus"
import type { AdminView, AdminViewDefinition, WorkstreamDefinition } from "@/components/admin/adminNavManifest"
import type { KBHealth } from "@/components/admin/useAdminWorkspace"

interface AdminWorkspaceContentProps {
  view: AdminView
  sessionParam: string | null
  trackParam: string | null
  currentSurface: AdminViewDefinition
  activeWorkstream: WorkstreamDefinition
  drawerOpen: boolean
  toggleButtonRef: RefObject<HTMLButtonElement>
  health: KBHealth | null
  healthError: boolean
  healthLoading: boolean
  refreshKey: number
  onToggleDrawer: () => void
  onNavigate: (next: { view?: AdminView | null; sessionId?: string | null; trackSlug?: string | null }) => void
  onRefresh: () => void
}

function KnowledgeWorkspace({
  health,
  healthError,
  healthLoading,
  refreshKey,
  onRefresh,
}: {
  health: KBHealth | null
  healthError: boolean
  healthLoading: boolean
  refreshKey: number
  onRefresh: () => void
}) {
  return (
    <section className="space-y-6">
      <div className="space-y-6">
        <KnowledgeUpload onUploaded={onRefresh} />
        <DocList refreshKey={refreshKey} onDeleted={onRefresh} />
      </div>

      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl text-[var(--cl-ink)]">KB Health</h2>
            <p className="mt-1 text-sm text-[var(--cl-muted)]">Document coverage, retrieval quality, and overlap signals.</p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-full border border-[var(--cl-line)] px-4 py-2 text-xs font-medium text-[var(--cl-ink)] hover:border-[var(--cl-accent)]"
          >
            Refresh
          </button>
        </div>

        {healthLoading && (
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <ActionStatus label="Loading KB health…" />
          </div>
        )}
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
              <LowConfidenceLog avgMatchScore={health.avg_match_score} queries={health.low_confidence_queries} />
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
  )
}

export default function AdminWorkspaceContent({
  view,
  sessionParam,
  trackParam,
  currentSurface,
  activeWorkstream,
  drawerOpen,
  toggleButtonRef,
  health,
  healthError,
  healthLoading,
  refreshKey,
  onToggleDrawer,
  onNavigate,
  onRefresh,
}: AdminWorkspaceContentProps) {
  return (
    <>
      <ToolsDrawer
        open={drawerOpen}
        workstreamId={activeWorkstream.id}
        activeView={view}
        onToggle={onToggleDrawer}
        onNavigate={(nextView) =>
          onNavigate({
            view: nextView,
            sessionId: nextView === "traces" ? sessionParam : null,
            trackSlug: nextView === "tracks" || nextView === "careers" ? trackParam : null,
          })
        }
        toggleButtonRef={toggleButtonRef}
      />

      <DirectiveBanner
        label={currentSurface.directive.label}
        whatYouDo={currentSurface.directive.whatYouDo}
        whatHappens={currentSurface.directive.whatHappens}
      />

      {view === "knowledge" && (
        <KnowledgeWorkspace
          health={health}
          healthError={healthError}
          healthLoading={healthLoading}
          refreshKey={refreshKey}
          onRefresh={onRefresh}
        />
      )}

      {view === "observability" && <LLMObservabilityTab />}

      {view === "student-insights" && <StudentInsightsTab />}

      {view === "facts" && <FactsDashboardTab />}

      {view === "traces" && <TraceExplorerTab initialSessionId={sessionParam} />}

      {view === "update" && (
        <KnowledgeUpdateTab
          onCommitted={onRefresh}
          onNavigateToSession={() => onNavigate({ view: "sessions", sessionId: null })}
        />
      )}

      {view === "resume" && <ResumeReviewTab />}

      {view === "broken" && <BrokenProfilesTab />}

      {view === "employers" && <EmployerFactsTab />}

      {view === "alumni" && <AlumniFactsTab />}

      {(view === "tracks" || view === "careers") && (
        <TrackBuilderTab
          selectedSlug={trackParam}
          onSelectedSlugChange={(slug) => onNavigate({ view, trackSlug: slug })}
        />
      )}

      {view === "sessions" &&
        (sessionParam ? (
          <SmartCanvas
            sessionId={sessionParam}
            onBack={() => onNavigate({ view: "sessions", sessionId: null })}
            onOpenTraces={(id) => onNavigate({ view: "traces", sessionId: id })}
          />
        ) : (
          <SessionInbox
            onSelectSession={(id) => onNavigate({ view: "sessions", sessionId: id })}
            onOpenTraces={(id) => onNavigate({ view: "traces", sessionId: id })}
            onOpenAlumni={() => onNavigate({ view: "alumni" })}
          />
        ))}
    </>
  )
}
