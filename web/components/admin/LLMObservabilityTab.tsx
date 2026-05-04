"use client"

import { useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import StatCards from "@/components/admin/StatCards"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"
import SourceStateSummary from "@/components/admin/SourceStateSummary"
import StaleSourceGuidanceModal from "@/components/admin/modals/StaleSourceGuidanceModal"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"
import type { LLMWorkflowDetail, LLMWorkflowSummary } from "@/types/llm-observability"

interface LowConfidenceQuery {
  ts: string
  query_text: string
  max_score: number
  doc_matched: string | null
}

interface DocCoverageItem {
  filename: string
  chunk_count: number
  coverage_status: "good" | "thin"
  has_overlap_warning: boolean
}

interface OverlapPair {
  doc_a: string
  doc_b: string
  overlap_pct: number
  recommendation: string
}

interface StaleSourceEvidence {
  filename: string
  reason: string
  chunk_count?: number | null
  last_seen_at?: string | null
}

interface SourceStatePayload {
  active_sources?: number | null
  active_source_count?: number | null
  superseded_sources?: number | null
  superseded_source_count?: number | null
  stale_sources?: number | null
  stale_source_count?: number | null
  active_hits?: number | null
  active_hit_count?: number | null
  superseded_hits?: number | null
  superseded_hit_count?: number | null
  last_refreshed_at?: string | null
  updated_at?: string | null
  stale_source_evidence?: StaleSourceEvidence[]
}

interface KBHealthResponse {
  total_docs: number
  total_chunks: number
  avg_match_score: number | null
  retrieval_diversity_score: number | null
  low_confidence_queries: LowConfidenceQuery[]
  doc_coverage: DocCoverageItem[]
  high_overlap_pairs: OverlapPair[]
  source_state?: SourceStatePayload
  active_sources?: number | null
  active_source_count?: number | null
  superseded_sources?: number | null
  superseded_source_count?: number | null
  stale_sources?: number | null
  stale_source_count?: number | null
  active_hits?: number | null
  active_hit_count?: number | null
  superseded_hits?: number | null
  superseded_hit_count?: number | null
  last_refreshed_at?: string | null
  updated_at?: string | null
  stale_source_evidence?: StaleSourceEvidence[]
}

interface SourceStateView {
  activeCount: number | null
  supersededCount: number | null
  staleCount: number | null
  activeHitCount: number | null
  supersededHitCount: number | null
  lastRefreshedAt: string | null
  staleEvidence: StaleSourceEvidence[]
}

interface KBHealthView extends Omit<KBHealthResponse, "source_state"> {
  sourceState: SourceStateView
}

function normalizeSourceState(health: KBHealthResponse): SourceStateView {
  const sourceState = health.source_state ?? health
  return {
    activeCount: sourceState.active_sources ?? sourceState.active_source_count ?? null,
    supersededCount: sourceState.superseded_sources ?? sourceState.superseded_source_count ?? null,
    staleCount: sourceState.stale_sources ?? sourceState.stale_source_count ?? null,
    activeHitCount: sourceState.active_hits ?? sourceState.active_hit_count ?? null,
    supersededHitCount: sourceState.superseded_hits ?? sourceState.superseded_hit_count ?? null,
    lastRefreshedAt: sourceState.last_refreshed_at ?? sourceState.updated_at ?? null,
    staleEvidence: sourceState.stale_source_evidence ?? [],
  }
}

function normalizeHealth(payload: KBHealthResponse): KBHealthView {
  const { source_state, ...rest } = payload
  return {
    ...rest,
    sourceState: normalizeSourceState(payload),
  }
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed)
}

