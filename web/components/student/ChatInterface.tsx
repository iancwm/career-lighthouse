"use client"

import { useEffect, useRef, useState } from "react"
import CitationBadge from "./CitationBadge"
import type { IntakeContext } from "./IntakeFlow"
import MarkdownMessage from "./MarkdownMessage"
import { backendFetch } from "@/lib/backend-api"

interface Citation {
  filename: string
  excerpt: string
  source_name?: string | null
  updated_at?: string | null
  source_lifecycle?: string | null
}

interface Message {
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
}

interface Props {
  resumeText: string
  intakeContext?: IntakeContext | null
  onEditContext?: () => void
}

const BACKGROUND_LABELS: Record<string, string> = {
  undergrad: "Undergrad",
  masters: "Pre-exp Masters",
  professional: "Working professional",
}

const REGION_LABELS: Record<string, string> = {
  sea: "Southeast Asia",
  south_asia: "South Asia",
  east_asia: "East Asia",
  other: "Other",
}

const INTEREST_LABELS: Record<string, string> = {
  finance: "Finance / Banking",
  consulting: "Consulting",
  tech: "Tech / Product",
  public_sector: "Public Sector / GLCs",
  not_sure: "Not sure yet",
}

function formatUnknown(value?: string | null): string {
  const clean = typeof value === "string" ? value.trim() : ""
  return clean || "Unknown"
}

