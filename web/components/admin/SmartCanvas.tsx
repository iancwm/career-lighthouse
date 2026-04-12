"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface IntentCard {
  card_id: string
  domain: string
  summary: string
  diff: Record<string, string>
  raw_input_ref: string
  status: string
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
  created_by: string
  created_at: string
  updated_at: string
}

interface SmartCanvasProps {
  sessionId: string
  onBack: () => void
}

export default function SmartCanvas({ sessionId, onBack }: SmartCanvasProps) {
  const [session, setSession] = useState<KnowledgeSession | null>(null)
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null)
  const [editingDiff, setEditingDiff] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function loadSession() {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/sessions/${sessionId}`)
      if (!res.ok) throw new Error("not found")
      const data: KnowledgeSession = await res.json()
      setSession(data)

      // Auto-trigger analysis for new sessions
      if (data.status === "in-progress" && data.intent_cards.length === 0) {
        await analyzeSession()
        return // analyzeSession reloads and sets cards
      }

      // Auto-select first pending card
      const firstPending = data.intent_cards.find((c) => c.status === "pending")
      if (firstPending) {
        setSelectedCardId(firstPending.card_id)
        setEditingDiff({ ...firstPending.diff })
      }
    } catch {
      setError("Could not load session.")
    } finally {
      setLoading(false)
    }
  }

  async function analyzeSession() {
    setActionLoading(true)
    setNotice("Analyzing your notes with AI…")
    setError("")
    try {
      const res = await fetch(`${API_URL}/api/sessions/${sessionId}/analyze`, {
        method: "POST",
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Analysis failed")
      }
      // Reload session to get the cards
      const reloadRes = await fetch(`${API_URL}/api/sessions/${sessionId}`)
      if (reloadRes.ok) {
        const data: KnowledgeSession = await reloadRes.json()
        setSession(data)
        if (data.intent_cards.length > 0) {
          setNotice(`${data.intent_cards.length} intent(s) extracted — select a card to review.`)
          // Auto-select first card
          const firstCard = data.intent_cards[0]
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
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSession()
  }, [sessionId])

  const selectedCard = session?.intent_cards.find((c) => c.card_id === selectedCardId) ?? null

  async function commitCard() {
    if (!selectedCardId || !session) return
    setActionLoading(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(
        `${API_URL}/api/sessions/${session.id}/cards/${selectedCardId}/commit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ diff: editingDiff }),
        }
      )
      if (!res.ok) throw new Error("commit failed")
      setNotice("Card committed.")
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
      const res = await fetch(
        `${API_URL}/api/sessions/${session.id}/cards/${selectedCardId}/discard`,
        { method: "POST" }
      )
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
      <div className="flex items-center gap-3 text-sm text-gray-500 py-8">
        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {session?.status === "in-progress" ? "Analyzing your notes with AI…" : "Loading session…"}
      </div>
    )
  }
  if (!session) return <p className="text-sm text-red-500">Session not found.</p>

  const isComplete = session.status === "completed"
  const isAnalyzed = session.status === "analyzed"
  const pendingCards = session.intent_cards.filter((c) => c.status === "pending")
  const hasNoCards = session.intent_cards.length === 0
  const guidance = session.track_guidance
  const showGuidance = guidance && guidance.status !== "safe_update"

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <button onClick={onBack} className="text-sm text-blue-600 hover:text-blue-800 mb-1">
            ← Back to Session Editor
          </button>
          <h2 className="text-lg font-semibold">
            {isComplete ? "Session Complete" : `Session: ${session.status}`}
          </h2>
          <p className="text-xs text-gray-500">
            Created {new Date(session.created_at).toLocaleString()} by {session.created_by}
          </p>
          <p className="mt-2 max-w-2xl text-sm text-gray-600">
            Review the extracted intents here. If the guidance suggests a new or emerging track, compare the nearest tracks and do your own research before you move anything into Track Builder.
          </p>
        </div>
        {/* Retry analysis button for sessions with zero cards */}
        {isAnalyzed && hasNoCards && (
          <button
            onClick={analyzeSession}
            disabled={actionLoading}
            className="rounded-lg border border-blue-300 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-40"
          >
            {actionLoading ? "Analyzing…" : "Re-analyze"}
          </button>
        )}
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
            <span className="text-xs font-medium uppercase tracking-wide opacity-70">
              {guidance.status.replace(/_/g, " ")}
            </span>
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

      <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-6">
        {/* Left Column — Cards */}
        <div className="rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Intents ({pendingCards.length} pending)
          </h3>
          <div className="space-y-2">
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
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      card.domain === "employer"
                        ? "bg-purple-100 text-purple-700"
                        : "bg-blue-100 text-blue-700"
                    }`}
                  >
                    {card.domain}
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
                <p className="text-sm font-medium text-gray-800 mt-1">{card.summary}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right Column — Diff View */}
        <div className="rounded-xl border border-gray-200 p-5">
          {selectedCard ? (
            <>
              <h3 className="text-sm font-semibold text-gray-800 mb-1">{selectedCard.summary}</h3>
              <p className="text-xs text-gray-500 mb-4">
                Domain: {selectedCard.domain}
              </p>

              {/* Raw input reference */}
              {selectedCard.raw_input_ref && (
                <div className="mb-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
                  <p className="text-xs font-medium text-gray-500 mb-1">From your notes:</p>
                  <p className="text-sm text-gray-700 italic">{selectedCard.raw_input_ref}</p>
                </div>
              )}

              {/* Diff fields */}
              {Object.entries(editingDiff).map(([key, value]) => (
                <label key={key} className="block text-sm text-gray-700 mb-4">
                  {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  <textarea
                    value={value}
                    onChange={(e) =>
                      setEditingDiff((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                    className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[80px]"
                  />
                </label>
              ))}

              {/* Actions */}
              <div className="flex gap-3 pt-3 border-t border-gray-100">
                <button
                  onClick={commitCard}
                  disabled={actionLoading}
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
                >
                  {actionLoading ? "Committing…" : "Commit"}
                </button>
                <button
                  onClick={discardCard}
                  disabled={actionLoading}
                  className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
                >
                  {actionLoading ? "Processing…" : "Discard"}
                </button>
              </div>
            </>
          ) : (
            <div>
              <h3 className="text-sm font-semibold text-gray-800 mb-2">Raw Input</h3>
              <pre className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 max-h-[500px] overflow-y-auto">
                {session.raw_input}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