function WorkflowWatchList({
  workflows,
  selectedWorkflowId,
  detail,
  detailLoading,
  onSelect,
}: {
  workflows: LLMWorkflowSummary[]
  selectedWorkflowId: string | null
  detail: LLMWorkflowDetail | null
  detailLoading: boolean
  onSelect: (workflowId: string) => void
}) {
  const cardCount = (workflow: Partial<LLMWorkflowSummary>) =>
    workflow.card_counts?.committed ?? workflow.card_counts?.repaired ?? workflow.card_counts?.raw ?? 0
  const failures = workflows.filter((workflow) => workflow.status === "error" || workflow.status === "failed").length
  const repairRuns = workflows.filter((workflow) => workflow.repair_applied).length
  const missingCards = workflows.filter((workflow) => cardCount(workflow) === 0).length

  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="flex flex-col gap-3 border-b border-[var(--cl-line)] pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Workflow queue</p>
          <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Session-card health</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
            Poll-friendly summaries first. Open one workflow to inspect the underlying repair, validation, and append story.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-3 py-2 text-sm text-[var(--cl-ink)]">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Failed workflows</span>
            <div className="mt-1 font-display text-2xl">{failures}</div>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-3 py-2 text-sm text-[var(--cl-ink)]">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Repair runs</span>
            <div className="mt-1 font-display text-2xl">{repairRuns}</div>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-3 py-2 text-sm text-[var(--cl-ink)]">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Zero-card runs</span>
            <div className="mt-1 font-display text-2xl">{missingCards}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="space-y-3">
          {workflows.length === 0 ? (
            <p className="text-sm text-[var(--cl-muted)]">No workflow summaries recorded yet.</p>
          ) : (
            workflows.map((workflow) => {
              const cards = cardCount(workflow)
              const selected = workflow.workflow_id === selectedWorkflowId
              return (
                <button
                  key={workflow.workflow_id}
                  type="button"
                  onClick={() => onSelect(workflow.workflow_id)}
                  className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
                    selected
                      ? "border-[var(--cl-accent)] bg-[var(--cl-accent)]/5"
                      : "border-[var(--cl-line)] bg-white hover:border-[var(--cl-accent)]/40"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--cl-muted)]">
                      {workflow.status}
                    </span>
                    {workflow.repair_applied && (
                      <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                        Repair applied
                      </span>
                    )}
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                      {cards} cards
                    </span>
                  </div>
                  <p className="mt-3 font-medium text-[var(--cl-ink)]">
                    {workflow.session_id ? `Session ${workflow.session_id.slice(0, 12)}` : workflow.workflow_name}
                  </p>
                  <p className="mt-1 text-sm text-[var(--cl-muted)]">
                    {workflow.prompt.prompt_name || "Prompt unavailable"}
                    {workflow.prompt.prompt_version ? ` · v${workflow.prompt.prompt_version}` : ""}
                  </p>
                  {workflow.failure_summary && (
                    <p className="mt-2 text-sm text-[var(--cl-error)]">{workflow.failure_summary}</p>
                  )}
                </button>
              )
            })
          )}
        </div>

        <div className="rounded-2xl border border-[var(--cl-line)] bg-white px-5 py-4">
          <h4 className="font-display text-xl text-[var(--cl-ink)]">Open detail</h4>
          {detailLoading && (
            <div className="mt-4">
              <ActionStatus label="Loading workflow detail…" />
            </div>
          )}
          {!detailLoading && !detail && (
            <p className="mt-4 text-sm text-[var(--cl-muted)]">Pick a workflow summary to open its detail panel.</p>
          )}
          {detail && !detailLoading && (
            <div className="mt-4 space-y-3 text-sm">
              <p className="font-medium text-[var(--cl-ink)]">{detail.summary}</p>
              <p className="text-[var(--cl-muted)]">{detail.likely_cause}</p>
              <p className="text-[var(--cl-muted)]">{detail.recommended_action}</p>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Prompt provenance</p>
                <p className="mt-2 text-[var(--cl-ink)]">
                  {detail.prompt.prompt_name || "Prompt version unavailable for this run"}
                  {detail.prompt.prompt_version ? ` · v${detail.prompt.prompt_version}` : ""}
                  {detail.prompt.prompt_source ? ` · ${detail.prompt.prompt_source}` : ""}
                </p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Model</p>
                <p className="mt-2 text-[var(--cl-ink)]">{detail.model || "Unavailable"}</p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Timeline</p>
                <p className="mt-2 text-[var(--cl-ink)]">
                  {detail.steps.map((step) => step.label).join(" → ") || "No steps recorded"}
                </p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Started</p>
                <p className="mt-2 text-[var(--cl-ink)]">{formatTimestamp(detail.started_at)}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function StaleSourceEvidencePanel({ evidence }: { evidence: StaleSourceEvidence[] }) {
  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="border-b border-[var(--cl-line)] pb-4">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Stale evidence</p>
        <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Lingering old chunks</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
          These items still exist in the vector index, but the source ledger says they are no longer current.
        </p>
      </div>

      {evidence.length === 0 ? (
        <p className="mt-4 text-sm text-[#2F6B4F]">No stale-source evidence detected yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {evidence.map((item) => (
            <li key={`${item.filename}-${item.last_seen_at ?? item.reason}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium text-[var(--cl-ink)]">{item.filename}</p>
                  <p className="mt-1 text-sm leading-6 text-[var(--cl-muted)]">{item.reason}</p>
                </div>
                <div className="text-sm text-[var(--cl-muted)] sm:text-right">
                  <p>
                    <span className="font-mono-display text-[var(--cl-ink)]">{item.chunk_count ?? "Unknown"}</span> chunks
                  </p>
                  <p>{item.last_seen_at ? formatTimestamp(item.last_seen_at) : "Last seen Unknown"}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function LLMObservabilityTab() {
  const [health, setHealth] = useState<KBHealthView | null>(null)
  const [workflows, setWorkflows] = useState<LLMWorkflowSummary[]>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const [detail, setDetail] = useState<LLMWorkflowDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState("")
  const [refreshKey, setRefreshKey] = useState(0)
  const [showStaleGuidance, setShowStaleGuidance] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")

    Promise.all([
      adminFetch("/api/kb/health").then(async (res) => {
        if (!res.ok) throw new Error(`health:${res.status}`)
        return res.json()
      }),
      adminFetch("/api/kb/workflow-summaries?limit=12").then(async (res) => {
        if (!res.ok) throw new Error(`workflows:${res.status}`)
        return res.json()
      }),
    ])
      .then(([healthData, workflowData]) => {
        if (cancelled) return
        const nextWorkflows = workflowData as LLMWorkflowSummary[]
        setHealth(normalizeHealth(healthData as KBHealthResponse))
        setWorkflows(nextWorkflows)
        setSelectedWorkflowId((current) => current ?? nextWorkflows[0]?.workflow_id ?? null)
      })
      .catch(() => {
        if (!cancelled) setError("Could not load observability data.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshKey])

  useEffect(() => {
    if (!selectedWorkflowId) {
      setDetail(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)

    adminFetch(`/api/kb/workflow-detail?workflow_id=${selectedWorkflowId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`detail:${res.status}`)
        return res.json()
      })
      .then((payload) => {
        if (!cancelled) setDetail(payload as LLMWorkflowDetail)
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedWorkflowId])

  const staleEvidence = health?.sourceState.staleEvidence ?? []

  if (loading && !health) {
    return (
      <section className="space-y-4">
        <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">LLM observability</p>
          <div className="mt-4">
            <ActionStatus size="md" label="Loading observability data…" />
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">LLM observability</p>
            <h2 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)]">Trace every call</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              This view combines KB health with session-card workflow summaries so you can spot broken runs quickly, then open one workflow for its debug story.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
            disabled={loading}
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-line)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Refresh
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
            {error}
          </div>
        )}
      </div>

      {health && (
        <div className="space-y-6">
          <SourceStateSummary
            activeCount={health.sourceState.activeCount}
            supersededCount={health.sourceState.supersededCount}
            staleCount={health.sourceState.staleCount}
            activeHitCount={health.sourceState.activeHitCount}
            supersededHitCount={health.sourceState.supersededHitCount}
            lastRefreshedAt={health.sourceState.lastRefreshedAt}
            loading={loading}
            onExplainStaleSources={() => setShowStaleGuidance(true)}
          />

          <StatCards
            totalDocs={health.total_docs}
            totalChunks={health.total_chunks}
            lowConfidenceCount={health.low_confidence_queries.length}
            avgMatchScore={health.avg_match_score}
            diversityScore={health.retrieval_diversity_score}
          />

          <WorkflowWatchList
            workflows={workflows}
            selectedWorkflowId={selectedWorkflowId}
            detail={detail}
            detailLoading={detailLoading}
            onSelect={setSelectedWorkflowId}
          />

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="space-y-4">
              <DocCoverageList docs={health.doc_coverage} />
              <StaleSourceEvidencePanel evidence={staleEvidence} />
              {health.high_overlap_pairs.length > 0 && <RedundancyPanel pairs={health.high_overlap_pairs} />}
            </div>
            <LowConfidenceLog avgMatchScore={health.avg_match_score} queries={health.low_confidence_queries} />
          </div>
        </div>
      )}

      {showStaleGuidance && (
        <StaleSourceGuidanceModal evidence={staleEvidence} onClose={() => setShowStaleGuidance(false)} />
      )}
    </section>
  )
}
