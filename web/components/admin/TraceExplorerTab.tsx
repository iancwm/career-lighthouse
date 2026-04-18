"use client"

import { useEffect, useMemo, useState } from "react"
import { adminFetch } from "@/lib/admin-api"

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

interface TraceExplorerTabProps {
  initialSessionId?: string | null
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

export default function TraceExplorerTab({ initialSessionId = null }: TraceExplorerTabProps) {
  const [sessionId, setSessionId] = useState(initialSessionId ?? "")
  const [operationFilter, setOperationFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [limit, setLimit] = useState(50)
  const [traces, setTraces] = useState<LLMTraceEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    setSessionId(initialSessionId ?? "")
  }, [initialSessionId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")

    const params = new URLSearchParams()
    params.set("limit", String(Math.min(Math.max(limit, 1), 200)))
    if (sessionId.trim()) params.set("session_id", sessionId.trim())
    if (operationFilter.trim()) params.set("operation", operationFilter.trim())
    if (statusFilter.trim()) params.set("status", statusFilter.trim())

    adminFetch(`/api/kb/llm-traces?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`traces:${res.status}`)
        return res.json()
      })
      .then((data) => {
        if (cancelled) return
        setTraces((data as LLMTraceEntry[]).slice().reverse())
      })
      .catch(() => {
        if (!cancelled) setError("Could not load traces.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshKey, sessionId, operationFilter, statusFilter, limit])

  useEffect(() => {
    if (!sessionId.trim()) return
    const interval = window.setInterval(() => {
      setRefreshKey((value) => value + 1)
    }, 8000)
    return () => window.clearInterval(interval)
  }, [sessionId])

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
    const sessions = new Set(traces.map((trace) => trace.session_id).filter(Boolean)).size
    return { failures, active, slowest, total: latestRuns.length, sessions }
  }, [traces])

  if (loading) {
    return <p className="text-sm text-[var(--cl-muted)]">Loading traces…</p>
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Trace explorer</p>
            <h2 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)]">Session-scoped LLM debugging</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              Filter traces by session, operation, or status. Started rows appear immediately, so you can watch active runs before they fail or finish.
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

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
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
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Sessions</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.sessions}</p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-4">
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Session ID</span>
            <input
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="Optional session filter"
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Operation</span>
            <input
              value={operationFilter}
              onChange={(e) => setOperationFilter(e.target.value)}
              placeholder="generate_session_intents"
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Status</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            >
              <option value="">All</option>
              <option value="started">started</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Limit</span>
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 50)}
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            />
          </label>
        </div>

        {sessionId.trim() && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[var(--cl-accent)]/10 px-3 py-1 text-xs font-medium text-[var(--cl-accent)]">
              Filtered to session {sessionId.trim().slice(0, 12)}
            </span>
            <button
              type="button"
              onClick={() => setSessionId("")}
              className="rounded-full border border-[var(--cl-line)] px-3 py-1 text-xs font-medium text-[var(--cl-ink)] hover:border-[var(--cl-accent)]"
            >
              Clear session filter
            </button>
          </div>
        )}
      </div>

      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-2xl text-[var(--cl-ink)]">Recent traces</h3>
            <p className="mt-1 text-sm text-[var(--cl-muted)]">Newest last. Started traces stay visible while work is in flight.</p>
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
                    {trace.error && <p className="text-[var(--cl-error)]">Error: {trace.error}</p>}
                  </div>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl bg-[var(--cl-surface-2)] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--cl-muted)]">Input preview</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--cl-ink)]">
                      {trace.input_preview || "—"}
                    </p>
                  </div>
                  <div className="rounded-xl bg-[var(--cl-surface-2)] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--cl-muted)]">Output preview</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--cl-ink)]">
                      {trace.output_preview || "—"}
                    </p>
                  </div>
                </div>

                <p className="mt-3 text-xs text-[var(--cl-muted)]">
                  Trace ID: <span className="font-mono">{trace.trace_id.slice(0, 12)}</span>
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
