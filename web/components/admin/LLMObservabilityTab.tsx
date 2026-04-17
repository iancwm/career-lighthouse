"use client"

import { useEffect, useMemo, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import StatCards from "@/components/admin/StatCards"
import DocCoverageList from "@/components/admin/DocCoverageList"
import LowConfidenceLog from "@/components/admin/LowConfidenceLog"
import RedundancyPanel from "@/components/admin/RedundancyPanel"

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

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function traceStatusClass(status: string): string {
  if (status === "ok") return "bg-emerald-100 text-emerald-700"
  if (status === "started") return "bg-sky-100 text-sky-700"
  return "bg-rose-100 text-rose-700"
}

export default function LLMObservabilityTab() {
  const [health, setHealth] = useState<KBHealth | null>(null)
  const [traces, setTraces] = useState<LLMTraceEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [refreshKey, setRefreshKey] = useState(0)

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
        setHealth(healthData as KBHealth)
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

  const summary = useMemo(() => {
    const latestByTrace = new Map<string, LLMTraceEntry>()
    for (const trace of traces) {
      const current = latestByTrace.get(trace.trace_id)
      if (!current || new Date(trace.ts).getTime() >= new Date(current.ts).getTime()) {
        latestByTrace.set(trace.trace_id, trace)
      }
    }

    const latestRuns = Array.from(latestByTrace.values())
    const failures = latestRuns.filter((trace) => trace.status === "error").length
    const active = latestRuns.filter((trace) => trace.status === "started").length
    const slowest = traces.reduce((max, trace) => Math.max(max, trace.latency_ms), 0)
    return { failures, active, slowest, total: latestRuns.length }
  }, [traces])

  if (loading) {
    return <p className="text-sm text-[var(--cl-muted)]">Loading observability…</p>
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">LLM observability</p>
            <h2 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)]">Trace every call</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              This view shows the local JSONL trace log, KB health, and Qdrant retrieval signals. It is the first step toward a Langfuse-backed workflow.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
            className="rounded-full border border-[var(--cl-line)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] hover:border-[var(--cl-accent)]"
          >
            Refresh
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
            {error}
          </div>
        )}

        {health && (
          <div className="mt-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Trace runs</p>
                <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.total}</p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">In flight</p>
                <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.active}</p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Failed runs</p>
                <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.failures}</p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Slowest trace</p>
                <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.slowest ? formatLatency(summary.slowest) : "—"}</p>
              </div>
              <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Weak queries</p>
                <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{health.low_confidence_queries.length}</p>
              </div>
            </div>

            <div className="mt-4">
              <StatCards
                totalDocs={health.total_docs}
                totalChunks={health.total_chunks}
                lowConfidenceCount={health.low_confidence_queries.length}
                avgMatchScore={health.avg_match_score}
                diversityScore={health.retrieval_diversity_score}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <DocCoverageList docs={health.doc_coverage} />
              <LowConfidenceLog avgMatchScore={health.avg_match_score} queries={health.low_confidence_queries} />
            </div>

            {health.high_overlap_pairs.length > 0 && (
              <div className="mt-4">
                <RedundancyPanel pairs={health.high_overlap_pairs} />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-2xl text-[var(--cl-ink)]">Recent LLM traces</h3>
            <p className="mt-1 text-sm text-[var(--cl-muted)]">Structured local traces from the API. Use these to debug prompt drift, timeouts, and malformed outputs.</p>
            <p className="mt-1 text-xs text-[var(--cl-muted)]">Each call emits a `started` row immediately and a terminal `ok` or `error` row when it finishes.</p>
          </div>
          <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
            newest last
          </span>
        </div>

        {traces.length === 0 ? (
          <p className="text-sm text-[var(--cl-muted)]">No LLM traces recorded yet.</p>
        ) : (
          <div className="space-y-3">
            {traces.map((trace) => (
              <article key={trace.trace_id} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-4 shadow-[0_8px_18px_rgba(31,41,55,0.04)]">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="font-display text-lg text-[var(--cl-ink)]">{trace.operation}</h4>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${traceStatusClass(trace.status)}`}>
                        {trace.status}
                      </span>
                      <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-0.5 text-xs font-mono text-[var(--cl-muted)]">
                        {trace.model}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--cl-muted)]">
                      {new Date(trace.ts).toLocaleString()} · {formatLatency(trace.latency_ms)} · {trace.max_tokens} max tokens
                      {trace.timeout_seconds ? ` · timeout ${trace.timeout_seconds}s` : ""}
                    </p>
                    {(trace.session_id || trace.phase || trace.chunk_index || trace.chunk_count) && (
                      <p className="mt-1 text-xs text-[var(--cl-muted)]">
                        {trace.session_id ? `session ${trace.session_id.slice(0, 8)}` : ""}
                        {trace.session_id && trace.phase ? " · " : ""}
                        {trace.phase ?? ""}
                        {trace.chunk_index && trace.chunk_count ? ` · chunk ${trace.chunk_index}/${trace.chunk_count}` : ""}
                      </p>
                    )}
                    {(trace.multi_pass_threshold_chars || trace.multi_pass_chunk_tokens || trace.multi_pass_overlap_tokens) && (
                      <p className="mt-1 text-xs text-[var(--cl-muted)]">
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

                  <div className="grid gap-2 text-right text-xs text-[var(--cl-muted)] lg:min-w-56">
                    <p>Input: {trace.input_chars} chars</p>
                    <p>Output: {trace.output_chars} chars</p>
                    <p>Trace ID: <span className="font-mono">{trace.trace_id.slice(0, 12)}</span></p>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Input preview</p>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-[var(--cl-surface-2)] p-3 text-xs leading-6 text-[var(--cl-ink)]">
                      {trace.input_preview || "—"}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Output preview</p>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-[var(--cl-surface-2)] p-3 text-xs leading-6 text-[var(--cl-ink)]">
                      {trace.error || trace.output_preview || "—"}
                    </pre>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
