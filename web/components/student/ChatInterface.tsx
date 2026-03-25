"use client"
import { useState, useRef, useEffect } from "react"
import CitationBadge from "./CitationBadge"
import type { IntakeContext } from "./IntakeFlow"

interface Message {
  role: "user" | "assistant"
  content: string
  citations?: { filename: string; excerpt: string }[]
}

interface Props {
  resumeText: string
  intakeContext?: IntakeContext | null
}

const CAREER_TYPE_LABELS: Record<string, string> = {
  investment_banking: "Investment Banking",
  consulting: "Consulting",
  tech_product: "Tech / Product",
  public_sector: "Public Sector / GLCs",
  general_singapore: "General Singapore Market",
}

export default function ChatInterface({ resumeText, intakeContext }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [activeCareerType, setActiveCareerType] = useState<string | null>(null)
  const [intakeConsumed, setIntakeConsumed] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Reset career type when a fresh intake context is provided (new conversation)
  useEffect(() => {
    setActiveCareerType(null)
    setIntakeConsumed(false)
    setMessages([])
  }, [intakeContext])

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
      // Pass intake_context on the first message only (then discard — PDPA)
      // Note: only mark as consumed after a successful API response so that
      // fetch failures don't silently discard intake_context on retry.
      const sendingIntake = intakeContext && !intakeConsumed
      if (sendingIntake) {
        body.intake_context = intakeContext
      }
      // Echo active_career_type on all subsequent messages as fallback
      if (activeCareerType) {
        body.active_career_type = activeCareerType
      }

      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      // Mark intake as consumed only on successful response — server received it
      if (sendingIntake) setIntakeConsumed(true)
      if (data.active_career_type) {
        setActiveCareerType(data.active_career_type)
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response, citations: data.citations },
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

  const careerLabel = activeCareerType ? CAREER_TYPE_LABELS[activeCareerType] ?? activeCareerType : null

  return (
    <div className="flex flex-col h-[600px]">
      {careerLabel && (
        <div className="mb-2 flex items-center gap-1.5">
          <span className="text-xs text-gray-500">Advising on:</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
            {careerLabel}
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">
            {careerLabel
              ? `Ready to help with ${careerLabel}. What's your question?`
              : "Ask me anything about careers at your school."}
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-white border"
              } rounded-2xl px-4 py-3`}
            >
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap gap-1">
                  {m.citations.map((c, j) => (
                    <CitationBadge key={j} filename={c.filename} excerpt={c.excerpt} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border rounded-2xl px-4 py-3 text-sm text-gray-400">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Ask about career paths, interviews, firms…"
          className="flex-1 border rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="px-5 py-2 bg-blue-600 text-white rounded-xl text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
