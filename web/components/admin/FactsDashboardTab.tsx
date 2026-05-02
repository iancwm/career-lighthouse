"use client"

import { FormEvent, useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import FactCard from "@/components/admin/forms/FactCard"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"
import { Fact, getFactTypeLabel, isActiveFact, sortFactsForDisplay } from "@/types/facts"

type GroupBy = "employer" | "type"

interface FactQueryResponse {
  facts: Fact[]
  total: number
  filters_applied?: Record<string, unknown>
}

interface FactGroupResponse {
  by: GroupBy
  groups: Record<string, Fact[]>
  total: number
  filters_applied?: Record<string, unknown>
}

interface DashboardState {
  status: "idle" | "loading" | "ready" | "empty" | "error"
  error: string
}

function summaryCard(label: string, value: string | number, caption?: string) {
  return (
    <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-4 shadow-[0_12px_24px_rgba(31,41,55,0.05)]">
      <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-muted)]">{label}</p>
      <p className="mt-2 font-display text-3xl text-[var(--cl-ink)]">{value}</p>
      {caption && <p className="mt-1 text-sm text-[var(--cl-muted)]">{caption}</p>}
    </div>
  )
}

export default function FactsDashboardTab() {
  const [type, setType] = useState("")
  const [employer, setEmployer] = useState("")
  const [school, setSchool] = useState("")
  const [source, setSource] = useState("")
  const [confidenceMin, setConfidenceMin] = useState("")
  const [groupBy, setGroupBy] = useState<GroupBy>("employer")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [facts, setFacts] = useState<Fact[]>([])
  const [groups, setGroups] = useState<Record<string, Fact[]>>({})
  const [total, setTotal] = useState(0)
  const [state, setState] = useState<DashboardState>({ status: "idle", error: "" })

  const buildFilters = (next?: {
    type?: string
    employer?: string
    school?: string
    source?: string
    confidenceMin?: string
    includeDeleted?: boolean
  }) => {
    const params: Record<string, string> = {}
    const nextType = (next?.type ?? type).trim()
    const nextEmployer = (next?.employer ?? employer).trim()
    const nextSchool = (next?.school ?? school).trim()
    const nextSource = (next?.source ?? source).trim()
    const nextConfidence = (next?.confidenceMin ?? confidenceMin).trim()
    const nextIncludeDeleted = next?.includeDeleted ?? includeDeleted

    if (nextType) params.type = nextType
    if (nextEmployer) params.employer = nextEmployer
    if (nextSchool) params.school = nextSchool
    if (nextSource) params.source = nextSource
    if (nextConfidence) params.confidence__gte = nextConfidence
    if (nextIncludeDeleted) params.include_deleted = "true"
    return params
  }

  async function loadFacts(next?: {
    type?: string
    employer?: string
    school?: string
    source?: string
    confidenceMin?: string
    includeDeleted?: boolean
    groupBy?: GroupBy
  }) {
    setState({ status: "loading", error: "" })

    const filters = buildFilters(next)
    const params = new URLSearchParams(filters)
    const groupedParams = new URLSearchParams({ ...filters, by: next?.groupBy ?? groupBy })

    try {
      const [factsResponse, groupedResponse] = await Promise.all([
        adminFetch(`/api/kb/facts${params.toString() ? `?${params.toString()}` : ""}`),
        adminFetch(`/api/kb/facts/grouped?${groupedParams.toString()}`),
      ])

      if (!factsResponse.ok || !groupedResponse.ok) {
        throw new Error("Unable to load facts dashboard.")
      }

      const factsData = (await factsResponse.json()) as FactQueryResponse
      const groupedData = (await groupedResponse.json()) as FactGroupResponse

      const nextFacts = factsData.facts ?? []
      setFacts(nextFacts)
      setGroups(groupedData.groups ?? {})
      setTotal(factsData.total ?? nextFacts.length)
      setState({
        status: nextFacts.length > 0 ? "ready" : "empty",
        error: "",
      })
    } catch (error) {
      setFacts([])
      setGroups({})
      setTotal(0)
      setState({
        status: "error",
        error: error instanceof Error && error.message ? error.message : "Unable to load facts dashboard.",
      })
    }
  }

  useEffect(() => {
    void loadFacts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await loadFacts()
  }

  function resetFilters() {
    setType("")
    setEmployer("")
    setSchool("")
    setSource("")
    setConfidenceMin("")
    setIncludeDeleted(false)
    void loadFacts({
      type: "",
      employer: "",
      school: "",
      source: "",
      confidenceMin: "",
      includeDeleted: false,
      groupBy,
    })
  }

  const activeFacts = facts.filter((fact) => isActiveFact(fact))
  const groupedEntries = Object.entries(groups).sort((a, b) => b[1].length - a[1].length)

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Smart Counsellor</p>
        <h2 className="mt-2 font-display text-3xl text-[var(--cl-ink)]">Facts Dashboard</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--cl-muted)]">
          Review structured facts captured from employer and profile YAMLs, then spot what is well-covered and what still needs counselor review.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
            <div className="flex flex-col gap-1">
              <label htmlFor="facts-type" className="text-xs font-medium text-[var(--cl-muted)]">Type</label>
              <input
                id="facts-type"
                value={type}
                onChange={(event) => setType(event.target.value)}
                placeholder="alumni"
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="facts-employer" className="text-xs font-medium text-[var(--cl-muted)]">Employer</label>
              <input
                id="facts-employer"
                value={employer}
                onChange={(event) => setEmployer(event.target.value)}
                placeholder="stripe"
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="facts-school" className="text-xs font-medium text-[var(--cl-muted)]">School</label>
              <input
                id="facts-school"
                value={school}
                onChange={(event) => setSchool(event.target.value)}
                placeholder="NUS"
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="facts-source" className="text-xs font-medium text-[var(--cl-muted)]">Source</label>
              <input
                id="facts-source"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                placeholder="direct_from_alumni"
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="facts-confidence" className="text-xs font-medium text-[var(--cl-muted)]">Min confidence</label>
              <input
                id="facts-confidence"
                value={confidenceMin}
                onChange={(event) => setConfidenceMin(event.target.value)}
                inputMode="numeric"
                placeholder="80"
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-[var(--cl-muted)]">
              <input
                type="checkbox"
                checked={includeDeleted}
                onChange={(event) => setIncludeDeleted(event.target.checked)}
                className="h-4 w-4 rounded border-[var(--cl-line)]"
              />
              Include deleted facts
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--cl-muted)]">
              <span>Group by</span>
              <select
                value={groupBy}
                onChange={(event) => setGroupBy(event.target.value as GroupBy)}
                className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
              >
                <option value="employer">Employer</option>
                <option value="type">Type</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={state.status === "loading"}
              className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {state.status === "loading" ? <ActionStatus variant="on-dark" label="Loading…" /> : "Refresh facts"}
            </button>
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-full border border-[var(--cl-line)] bg-white/70 px-5 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
            >
              Clear filters
            </button>
          </div>
        </form>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {summaryCard("Total facts", total, "Includes matching active and deleted records when requested")}
        {summaryCard("Active facts", activeFacts.length, "Deleted and superseded records are filtered by default")}
        {summaryCard("Buckets", Object.keys(groups).length, `Grouped by ${groupBy}`)}
      </div>

      {state.status === "loading" && (
        <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6">
          <ActionStatus size="md" label="Loading facts…" />
        </div>
      )}

      {state.status === "error" && (
        <div className="rounded-3xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 p-6 text-sm text-[var(--cl-error)]">
          {state.error}
        </div>
      )}

      {state.status !== "error" && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="space-y-6">
            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-display text-2xl text-[var(--cl-ink)]">Grouped facts</h3>
                  <p className="mt-1 text-sm text-[var(--cl-muted)]">Grouped by {groupBy} so you can spot coverage gaps quickly.</p>
                </div>
                <span className="rounded-full bg-[var(--cl-surface-2)] px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
                  {groupedEntries.length} groups
                </span>
              </div>

              {groupedEntries.length === 0 ? (
                <p className="text-sm text-[var(--cl-muted)]">No grouped facts to show.</p>
              ) : (
                <div className="space-y-4">
                  {groupedEntries.map(([bucket, bucketFacts]) => {
                    const displayFacts = sortFactsForDisplay(bucketFacts)
                    return (
                      <details key={bucket} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                        <summary className="cursor-pointer list-none">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="font-medium text-[var(--cl-ink)]">{bucket}</p>
                              <p className="text-xs text-[var(--cl-muted)]">{bucketFacts.length} fact{bucketFacts.length === 1 ? "" : "s"}</p>
                            </div>
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-[var(--cl-muted)]">
                              {bucketFacts.filter((fact) => isActiveFact(fact)).length} active
                            </span>
                          </div>
                        </summary>
                        <div className="mt-4 space-y-3">
                          {displayFacts.slice(0, 3).map((fact) => (
                            <FactCard key={fact.slug} fact={fact} />
                          ))}
                          {displayFacts.length > 3 && (
                            <p className="text-xs text-[var(--cl-muted)]">+ {displayFacts.length - 3} more fact(s)</p>
                          )}
                        </div>
                      </details>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
              <h3 className="font-display text-2xl text-[var(--cl-ink)]">Recent facts</h3>
              <p className="mt-1 text-sm text-[var(--cl-muted)]">The most recent facts that match your current filters.</p>

              <div className="mt-4 space-y-3">
                {sortFactsForDisplay(facts).length === 0 ? (
                  <p className="text-sm text-[var(--cl-muted)]">No facts match the current filters.</p>
                ) : (
                  sortFactsForDisplay(facts).slice(0, 6).map((fact) => <FactCard key={fact.slug} fact={fact} />)
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
              <h3 className="font-display text-2xl text-[var(--cl-ink)]">Coverage snapshot</h3>
              <div className="mt-4 space-y-3 text-sm text-[var(--cl-muted)]">
                <p>Facts are pulled from employer YAMLs and profile YAMLs on read, so the dashboard reflects what is on disk now.</p>
                <p>Deleted facts stay visible only when you ask for them, which keeps the default view clean for counselors.</p>
                <p>Use the grouped view to spot whether one employer or one fact type is carrying all the coverage.</p>
              </div>
            </div>
          </aside>
        </div>
      )}
    </section>
  )
}
