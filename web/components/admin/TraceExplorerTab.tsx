"use client"

import { useEffect, useMemo, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"
import type { LLMWorkflowDetail, LLMWorkflowSummary } from "@/types/llm-observability"

interface TraceExplorerTabProps {
  initialSessionId?: string | null
}

function formatLatency(ms?: number | null): string {
  if (!ms) return "—"
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
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

function workflowStatusClass(status: string): string {
  if (status === "ok" || status === "analyzed" || status === "completed") return "bg-emerald-100 text-emerald-700"
  if (status === "started" || status === "analyzing") return "bg-amber-100 text-amber-800"
  if (status === "cancelled") return "bg-slate-100 text-slate-700"
  return "bg-rose-100 text-rose-700"
}

function renderKeyValueMap(data: Record<string, unknown>) {
  const entries = Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== "")
  if (entries.length === 0) return <p className="text-sm text-[var(--cl-muted)]">No evidence recorded for this section.</p>

  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3">
          <dt className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">{key.replace(/_/g, " ")}</dt>
          <dd className="mt-2 whitespace-pre-wrap text-sm text-[var(--cl-ink)]">
            {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export default function TraceExplorerTab({ initialSessionId = null }: TraceExplorerTabProps) {
  const [sessionId, setSessionId] = useState(initialSessionId ?? "")
  const [statusFilter, setStatusFilter] = useState("")
  const [limit, setLimit] = useState(25)
  const [workflows, setWorkflows] = useState<LLMWorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const [detail, setDetail] = useState<LLMWorkflowDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState("")

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
    if (statusFilter.trim()) params.set("status", statusFilter.trim())

    adminFetch(`/api/kb/workflow-summaries?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`workflow-summaries:${res.status}`)
        return res.json()
      })
      .then((data) => {
        if (cancelled) return
        const nextWorkflows = data as LLMWorkflowSummary[]
        setWorkflows(nextWorkflows)
        if (!selectedWorkflowId && nextWorkflows.length > 0) {
          setSelectedWorkflowId(nextWorkflows[0].workflow_id)
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load workflow summaries.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [limit, refreshKey, sessionId, statusFilter])

  useEffect(() => {
    if (!selectedWorkflowId) {
      setDetail(null)
      return
    }

    let cancelled = false
    setDetailLoading(true)
    setDetailError("")

    const params = new URLSearchParams()
    params.set("workflow_id", selectedWorkflowId)
    if (sessionId.trim()) params.set("session_id", sessionId.trim())

    adminFetch(`/api/kb/workflow-detail?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`workflow-detail:${res.status}`)
        return res.json()
      })
      .then((data) => {
        if (!cancelled) setDetail(data as LLMWorkflowDetail)
      })
      .catch(() => {
        if (!cancelled) setDetailError("Could not load workflow detail.")
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshKey, selectedWorkflowId, sessionId])

  useEffect(() => {
    const hasActiveWorkflow = workflows.some((workflow) => workflow.status === "started" || workflow.status === "analyzing")
    if (!hasActiveWorkflow) return
    const interval = window.setInterval(() => {
      setRefreshKey((value) => value + 1)
    }, 8000)
    return () => window.clearInterval(interval)
  }, [workflows])

  useEffect(() => {
    if (!detail || (detail.status !== "started" && detail.status !== "analyzing")) return
    const interval = window.setInterval(() => {
      setRefreshKey((value) => value + 1)
    }, 5000)
    return () => window.clearInterval(interval)
  }, [detail])

  const summary = useMemo(() => {
    const failures = workflows.filter((workflow) => workflow.status === "error" || workflow.status === "failed").length
    const active = workflows.filter((workflow) => workflow.status === "started" || workflow.status === "analyzing").length
    const repairs = workflows.filter((workflow) => workflow.repair_applied).length
    const sessions = new Set(workflows.map((workflow) => workflow.session_id).filter(Boolean)).size
    return { failures, active, repairs, total: workflows.length, sessions }
  }, [workflows])

  if (loading) {
    return (
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <ActionStatus size="md" label="Loading workflow summaries…" />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Trace explorer</p>
            <h2 className="mt-2 font-display text-3xl leading-tight text-[var(--cl-ink)]">Debug Workflow</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              Poll the lean workflow queue, then open one run at a time for session-scoped evidence about prompt provenance, repair, validation, and append behavior.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
            disabled={loading}
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-line)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] hover:border-[var(--cl-accent)] disabled:cursor-not-allowed disabled:opacity-40"
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
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Workflow runs</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.total}</p>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">In flight</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.active}</p>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Failed workflows</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.failures}</p>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Repair runs</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.repairs}</p>
          </div>
          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Sessions</p>
            <p className="mt-1 font-display text-2xl text-[var(--cl-ink)]">{summary.sessions}</p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-3">
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
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Status</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            >
              <option value="">All</option>
              <option value="ok">ok</option>
              <option value="started">started</option>
              <option value="error">error</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Limit</span>
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 25)}
              className="mt-2 w-full rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
            />
          </label>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)]">
        <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-2xl text-[var(--cl-ink)]">Workflow queue</h3>
              <p className="mt-1 text-sm text-[var(--cl-muted)]">Poll-friendly summary rows. Open one workflow at a time for full detail.</p>
            </div>
            <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
              {workflows.length} shown
            </span>
          </div>

          {workflows.length === 0 ? (
            <p className="text-sm text-[var(--cl-muted)]">No session-card workflows recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {workflows.map((workflow) => {
                const isSelected = workflow.workflow_id === selectedWorkflowId
                return (
                  <button
                    key={workflow.workflow_id}
                    type="button"
                    onClick={() => setSelectedWorkflowId(workflow.workflow_id)}
                    className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
                      isSelected
                        ? "border-[var(--cl-accent)] bg-[var(--cl-accent)]/5"
                        : "border-[var(--cl-line)] bg-white hover:border-[var(--cl-accent)]/50"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${workflowStatusClass(workflow.status)}`}>
                        {workflow.status}
                      </span>
                      {workflow.repair_applied && (
                        <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                          Repair applied
                        </span>
                      )}
                      {workflow.drop_point && (
                        <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--cl-muted)]">
                          {workflow.drop_point}
                        </span>
                      )}
                    </div>

                    <div className="mt-3">
                      <p className="font-display text-lg text-[var(--cl-ink)]">
                        {workflow.session_id ? `Session ${workflow.session_id.slice(0, 12)}` : workflow.workflow_name}
                      </p>
                      <p className="mt-1 text-sm text-[var(--cl-muted)]">
                        {workflow.prompt.prompt_name || "Prompt unavailable"}
                        {workflow.prompt.prompt_version ? ` · v${workflow.prompt.prompt_version}` : ""}
                        {workflow.prompt.prompt_label ? ` · ${workflow.prompt.prompt_label}` : ""}
                      </p>
                    </div>

                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Cards</p>
                        <p className="mt-1 text-sm text-[var(--cl-ink)]">
                          {workflow.card_counts.committed ?? workflow.card_counts.repaired ?? workflow.card_counts.raw ?? 0}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Started</p>
                        <p className="mt-1 text-sm text-[var(--cl-ink)]">{formatTimestamp(workflow.started_at)}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Duration</p>
                        <p className="mt-1 text-sm text-[var(--cl-ink)]">{formatLatency(workflow.duration_ms)}</p>
                      </div>
                    </div>

                    {workflow.failure_summary && (
                      <p className="mt-3 text-sm text-[var(--cl-error)]">{workflow.failure_summary}</p>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
          <div className="border-b border-[var(--cl-line)] pb-4">
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Workflow detail</p>
            <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">What happened</h3>
            <p className="mt-2 text-sm leading-6 text-[var(--cl-muted)]">
              Start with the plain-English story, then drop into prompt provenance, repair, validation, and append evidence.
            </p>
          </div>

          {detailLoading && (
            <div className="mt-5">
              <ActionStatus label="Loading workflow detail…" />
            </div>
          )}

          {detailError && (
            <div className="mt-5 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
              {detailError}
            </div>
          )}

          {!detailLoading && !detail && !detailError && (
            <p className="mt-5 text-sm text-[var(--cl-muted)]">No workflow recorded yet.</p>
          )}

          {detail && (
            <div className="mt-5 space-y-6">
              <section className="rounded-2xl border border-[var(--cl-line)] bg-white px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${workflowStatusClass(detail.status)}`}>
                    {detail.status}
                  </span>
                  {detail.drop_point && (
                    <span className="rounded-full bg-[var(--cl-surface-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--cl-muted)]">
                      Drop point: {detail.drop_point}
                    </span>
                  )}
                </div>
                <h4 className="mt-3 font-display text-2xl text-[var(--cl-ink)]">{detail.summary || "Workflow detail"}</h4>
                <p className="mt-3 text-sm leading-6 text-[var(--cl-ink)]">{detail.likely_cause || "No plain-English cause was recorded."}</p>
                <p className="mt-3 text-sm leading-6 text-[var(--cl-muted)]">{detail.recommended_action || "No next action recorded."}</p>
              </section>

              <section className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-5 py-4">
                <h4 className="font-display text-xl text-[var(--cl-ink)]">Technical details</h4>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Prompt</p>
                    <p className="mt-1 text-sm text-[var(--cl-ink)]">{detail.prompt.prompt_name || "Prompt version unavailable for this run"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Version</p>
                    <p className="mt-1 text-sm text-[var(--cl-ink)]">
                      {detail.prompt.prompt_version ? `v${detail.prompt.prompt_version}` : "Unavailable"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Source</p>
                    <p className="mt-1 text-sm text-[var(--cl-ink)]">{detail.prompt.prompt_source || "Unavailable"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Duration</p>
                    <p className="mt-1 text-sm text-[var(--cl-ink)]">{formatLatency(detail.duration_ms)}</p>
                  </div>
                </div>
              </section>

              <section>
                <h4 className="font-display text-xl text-[var(--cl-ink)]">Timeline</h4>
                <div className="mt-4 space-y-3">
                  {detail.steps.map((step) => (
                    <article key={step.step_id} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="font-medium text-[var(--cl-ink)]">{step.label}</p>
                          <p className="mt-1 text-xs text-[var(--cl-muted)]">
                            {formatTimestamp(step.started_at)} {step.duration_ms ? `· ${formatLatency(step.duration_ms)}` : ""}
                          </p>
                        </div>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${workflowStatusClass(step.status)}`}>
                          {step.status}
                        </span>
                      </div>
                      {step.detail && <p className="mt-3 text-sm text-[var(--cl-muted)]">{step.detail}</p>}
                    </article>
                  ))}
                </div>
              </section>

              <section className="space-y-4">
                <h4 className="font-display text-xl text-[var(--cl-ink)]">Evidence</h4>

                {detail.alumni_path && (
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Alumni path</p>
                    <div className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-3 text-sm text-[var(--cl-ink)]">
                      {detail.alumni_path}
                    </div>
                  </div>
                )}

                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Context pack</p>
                  {renderKeyValueMap(detail.context_pack_summary)}
                </div>

                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Repair</p>
                  {renderKeyValueMap(detail.repair_summary)}
                </div>

                {Object.keys(detail.raw_output_summary).length > 0 && (
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Raw output</p>
                    {renderKeyValueMap(detail.raw_output_summary)}
                  </div>
                )}

                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Parsed payload</p>
                  {renderKeyValueMap(detail.parsed_payload_summary)}
                </div>

                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Validation</p>
                  {renderKeyValueMap(detail.validation_summary)}
                </div>

                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--cl-muted)]">Append</p>
                  {renderKeyValueMap(detail.append_summary)}
                </div>
              </section>

              <section>
                <h4 className="font-display text-xl text-[var(--cl-ink)]">Scores</h4>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {detail.scores.map((score) => (
                    <article key={score.key} className="rounded-2xl border border-[var(--cl-line)] bg-white px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-[var(--cl-ink)]">{score.label}</p>
                        <span className="font-mono-display text-sm text-[var(--cl-muted)]">{String(score.value)}</span>
                      </div>
                      {score.rationale && <p className="mt-2 text-sm text-[var(--cl-muted)]">{score.rationale}</p>}
                    </article>
                  ))}
                </div>
              </section>

              {detail.limitations.length > 0 && (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
                  <h4 className="font-display text-xl text-amber-950">Known limitations</h4>
                  <ul className="mt-3 space-y-2 text-sm text-amber-900">
                    {detail.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