function formatDate(value?: string | null): string {
  const clean = typeof value === "string" ? value.trim() : ""
  if (!clean) return "Unknown"
  const parsed = new Date(clean)
  if (Number.isNaN(parsed.getTime())) return clean
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function labelForValue(map: Record<string, string>, value?: string | null): string {
  if (!value) return "Unknown"
  return map[value] || value
}

export default function ChatInterface({ resumeText, intakeContext, onEditContext }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [activeCareerType, setActiveCareerType] = useState<string | null>(null)
  const [intakeConsumed, setIntakeConsumed] = useState(false)
  const [careerLabels, setCareerLabels] = useState<Record<string, string>>({})
  const [trustOpen, setTrustOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Fresh intake means a fresh chat state.
  useEffect(() => {
    setActiveCareerType(null)
    setIntakeConsumed(false)
    setMessages([])
    setInput("")
    setLoading(false)
    setTrustOpen(false)
  }, [intakeContext])

  useEffect(() => {
    async function loadTracks() {
      try {
        const res = await backendFetch("/api/tracks")
        if (!res.ok) return
        const data = await res.json()
        const map: Record<string, string> = {}
        data.forEach((t: { slug: string; label: string }) => {
          map[t.slug] = t.label
        })
        setCareerLabels(map)
      } catch (err) {
        console.error("Failed to load tracks", err)
      }
    }

    loadTracks()
  }, [])

  function clearChatState() {
    setMessages([])
    setInput("")
    setLoading(false)
    setActiveCareerType(null)
    setIntakeConsumed(false)
    setTrustOpen(false)
  }

  async function send() {
    const msg = input.trim()
    if (!msg || loading) return

    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [...prev, { role: "user", content: msg }])
    setInput("")
    setLoading(true)

    try {
      const body: Record<string, unknown> = {
        message: msg,
        resume_text: resumeText || null,
        history,
      }

      const sendingIntake = intakeContext && !intakeConsumed
      if (sendingIntake) {
        body.intake_context = intakeContext
      }
      if (activeCareerType) {
        body.active_career_type = activeCareerType
      }

      const res = await backendFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error(`${res.status}`)

      const data = await res.json()
      if (sendingIntake) setIntakeConsumed(true)
      if (data.active_career_type !== undefined) {
        setActiveCareerType(data.active_career_type || null)
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          citations: data.citations,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong — please try again." },
      ])
    } finally {
      setLoading(false)
    }
  }

  const careerLabel = activeCareerType ? careerLabels[activeCareerType] ?? activeCareerType : null
  const backgroundLabel = labelForValue(BACKGROUND_LABELS, intakeContext?.background)
  const regionLabel = labelForValue(REGION_LABELS, intakeContext?.region)
  const interestLabel = labelForValue(INTEREST_LABELS, intakeContext?.interest)
  const hasResume = Boolean(resumeText.trim())
  const resumeLabel = hasResume ? "Present" : "Not present"
  const activeCareerLabel = careerLabel ?? "Unknown"
  const compactSummary = [
    backgroundLabel,
    regionLabel,
    interestLabel,
    activeCareerLabel,
    hasResume ? "Resume" : "No resume",
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <section className="flex h-[600px] flex-col rounded-[22px] border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-4 shadow-sm">
      <div className="mb-3">
        <button
          type="button"
          aria-expanded={trustOpen}
          aria-controls="student-trust-panel"
          onClick={() => setTrustOpen((value) => !value)}
          className="flex min-h-11 w-full items-center justify-between gap-3 rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-2 text-left text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
        >
          <span className="min-w-0 truncate font-medium">
            {trustOpen ? "Hide context" : "Context"}: {compactSummary || "Unknown"}
          </span>
          <span className="shrink-0 font-mono-display text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
            {trustOpen ? "Collapse" : "Expand"}
          </span>
        </button>

        {trustOpen && (
          <div
            id="student-trust-panel"
            className="mt-3 rounded-[18px] border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                  Background
                </div>
                <div className="mt-1 text-sm text-[var(--cl-ink)]">{backgroundLabel}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                  Region
                </div>
                <div className="mt-1 text-sm text-[var(--cl-ink)]">{regionLabel}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                  Interest
                </div>
                <div className="mt-1 text-sm text-[var(--cl-ink)]">{interestLabel}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                  Active career
                </div>
                <div className="mt-1 text-sm text-[var(--cl-ink)]">{activeCareerLabel}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--cl-muted)]">
                  Resume
                </div>
                <div className="mt-1 text-sm text-[var(--cl-ink)]">{resumeLabel}</div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onEditContext}
                className="inline-flex min-h-11 items-center rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
              >
                Edit context
              </button>
              <button
                type="button"
                onClick={clearChatState}
                className="inline-flex min-h-11 items-center rounded-full border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-2 text-sm font-medium text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
              >
                Reset chat
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="mx-auto mt-8 max-w-md rounded-[18px] border border-dashed border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-4 text-center text-sm leading-6 text-[var(--cl-muted)]">
            {careerLabel
              ? `Ready to help with ${careerLabel}. What's your question?`
              : "Ask me anything about careers at your school."}
          </div>
        )}

        <div className="space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[88%] rounded-[18px] px-4 py-3 ${
                  m.role === "user"
                    ? "bg-[var(--cl-accent)] text-white"
                    : "border border-[var(--cl-line)] bg-[var(--cl-surface)] text-[var(--cl-ink)]"
                }`}
              >
                {m.role === "assistant" ? (
                  <div className="text-[15px] leading-7">
                    <MarkdownMessage content={m.content} />
                  </div>
                ) : (
                  <p className="text-[15px] leading-6 whitespace-pre-wrap">{m.content}</p>
                )}
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-3 border-t border-[var(--cl-line)] pt-3">
                    <div className="flex flex-wrap gap-2">
                      {m.citations.map((c, j) => (
                        <CitationBadge
                          key={j}
                          filename={c.filename}
                          excerpt={c.excerpt}
                          sourceName={c.source_name}
                          updatedAt={c.updated_at}
                          sourceLifecycle={c.source_lifecycle}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-[18px] border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3 text-sm text-[var(--cl-muted)]">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-[var(--cl-line)] pt-4 sm:flex-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Ask about career paths, interviews, firms…"
          className="min-h-11 flex-1 rounded-[14px] border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-3 text-sm text-[var(--cl-ink)] placeholder:text-[var(--cl-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--cl-accent)]"
          disabled={loading}
        />
        <button
          type="button"
          onClick={send}
          disabled={loading || !input.trim()}
          className="inline-flex min-h-11 items-center justify-center rounded-[14px] bg-[var(--cl-accent)] px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-[var(--cl-accent-strong)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </section>
  )
}
