"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface KnowledgeSession {
  id: string
  status: string
  raw_input: string
  intent_cards: Array<{ card_id: string; domain: string; summary: string; status: string }>
  created_by: string
  created_at: string
  updated_at: string
}

interface SessionInboxProps {
  onSelectSession: (sessionId: string) => void
}

export default function SessionInbox({ onSelectSession }: SessionInboxProps) {
  const [sessions, setSessions] = useState<KnowledgeSession[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [rawInput, setRawInput] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function loadSessions() {
    try {
      const res = await fetch(`${API_URL}/api/sessions`)
      if (!res.ok) throw new Error("load failed")
      const data: KnowledgeSession[] = await res.json()
      setSessions(data.filter((s) => s.status !== "completed"))
    } catch {
      setError("Could not load sessions.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSessions()
    const interval = setInterval(loadSessions, 30000)
    return () => clearInterval(interval)
  }, [])

  async function createSession() {
    if (!rawInput.trim()) return
    setCreating(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: rawInput.trim(), counsellor_id: "counsellor" }),
      })
      if (!res.ok) throw new Error("create failed")
      const session: KnowledgeSession = await res.json()
      setNotice("Session created.")
      setRawInput("")
      onSelectSession(session.id)
    } catch {
      setError("Could not create session.")
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading sessions…</p>

  return (
    <div>
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

      {/* New Session Form */}
      <div className="mb-6 rounded-xl border border-[#D8D0C4] bg-[#F6F1E8] p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">New Publishing Session</h3>
        <p className="text-sm text-gray-600 mb-3">
          Paste full counsellor research notes here — the system will extract
          individual update cards for each employer and track mentioned.
        </p>
        <textarea
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[110px] mb-3"
          placeholder="Example: Met with Goldman Sachs — they raised EP requirement from EP3 to EP4. Consulting market feels more competitive this year…"
        />
        <button
          onClick={createSession}
          disabled={creating || !rawInput.trim()}
          className="rounded-xl bg-[#0F766E] px-4 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] disabled:opacity-40"
        >
          {creating ? "Creating…" : "Create Session"}
        </button>
      </div>

      {/* Sessions List */}
      {sessions.length === 0 ? (
        <p className="text-sm text-gray-400">No active sessions. Create one above.</p>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => {
            const pendingCards = session.intent_cards.filter((c) => c.status === "pending").length
            return (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-left hover:border-gray-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1 mr-4">
                    <p className="text-sm font-medium text-gray-800">
                      {session.status === "analyzed" ? "Analyzed" : "In Progress"}
                    </p>
                    <p className="text-xs text-gray-500 mt-1 truncate">
                      {session.raw_input.slice(0, 100)}{session.raw_input.length > 100 ? "…" : ""}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(session.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                        session.status === "analyzed"
                          ? "bg-[#CCEBE8] text-[#0F766E]"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {session.status}
                    </span>
                    {pendingCards > 0 && (
                      <p className="text-xs text-gray-500 mt-1">
                        {pendingCards} pending
                      </p>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
