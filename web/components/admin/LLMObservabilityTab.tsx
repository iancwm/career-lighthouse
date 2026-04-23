"use client"

import { useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import StatCards from "@/components/admin/StatCards"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"
import SourceStateSummary from "@/components/admin/SourceStateSummary"
import StaleSourceGuidanceModal from "@/components/admin/modals/StaleSourceGuidanceModal"

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

interface LLMTraceEntry {
  trace_id: string
  ts: string
  operation: string
  status: string
  model: string
  session_id?: string | null
  phase?: string | null
  chunk_index?: number | null
  chunk_count?: number | null
  multi_pass_threshold_chars?: number | null
  multi_pass_chunk_tokens?: number | null
  multi_pass_overlap_tokens?: number | null
  timeout_seconds: number | null
  max_tokens: number
  latency_ms: number
  input_chars: number
  output_chars: number
  input_preview: string
  output_preview: string
  error: string | null
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

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed)
}

function traceStatusClass(status: string): string {
  if (status === "ok") return "border-emerald-200 bg-emerald-100 text-emerald-700"
  if (status === "started") return "border-sky-200 bg-sky-100 text-sky-700"
  return "border-rose-200 bg-rose-100 text-rose-700"
}

function traceStatusLabel(status: string): string {
  if (status === "ok") return "Completed"
  if (status === "started") return "In flight"
  return "Error"
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

function TraceTable({ traces }: { traces: LLMTraceEntry[] }) {
  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="flex flex-col gap-2 border-b border-[var(--cl-line)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Trace evidence</p>
          <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Recent LLM traces</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
            Newest last. Started rows stay visible while a request is still in flight.
          </p>
        </div>
        <p className="text-sm text-[var(--cl-muted)]">{traces.length} rows</p>
      </div>

      {traces.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--cl-muted)]">No LLM traces recorded yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--cl-line)]">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-[var(--cl-surface-2)]">
                <tr className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">
                  <th className="px-4 py-3 font-mono-display">Time</th>
                  <th className="px-4 py-3 font-mono-display">Operation</th>
                  <th className="px-4 py-3 font-mono-display">Status</th>
                  <th className="px-4 py-3 font-mono-display">Model</th>
                  <th className="px-4 py-3 font-mono-display">Latency</th>
                  <th className="px-4 py-3 font-mono-display">Session</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((trace, index) => (
                  <tr
                    key={`${trace.trace_id}-${trace.status}-${trace.ts}-${index}`}
                    className="border-t border-[var(--cl-line)] bg-[var(--cl-surface)]"
                  >
                    <td className="px-4 py-4 align-top text-sm text-[var(--cl-ink)]">{formatTimestamp(trace.ts)}</td>
                    <td className="px-4 py-4 align-top">
                      <div className="space-y-2">
                        <p className="font-medium text-[var(--cl-ink)]">{trace.operation}</p>
                        <p className="text-xs leading-5 text-[var(--cl-muted)]">
                          {trace.phase ?? "No phase"}
                          {trace.chunk_index && trace.chunk_count ? ` · chunk ${trace.chunk_index}/${trace.chunk_count}` : ""}
                        </p>
                        {(trace.multi_pass_threshold_chars || trace.multi_pass_chunk_tokens || trace.multi_pass_overlap_tokens) && (
                          <p className="text-xs leading-5 text-[var(--cl-muted)]">
                            {trace.multi_pass_threshold_chars ? `threshold ${trace.multi_pass_threshold_chars} chars` : ""}
                            {trace.multi_pass_threshold_chars && trace.multi_pass_chunk_tokens ? " · " : ""}
                            {trace.multi_pass_chunk_tokens ? `chunk ${trace.multi_pass_chunk_tokens} tokens` : ""}
                            {(trace.multi_pass_threshold_chars || trace.multi_pass_chunk_tokens) && trace.multi_pass_overlap_tokens ? " · " : ""}
                            {trace.multi_pass_overlap_tokens !== undefined && trace.multi_pass_overlap_tokens !== null
                              ? `overlap ${trace.multi_pass_overlap_tokens} tokens`
                              : ""}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${traceStatusClass(trace.status)}`}>
                        {traceStatusLabel(trace.status)}
                      </span>
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--cl-ink)]">{trace.model}</td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--cl-ink)]">
                      {formatLatency(trace.latency_ms)}
                      <div className="mt-1 text-xs text-[var(--cl-muted)]">
                        {trace.timeout_seconds ? `timeout ${trace.timeout_seconds}s` : "No timeout"}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--cl-ink)]">
                      {trace.session_id ? <span className="font-mono-display">{trace.session_id.slice(0, 12)}</span> : "Unknown"}
                      <div className="mt-1 text-xs text-[var(--cl-muted)]">
                        {trace.input_chars} in · {trace.output_chars} out
                      </div>
                      {trace.error && <p className="mt-1 text-xs text-[var(--cl-error)]">{trace.error}</p>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

export default function LLMObservabilityTab() {
  const [health, setHealth] = useState<KBHealthView | null>(null)
  const [traces, setTraces] = useState<LLMTraceEntry[]>([])
  const [loading, setLoading] = useState(true)
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
      adminFetch("/api/kb/llm-traces?limit=25").then(async (res) => {
        if (!res.ok) throw new Error(`traces:${res.status}`)
        return res.json()
      }),
    ])
      .then(([healthData, traceData]) => {
        if (cancelled) return
        setHealth(normalizeHealth(healthData as KBHealthResponse))
        setTraces((traceData as LLMTraceEntry[]).slice().reverse())
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

  const staleEvidence = health?.sourceState.staleEvidence ?? []

  if (loading && !health) {
    return (
      <section className="space-y-4">
        <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">LLM observability</p>
          <div className="mt-3 h-8 w-56 rounded bg-[var(--cl-surface-2)]" />
          <div className="mt-4 h-4 w-80 rounded bg-[var(--cl-surface-2)]" />
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <div className="h-32 rounded-3xl bg-[var(--cl-surface-2)]" />
            <div className="h-32 rounded-3xl bg-[var(--cl-surface-2)]" />
            <div className="h-32 rounded-3xl bg-[var(--cl-surface-2)]" />
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
              This view shows Langfuse-backed trace data, KB health, and the source-state ledger, with a JSONL fallback only when Langfuse is unavailable.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-line)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
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

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="space-y-4">
              <DocCoverageList docs={health.doc_coverage} />
              <StaleSourceEvidencePanel evidence={staleEvidence} />
              {health.high_overlap_pairs.length > 0 && <RedundancyPanel pairs={health.high_overlap_pairs} />}
            </div>
            <LowConfidenceLog avgMatchScore={health.avg_match_score} queries={health.low_confidence_queries} />
          </div>

          <TraceTable traces={traces} />
        </div>
      )}

      {!health && !error && (
        <p className="text-sm text-[var(--cl-muted)]">No observability data available yet.</p>
      )}
      {!health && error && (
        <p className="text-sm text-[var(--cl-muted)]">Refresh once the backend is available again.</p>
      )}

      {showStaleGuidance && (
        <StaleSourceGuidanceModal evidence={staleEvidence} onClose={() => setShowStaleGuidance(false)} />
      )}
    </section>
  )
}
