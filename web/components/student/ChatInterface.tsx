"use client"
import { useState, useRef, useEffect } from "react"
import CitationBadge from "./CitationBadge"

interface Message { role: "user" | "assistant"; content: string; citations?: { filename: string; excerpt: string }[] }
interface Props { resumeText: string }

export default function ChatInterface({ resumeText }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  async function send() {
    const msg = input.trim()
    if (!msg || loading) return
    const history = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: "user", content: msg }])
    setInput("")
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, resume_text: resumeText || null, history }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: "assistant", content: data.response, citations: data.citations }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[600px]">
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">Ask me anything about careers at your school.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border"} rounded-2xl px-4 py-3`}>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap gap-1">
                  {m.citations.map((c, j) => <CitationBadge key={j} filename={c.filename} excerpt={c.excerpt} />)}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border rounded-2xl px-4 py-3 text-sm text-gray-400">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Ask about career paths, interviews, firms…"
          className="flex-1 border rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="px-5 py-2 bg-blue-600 text-white rounded-xl text-sm disabled:opacity-50">
          Send
        </button>
      </div>
    </div>
  )
}
