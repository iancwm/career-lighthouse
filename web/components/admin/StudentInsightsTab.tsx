"use client"

import { FormEvent, useMemo, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"

interface StudentInsightResult {
  message_id: string
  text: string
  timestamp: string
  active_career_type?: string | null
  background?: string | null
  region?: string | null
  score?: number | null
  source_label?: string | null
}

interface StudentInsightsResponse {
  results: StudentInsightResult[]
  total_returned?: number
  insights_enabled?: boolean
  supports_background_filter?: boolean
  supports_region_filter?: boolean
}

type ViewState = "idle" | "loading" | "results" | "empty" | "error" | "disabled"

function formatTimestamp(timestamp: string): string {
  const parsed = new Date(timestamp)
  if (Number.isNaN(parsed.getTime())) return timestamp
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed)
}

function formatScore(value: number): string {
  return value.toFixed(3)
}

export default function StudentInsightsTab() {
  const [query, setQuery] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [careerType, setCareerType] = useState("")
  const [background, setBackground] = useState("")
  const [region, setRegion] = useState("")
  const [state, setState] = useState<ViewState>("idle")
  const [results, setResults] = useState<StudentInsightResult[]>([])
  const [errorMessage, setErrorMessage] = useState("")
  const [supportsBackgroundFilter, setSupportsBackgroundFilter] = useState(true)
  const [supportsRegionFilter, setSupportsRegionFilter] = useState(true)

  const requestPayload = useMemo(() => {
    const payload: Record<string, string> = {
      query: query.trim(),
    }
    if (dateFrom.trim()) payload.date_from = dateFrom.trim()
    if (dateTo.trim()) payload.date_to = dateTo.trim()
    if (careerType.trim()) payload.career_type = careerType.trim()
    if (supportsBackgroundFilter && background.trim()) payload.background = background.trim()
    if (supportsRegionFilter && region.trim()) payload.region = region.trim()
    return payload
  }, [background, careerType, dateFrom, dateTo, query, region, supportsBackgroundFilter, supportsRegionFilter])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!requestPayload.query) return

    setState("loading")
    setErrorMessage("")

    try {
      const requestInit: RequestInit = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      }

      const response = await adminFetch("/api/insights/student-questions/search", requestInit)

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("Student insights search is currently disabled.")
        }
        throw new Error("Search failed. Try again.")
      }

      const data = (await response.json()) as StudentInsightsResponse
      setSupportsBackgroundFilter(data.supports_background_filter !== false)
      setSupportsRegionFilter(data.supports_region_filter !== false)

      if (data.insights_enabled === false) {
        setResults([])
        setState("disabled")
        return
      }

      const nextResults = data.results ?? []
      setResults(nextResults)
      setState(nextResults.length > 0 ? "results" : "empty")
    } catch (error) {
      const fallback = "Search failed. Try again."
      setErrorMessage(error instanceof Error && error.message ? error.message : fallback)
      setResults([])
      setState("error")
    }
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-6 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
        <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Admin Room</p>
        <h2 className="mt-2 font-display text-3xl text-[var(--cl-ink)]">Student Insights</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--cl-muted)]">
          Semantically search what students have been asking and spot concern patterns before your next session.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="student-insights-query" className="mb-2 block text-sm font-medium text-[var(--cl-ink)]">
              Search query
            </label>
            <input
              id="student-insights-query"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search what students have been asking…"
              className="w-full rounded-xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3 text-sm text-[var(--cl-ink)] outline-none transition focus:border-[var(--cl-accent)] focus:ring-2 focus:ring-[var(--cl-accent)]/15"
            />
          </div>

          <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--cl-muted)]">Optional filters</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-5">
              <div className="flex flex-col gap-1">
                <label htmlFor="student-insights-date-from" className="text-xs font-medium text-[var(--cl-muted)]">
                  Date from
                </label>
                <input
                  id="student-insights-date-from"
                  type="date"
                  value={dateFrom}
                  onChange={(event) => setDateFrom(event.target.value)}
                  className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="student-insights-date-to" className="text-xs font-medium text-[var(--cl-muted)]">
                  Date to
                </label>
                <input
                  id="student-insights-date-to"
                  type="date"
                  value={dateTo}
                  onChange={(event) => setDateTo(event.target.value)}
                  className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="student-insights-career-type" className="text-xs font-medium text-[var(--cl-muted)]">
                  Career type
                </label>
                <input
                  id="student-insights-career-type"
                  type="text"
                  value={careerType}
                  onChange={(event) => setCareerType(event.target.value)}
                  placeholder="software_engineering"
                  className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="student-insights-background" className="text-xs font-medium text-[var(--cl-muted)]">
                  Background
                </label>
                <input
                  id="student-insights-background"
                  type="text"
                  value={background}
                  onChange={(event) => setBackground(event.target.value)}
                  placeholder="business"
                  disabled={!supportsBackgroundFilter}
                  className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
                />
                {!supportsBackgroundFilter && (
                  <p className="text-[11px] text-[var(--cl-muted)]">Background filter unavailable in current backend config.</p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="student-insights-region" className="text-xs font-medium text-[var(--cl-muted)]">
                  Region
                </label>
                <input
                  id="student-insights-region"
                  type="text"
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  placeholder="southeast_asia"
                  disabled={!supportsRegionFilter}
                  className="rounded-lg border border-[var(--cl-line)] bg-[var(--cl-surface)] px-3 py-2 text-sm text-[var(--cl-ink)] outline-none focus:border-[var(--cl-accent)]"
                />
                {!supportsRegionFilter && (
                  <p className="text-[11px] text-[var(--cl-muted)]">Region filter unavailable in current backend config.</p>
                )}
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={state === "loading" || !query.trim()}
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-accent)] bg-[var(--cl-accent)] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent)]/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {state === "loading" ? <ActionStatus variant="on-dark" label="Searching…" /> : "Search student questions"}
          </button>
        </form>
      </div>

      {state === "idle" && (
        <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-5 py-4 text-sm leading-6 text-[var(--cl-muted)]">
          Enter a query to find semantically related student questions from chat history.
        </div>
      )}

      {state === "loading" && (
        <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-5 py-4">
          <ActionStatus label="Searching student questions…" />
        </div>
      )}

      {state === "error" && (
        <div className="rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-5 py-4 text-sm text-[var(--cl-error)]">
          {errorMessage || "Search failed. Try again."}
        </div>
      )}

      {state === "empty" && (
        <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-5 py-4 text-sm text-[var(--cl-muted)]">
          No student questions matched your search.
        </div>
      )}

      {state === "disabled" && (
        <div className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-5 py-4 text-sm text-[var(--cl-muted)]">
          Student insights search is currently disabled in this environment.
        </div>
      )}

      {state === "results" && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl text-[var(--cl-ink)]">Search results</h3>
            <p className="text-sm text-[var(--cl-muted)]">
              {results.length} result{results.length === 1 ? "" : "s"}
            </p>
          </div>
          {results.map((item) => (
            <article
              key={item.message_id}
              className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_8px_24px_rgba(31,41,55,0.05)]"
            >
              <p className="text-sm leading-7 text-[var(--cl-ink)]">{item.text}</p>
              <p className="mt-3 text-xs text-[var(--cl-muted)]">Asked {formatTimestamp(item.timestamp)}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {item.active_career_type && (
                  <span className="rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs text-[var(--cl-ink)]">
                    Track: {item.active_career_type}
                  </span>
                )}
                {item.background && (
                  <span className="rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs text-[var(--cl-ink)]">
                    Background: {item.background}
                  </span>
                )}
                {item.region && (
                  <span className="rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs text-[var(--cl-ink)]">
                    Region: {item.region}
                  </span>
                )}
                {typeof item.score === "number" && (
                  <span className="rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-2.5 py-1 text-xs text-[var(--cl-muted)]">
                    Score: {formatScore(item.score)}
                  </span>
                )}
              </div>
              <p className="mt-3 font-mono-display text-[12px] text-[var(--cl-muted)]">
                Source: {item.source_label ?? "Student chat"}
              </p>
            </article>
          ))}
        </section>
      )}
    </section>
  )
}
