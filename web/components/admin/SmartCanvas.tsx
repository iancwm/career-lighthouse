"use client"
import { useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"

type CardDomain = "employer" | "track" | "alumni" | string

interface IntentCard {
  card_id: string
  domain: CardDomain
  summary: string
  diff: Record<string, unknown>
  raw_input_ref: string
  status: string
  proposals?: Record<string, FieldProposal>
  is_update?: boolean
  matched_slug?: string | null
}

interface AlreadyCovered {
  content: string
  reason: string
}

interface TrackCandidate {
  slug: string
  label: string
  score: number
}

interface TrackGuidance {
  status: "safe_update" | "clustered_uncertainty" | "emerging_taxonomy_signal" | string
  recommendation: string
  nearest_tracks: TrackCandidate[]
  recurrence_count: number
  cluster_key?: string | null
}

interface KnowledgeSession {
  id: string
  status: string
  raw_input: string
  intent_cards: IntentCard[]
  already_covered?: AlreadyCovered[]
  track_guidance?: TrackGuidance | null
  analysis_error?: string | null
  created_by: string
  created_at: string
  updated_at: string
}

interface FieldProposal {
  confidence?: number | null
  evidence?: unknown
  rationale?: string | null
}

interface AlumniCompanyLink {
  company_name?: string
  company_slug?: string
  relationship?: string
  notes?: string
  title?: string
  role?: string
  start_date?: string
  end_date?: string
  start_year?: string | number
  end_year?: string | number
  is_current?: boolean
  current?: boolean
}

interface SmartCanvasProps {
  sessionId: string
  onBack: () => void
  onOpenTraces: (sessionId: string) => void
}

interface CreateTrackFromSessionProps {
  sessionId: string
  rawInput: string
  actionLoading: boolean
  setActionLoading: (loading: boolean) => void
  setNotice: (notice: string) => void
  setError: (error: string) => void
}

function formatDiffValue(value: unknown): string {
  if (typeof value === "string") return value
  if (value == null) return ""
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatFieldLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

function toDisplayText(value: unknown): string {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return ""
}

function normalizeEvidence(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
  if (typeof value === "string" && value.trim()) return [value.trim()]
  return []
}

function parseStructuredValue(value: unknown): unknown {
  if (typeof value !== "string") return value
  const trimmed = value.trim()
  if (!trimmed) return value
  if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
    try {
      return JSON.parse(trimmed)
    } catch {
      return value
    }
  }
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function coerceEditedValue(originalValue: unknown, editedValue: unknown): unknown {
  if (typeof editedValue !== "string") return editedValue

  if (typeof originalValue === "boolean") {
    const lowered = editedValue.trim().toLowerCase()
    if (["true", "yes", "1"].includes(lowered)) return true
    if (["false", "no", "0"].includes(lowered)) return false
    return editedValue
  }

  if (typeof originalValue === "number") {
    const parsed = Number(editedValue)
    return Number.isNaN(parsed) ? editedValue : parsed
  }

  if (Array.isArray(originalValue) || isRecord(originalValue)) {
    return parseStructuredValue(editedValue)
  }

  return editedValue
}

function getBadgeClasses(domain: CardDomain): string {
  if (domain === "employer") return "bg-purple-100 text-purple-700"
  if (domain === "alumni") return "bg-emerald-100 text-emerald-700"
  return "bg-blue-100 text-blue-700"
}

function getLinkDateValue(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value !== "string" || !value.trim()) return Number.NaN

  const timestamp = Date.parse(value)
  if (!Number.isNaN(timestamp)) return timestamp

  if (/^\d{4}$/.test(value.trim())) return Number(value.trim())
  return Number.NaN
}

function formatLinkDateLabel(link: AlumniCompanyLink): string {
  const start = toDisplayText(link.start_date) || toDisplayText(link.start_year)
  const end = toDisplayText(link.end_date) || toDisplayText(link.end_year)
  const isCurrent = Boolean(link.is_current ?? link.current)

  if (start && (end || isCurrent)) return `${start} - ${isCurrent ? "Present" : end}`
  if (start) return start
  if (end) return end
  if (isCurrent) return "Current"
  return ""
}

function normalizeCompanyLinks(value: unknown): AlumniCompanyLink[] {
  const parsed = parseStructuredValue(value)
  if (!Array.isArray(parsed)) return []

  return parsed
    .filter((item): item is AlumniCompanyLink => isRecord(item))
    .map((item) => ({ ...item }))
    .sort((left, right) => {
      const leftStart = getLinkDateValue(left.start_date ?? left.start_year ?? left.end_date ?? left.end_year)
      const rightStart = getLinkDateValue(right.start_date ?? right.start_year ?? right.end_date ?? right.end_year)

      if (Number.isNaN(leftStart) && Number.isNaN(rightStart)) return 0
      if (Number.isNaN(leftStart)) return 1
      if (Number.isNaN(rightStart)) return -1
      return leftStart - rightStart
    })
}

/** Sub-component: generates a draft track from session raw input and navigates to Track Builder. */
function CreateTrackFromSession({ sessionId, rawInput, actionLoading, setActionLoading, setNotice, setError }: CreateTrackFromSessionProps) {
  const [creating, setCreating] = useState(false)
  const [trackName, setTrackName] = useState("")
  const [draftSlug, setDraftSlug] = useState("")

  async function handleCreate() {
    if (!trackName.trim()) return
    setCreating(true)
    setError("")
    setNotice("")
    try {
      const res = await adminFetch("/api/kb/draft-tracks/generate", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          slug: trackName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""),
          track_name: trackName.trim(),
          text: rawInput,
          source_type: "note",
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Could not generate draft.")
      }
      const data = await res.json()
      setDraftSlug(data.slug)
      setNotice(`Draft "${data.track_name}" created. Opening in Track Builder…`)
      // Navigate to Track Builder with the new draft
      window.location.href = `/admin?view=tracks&trackSlug=${data.slug}`
    } catch (err: any) {
      setError(err.message || "Could not create track.")
    } finally {
      setCreating(false)
    }
  }

  if (draftSlug) {
    return (
      <p className="text-sm text-[#2F6B4F]">
        Draft created — redirecting to Track Builder…
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex-1">
        <label className="block text-xs font-medium text-[#5F6B76] mb-1">
          Track name
        </label>
        <input
          type="text"
          value={trackName}
          onChange={(e) => setTrackName(e.target.value)}
          placeholder="e.g. Fintech Compliance, Quantitative Marketing"
          className="w-full rounded border border-[#D8D0C4] bg-[#FFFDFC] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
          disabled={creating || actionLoading}
        />
      </div>
      <button
        onClick={handleCreate}
        disabled={creating || actionLoading || !trackName.trim()}
        className="rounded-xl bg-[#0F766E] px-5 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] disabled:opacity-40 transition-colors whitespace-nowrap"
        style={{ minHeight: "44px" }}
      >
        {creating ? "Creating draft…" : "Create draft track"}
      </button>
    </div>
  )
}

export default function SmartCanvas({ sessionId, onBack, onOpenTraces }: SmartCanvasProps) {
  const [session, setSession] = useState<KnowledgeSession | null>(null)
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null)
  const [editingDiff, setEditingDiff] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [isAnalyzingNow, setIsAnalyzingNow] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [statusDots, setStatusDots] = useState(0)
  const [guidanceDismissed, setGuidanceDismissed] = useState(false)

  async function loadSession() {
    setLoading(true)
    try {
      const res = await adminFetch(`/api/sessions/${sessionId}`)
      if (!res.ok) throw new Error("not found")
      const data: KnowledgeSession = await res.json()
      setSession(data)

      // Auto-trigger analysis for new sessions
      if (data.status === "in-progress" && data.intent_cards.length === 0) {
        await analyzeSession()
        return // analyzeSession reloads and sets cards
      }

      // If the currently selected card is no longer pending, auto-select the next pending one
      const currentCard = data.intent_cards.find((c) => c.card_id === selectedCardId)
      if (currentCard && currentCard.status !== "pending") {
        const nextPending = data.intent_cards.find((c) => c.status === "pending")
        if (nextPending) {
          setSelectedCardId(nextPending.card_id)
          setEditingDiff({ ...nextPending.diff })
        } else {
          setSelectedCardId(null)
          setEditingDiff({})
        }
      } else if (!selectedCardId) {
        // Auto-select first pending card on initial load
        const firstPending = data.intent_cards.find((c) => c.status === "pending")
        if (firstPending) {
          setSelectedCardId(firstPending.card_id)
          setEditingDiff({ ...firstPending.diff })
        }
      }
    } catch {
      setError("Could not load session.")
    } finally {
      setLoading(false)
    }
  }

  async function analyzeSession() {
    setActionLoading(true)
    setIsAnalyzingNow(true)
    setNotice("Analyzing your notes with AI…")
    setError("")
    try {
      const res = await adminFetch(`/api/sessions/${sessionId}/analyze`, {
        method: "POST",
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Analysis failed")
      }
      // Reload session to get the cards
      const reloadRes = await adminFetch(`/api/sessions/${sessionId}`)
      if (reloadRes.ok) {
        const data: KnowledgeSession = await reloadRes.json()
        setSession(data)
        if (data.intent_cards.length > 0) {
          const pendingCount = data.intent_cards.filter((card) => card.status === "pending").length
          setNotice(
            pendingCount > 0
              ? `Your session is ready. ${pendingCount} cards are ready to review.`
              : "Your session is ready."
          )
          const firstCard = data.intent_cards.find((card) => card.status === "pending") ?? data.intent_cards[0]
          setSelectedCardId(firstCard.card_id)
          setEditingDiff({ ...firstCard.diff })
        } else if (data.track_guidance && data.track_guidance.status !== "safe_update") {
          setNotice(data.track_guidance.recommendation)
        } else if ((data.already_covered?.length ?? 0) > 0) {
          setNotice("No changes needed — your notes confirm existing knowledge.")
        } else {
          setError("No intents were extracted. Your notes may not contain specific changes to tracks or employers.")
        }
      }
    } catch (err: any) {
      setError(err.message || "Could not analyze session.")
    } finally {
      setActionLoading(false)
      setIsAnalyzingNow(false)
      setLoading(false)
    }
  }

  async function cancelSession() {
    if (!session) return
    setActionLoading(true)
    setNotice("")
    setError("")
    try {
      const res = await adminFetch(`/api/sessions/${session.id}/cancel`, {
        method: "POST",
      })
      if (res.status === 409) {
        await loadSession()
        return
      }
      if (!res.ok) throw new Error("cancel failed")
      setNotice("Analysis stopped.")
      await loadSession()
    } catch {
      setError("Could not stop analysis.")
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => {
    setGuidanceDismissed(false)
    loadSession()
  }, [sessionId])

  useEffect(() => {
    if (!session || (session.status !== "in-progress" && session.status !== "analyzing")) {
      setStatusDots(0)
      return
    }

    const interval = window.setInterval(() => {
      setStatusDots((value) => (value + 1) % 4)
    }, 500)

    return () => window.clearInterval(interval)
  }, [session?.status])

  const selectedCard = session?.intent_cards.find((c) => c.card_id === selectedCardId) ?? null

  async function commitCard() {
    if (!selectedCardId || !session) return
    setActionLoading(true)
    setError("")
    setNotice("")
    try {
      const nextDiff = selectedCard
        ? Object.fromEntries(
            Object.entries(editingDiff).map(([key, value]) => [key, coerceEditedValue(selectedCard.diff[key], value)])
          )
        : editingDiff
      const res = await adminFetch(`/api/sessions/${session.id}/cards/${selectedCardId}/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diff: nextDiff }),
      })
      if (res.status === 409) {
        // Card already committed/discarded — reload to sync state
        await loadSession()
        return
      }
      if (!res.ok) throw new Error("commit failed")
      const data = await res.json().catch(() => ({}))
      const warning = data?.company_links_warning
      setNotice(warning ? `Card committed. ⚠️ ${warning}` : "Card committed.")
      await loadSession()
    } catch {
      setError("Could not commit card.")
    } finally {
      setActionLoading(false)
    }
  }

  async function discardCard() {
    if (!selectedCardId || !session) return
    setActionLoading(true)
    setError("")
    setNotice("")
    try {
      const res = await adminFetch(`/api/sessions/${session.id}/cards/${selectedCardId}/discard`, {
        method: "POST",
      })
      if (res.status === 409) {
        // Card already committed/discarded — reload to sync state
        await loadSession()
        return
      }
      if (!res.ok) throw new Error("discard failed")
      setNotice("Card discarded.")
      await loadSession()
    } catch {
      setError("Could not discard card.")
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="py-8">
        <ActionStatus
          size="md"
          label={
            session?.status === "in-progress" || session?.status === "analyzing"
              ? `Analyzing${".".repeat(statusDots)}`
              : "Loading session…"
          }
        />
      </div>
    )
  }
  if (!session) return <p className="text-sm text-red-500">Session not found.</p>

  const isComplete = session.status === "completed"
  const isAnalyzed = session.status === "analyzed"
  const isInFlight = session.status === "in-progress" || session.status === "analyzing" || isAnalyzingNow
  const canRetry = session.status === "failed" || session.status === "cancelled"
  const statusText = isInFlight ? `Analyzing${".".repeat(statusDots)}` : session.status
  const pendingCards = session.intent_cards.filter((c) => c.status === "pending")
  const hasNoCards = session.intent_cards.length === 0
  const guidance = session.track_guidance
  const showGuidance = guidance && guidance.status !== "safe_update" && !guidanceDismissed
  const isAlumniCard = selectedCard?.domain === "alumni"
  const selectedCardName = toDisplayText(editingDiff.full_name) || toDisplayText(selectedCard?.diff.full_name) || selectedCard?.summary || ""
  const selectedCardTitle = toDisplayText(editingDiff.current_title) || toDisplayText(selectedCard?.diff.current_title)
  const selectedCardCompany = toDisplayText(editingDiff.current_company) || toDisplayText(selectedCard?.diff.current_company)
  const selectedCardHeadline = [selectedCardTitle, selectedCardCompany].filter(Boolean).join(" @ ")
  const companyLinks = isAlumniCard ? normalizeCompanyLinks(editingDiff.company_links) : []

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <button onClick={onBack} className="text-sm text-blue-600 hover:text-blue-800 mb-1">
            ← Back to Sessions
          </button>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">
              {isComplete ? "Session Complete" : `Session: ${statusText}`}
            </h2>
            {isInFlight && (
              <ActionStatus variant="caution" size="sm" />
            )}
          </div>
          <p className="text-xs text-gray-500">
            Created {new Date(session.created_at).toLocaleString()} by {session.created_by}
          </p>
          {session.analysis_error && (
            <p className="mt-2 max-w-2xl rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {session.analysis_error}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onOpenTraces(sessionId)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Debug Workflow
          </button>
          {isInFlight && (
            <button
              onClick={cancelSession}
              disabled={actionLoading}
              className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-40"
            >
              {actionLoading ? "Stopping…" : "Stop analysis"}
            </button>
          )}
          {canRetry && (
            <button
              onClick={analyzeSession}
              disabled={actionLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--cl-accent)] px-3 py-1.5 text-xs font-medium text-[var(--cl-accent)] hover:bg-teal-50 disabled:opacity-40"
            >
              {actionLoading
                ? <ActionStatus variant="active" size="sm" label="Analyzing…" />
                : "Retry analysis"}
            </button>
          )}
          {isAnalyzed && hasNoCards && (
            <button
              onClick={analyzeSession}
              disabled={actionLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--cl-accent)] px-3 py-1.5 text-xs font-medium text-[var(--cl-accent)] hover:bg-teal-50 disabled:opacity-40"
            >
              {actionLoading
                ? <ActionStatus variant="active" size="sm" label="Analyzing…" />
                : "Re-analyze"}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {notice}
        </div>
      )}

      {showGuidance && (
        <div
          className={`mb-6 rounded-xl border px-4 py-4 text-sm ${
            guidance.status === "emerging_taxonomy_signal"
              ? "border-rose-200 bg-rose-50 text-rose-900"
              : "border-amber-200 bg-amber-50 text-amber-950"
          }`}
        >
          <div className="flex items-center justify-between gap-4">
            <h3 className="font-semibold">
              {guidance.status === "emerging_taxonomy_signal"
                ? "Recurring emerging track"
                : "Clustered uncertainty"}
            </h3>
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium uppercase tracking-wide opacity-70">
                {guidance.status.replace(/_/g, " ")}
              </span>
              <button
                onClick={() => setGuidanceDismissed(true)}
                className="text-xs opacity-60 hover:opacity-100 transition-opacity"
                aria-label="Dismiss guidance"
              >
                ✕
              </button>
            </div>
          </div>
          <p className="mt-2">{guidance.recommendation}</p>
          {guidance.nearest_tracks.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {guidance.nearest_tracks.map((track) => (
                <span
                  key={track.slug}
                  className="inline-flex items-center gap-2 rounded-full border border-current/20 bg-white/70 px-3 py-1 text-xs"
                >
                  <span className="font-medium">{track.label}</span>
                  <span className="opacity-70">{track.score.toFixed(2)}</span>
                </span>
              ))}
            </div>
          )}
          {guidance.recurrence_count > 0 && (
            <p className="mt-3 text-xs opacity-80">
              Recurrence count: {guidance.recurrence_count}
            </p>
          )}
        </div>
      )}

      {/* Already covered section */}
      {(session.already_covered?.length ?? 0) > 0 && (
        <div className="mb-6 rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Already Covered</h3>
          <div className="space-y-2">
            {session.already_covered!.map((item, i) => (
              <div key={i} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">
                <p>{item.content}</p>
                {item.reason && <p className="text-xs text-gray-400 mt-1">{item.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create career track from session notes */}
      {isAnalyzed && !hasNoCards && (
        <div className="mb-6 rounded-xl border border-[#D8D0C4] bg-[#F6F1E8] p-5">
          <h3 className="text-sm font-semibold text-[#1F2937] mb-1">
            Create a career track from these notes
          </h3>
          <p className="text-sm text-[#5F6B76] mb-3">
            AI will draft a new career track from your session notes.
            You'll review and edit the draft before anything is published.
          </p>
          <CreateTrackFromSession
            sessionId={session.id}
            rawInput={session.raw_input}
            actionLoading={actionLoading}
            setActionLoading={setActionLoading}
            setNotice={setNotice}
            setError={setError}
          />
        </div>
      )}

      {isComplete && (
        <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-6 py-4 text-center">
          <p className="text-lg font-semibold text-green-700">All cards processed</p>
          <button
            onClick={onBack}
            className="mt-2 rounded-lg border border-green-300 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-100"
          >
            Return to Inbox
          </button>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)] xl:min-h-[560px] xl:h-[calc(100vh-18rem)]">
        {/* Left Column — Cards */}
        <div className="order-2 rounded-xl border border-gray-200 xl:order-1 xl:flex xl:min-h-0 xl:flex-col">
          <div className="border-b border-gray-100 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-gray-700">
                Intents ({pendingCards.length} pending)
              </h3>
              {isInFlight && <ActionStatus variant="caution" size="sm" label="Analyzing…" announce={false} />}
            </div>
          </div>
          <div className="space-y-2 p-4 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
            {session.intent_cards.map((card) => (
              <button
                key={card.card_id}
                onClick={() => {
                  if (card.status === "pending") {
                    setSelectedCardId(card.card_id)
                    setEditingDiff({ ...card.diff })
                  }
                }}
                disabled={card.status !== "pending"}
                className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                  selectedCardId === card.card_id
                    ? "border-blue-500 bg-blue-50"
                    : card.status === "pending"
                    ? "border-gray-200 hover:border-gray-300"
                    : "border-gray-100 opacity-50 cursor-default"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getBadgeClasses(card.domain)}`}
                  >
                    {formatFieldLabel(card.domain)}
                  </span>
                  <span
                    className={`text-xs ${
                      card.status === "committed"
                        ? "text-green-600"
                        : card.status === "discarded"
                        ? "text-gray-400"
                        : "text-amber-600"
                    }`}
                  >
                    {card.status}
                  </span>
                </div>
                <p className="mt-1 text-sm font-medium text-gray-800">{card.summary}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right Column — Diff View */}
        <div className="order-1 rounded-xl border border-gray-200 xl:order-2 xl:flex xl:min-h-0 xl:flex-col">
          {selectedCard ? (
            <>
              <div className="border-b border-gray-100 bg-white px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${getBadgeClasses(selectedCard.domain)}`}>
                        {formatFieldLabel(selectedCard.domain)}
                      </span>
                      {selectedCard.is_update && (
                        <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800">
                          Update
                        </span>
                      )}
                    </div>
                    <h3 className="mt-3 text-sm font-semibold text-gray-800">
                      {isAlumniCard ? selectedCardName : selectedCard.summary}
                    </h3>
                    <p className="mt-1 text-xs text-gray-500">
                      {isAlumniCard
                        ? selectedCardHeadline || `Domain: ${selectedCard.domain}`
                        : `Domain: ${selectedCard.domain}`}
                    </p>
                  </div>
                  {isInFlight && (
                    <ActionStatus variant="caution" size="sm" label="Analysis still running" />
                  )}
                </div>
              </div>

              <div className="space-y-4 p-5 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
                {isAlumniCard && selectedCard.is_update && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    Updating existing {selectedCardName || selectedCard.matched_slug || "alumni record"}
                  </div>
                )}

                {/* Raw input reference */}
                {selectedCard.raw_input_ref && (
                  <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
                    <p className="mb-1 text-xs font-medium text-gray-500">From your notes:</p>
                    <p className="text-sm text-gray-700 italic">{selectedCard.raw_input_ref}</p>
                  </div>
                )}

                {isAlumniCard && companyLinks.length > 0 && (
                  <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-sm font-semibold text-emerald-900">Company history</h4>
                      <span className="text-xs text-emerald-700">Chronological</span>
                    </div>
                    <div className="mt-3 space-y-3">
                      {companyLinks.map((link, index) => {
                        const companyName = toDisplayText(link.company_name) || toDisplayText(link.company_slug) || "Linked company"
                        const role = toDisplayText(link.title) || toDisplayText(link.role)
                        const relationship = toDisplayText(link.relationship)
                        const notes = toDisplayText(link.notes)
                        const dateLabel = formatLinkDateLabel(link)

                        return (
                          <div key={`${companyName}-${dateLabel}-${index}`} className="rounded-lg border border-emerald-100 bg-white px-4 py-3">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-gray-900">{companyName}</p>
                                {(role || relationship) && (
                                  <p className="mt-1 text-xs text-gray-600">
                                    {[role, relationship].filter(Boolean).join(" · ")}
                                  </p>
                                )}
                              </div>
                              {dateLabel && (
                                <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800">
                                  {dateLabel}
                                </span>
                              )}
                            </div>
                            {notes && <p className="mt-2 text-sm text-gray-700">{notes}</p>}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Diff fields */}
                {Object.entries(editingDiff).map(([key, value]) => {
                  const proposal = selectedCard.proposals?.[key]
                  const evidence = normalizeEvidence(proposal?.evidence)
                  const rationale = toDisplayText(proposal?.rationale)
                  const isTrajectoryField = isAlumniCard && key === "career_trajectory_summary"

                  return (
                    <div key={key} className="rounded-lg border border-gray-200 bg-white p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <label className="text-sm font-medium text-gray-700" htmlFor={`smart-canvas-field-${key}`}>
                          {formatFieldLabel(key)}
                        </label>
                        {isAlumniCard && proposal?.confidence != null && (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                            Confidence {proposal.confidence}%
                          </span>
                        )}
                      </div>

                      {isTrajectoryField && (
                        <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                          <summary className="cursor-pointer text-xs font-medium text-slate-700">
                            Trajectory preview
                          </summary>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                            {formatDiffValue(value) || "No trajectory summary yet."}
                          </p>
                        </details>
                      )}

                      {(evidence.length > 0 || rationale) && isAlumniCard && (
                        <details className="mt-3 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2">
                          <summary className="cursor-pointer text-xs font-medium text-gray-600">
                            Evidence
                          </summary>
                          {evidence.length > 0 && (
                            <ul className="mt-2 space-y-2 text-sm text-gray-700">
                              {evidence.map((item, index) => (
                                <li key={`${key}-evidence-${index}`} className="rounded bg-white px-3 py-2">
                                  {item}
                                </li>
                              ))}
                            </ul>
                          )}
                          {rationale && (
                            <p className="mt-2 text-xs leading-5 text-gray-500">
                              {rationale}
                            </p>
                          )}
                        </details>
                      )}

                      <textarea
                        id={`smart-canvas-field-${key}`}
                        value={formatDiffValue(value)}
                        onChange={(e) =>
                          setEditingDiff((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                        className="mt-3 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[80px]"
                      />
                    </div>
                  )
                })}
              </div>

              <div className="border-t border-gray-100 bg-white/95 px-5 py-4 backdrop-blur supports-[backdrop-filter]:bg-white/80">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-gray-500">
                    Commit saves this card into the knowledge base. Discard skips it and moves on.
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={commitCard}
                      disabled={actionLoading}
                      className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
                    >
                      {actionLoading ? <ActionStatus variant="on-dark" label="Committing…" /> : "Commit"}
                    </button>
                    <button
                      onClick={discardCard}
                      disabled={actionLoading}
                      className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
                    >
                      {actionLoading ? <ActionStatus label="Processing…" /> : "Discard"}
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="xl:flex xl:min-h-0 xl:flex-1 xl:flex-col">
              <div className="border-b border-gray-100 px-5 py-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-800">Raw Input</h3>
                  <p className="mt-1 text-xs text-gray-500">Select a pending card to review proposed updates, or read the original notes here.</p>
                </div>
              </div>
              <div className="p-5 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
                <pre className="whitespace-pre-wrap rounded-lg bg-gray-50 p-4 text-sm text-gray-600 xl:min-h-full">
                  {session.raw_input}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
