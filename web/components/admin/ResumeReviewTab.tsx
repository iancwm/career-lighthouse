"use client"
import { useRef, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import MarkdownMessage from "@/components/student/MarkdownMessage"

export default function ResumeReviewTab() {
  const [resume, setResume] = useState("")
  const [brief, setBrief] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  async function handleGenerate() {
    if (!resume.trim()) return
    setLoading(true)
    setBrief("")
    setError("")
    try {
      const res = await adminFetch("/api/brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_text: resume }),
      })
      if (!res.ok) throw new Error(`Failed (${res.status})`)
      const data = await res.json()
      setBrief(data.brief)
    } catch {
      setError("Could not generate brief. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  function scrollToInput() {
    textareaRef.current?.scrollIntoView({ behavior: "smooth" })
    setTimeout(() => textareaRef.current?.focus(), 300)
  }

  return (
    <div>
      {/* Upcoming student meeting banner */}
      <div className="mb-6 rounded-lg bg-[#F0E7DB] border-l-4 border-[#0F766E] px-4 py-3">
        <p className="text-sm font-semibold text-[#1F2937]">
          Have an upcoming student meeting?
        </p>
        <p className="text-sm text-[#5F6B76] mt-1">
          Paste the student's resume below to generate a prep brief with fit assessment,
          risks, and talking points for your next meeting.
        </p>
        <button
          onClick={scrollToInput}
          className="mt-2 rounded-lg bg-[#0F766E] px-4 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] transition-colors"
          style={{ minHeight: "44px" }}
        >
          Start a resume review
        </button>
      </div>

      <h2 className="text-lg font-semibold mb-1">Student Resume Review</h2>
      <p className="text-sm text-[#5F6B76] mb-4">
        Paste a student resume to draft a prep brief with likely fit, risks, and talking points for the next meeting.
      </p>

      <textarea
        ref={textareaRef}
        value={resume}
        onChange={(e) => setResume(e.target.value)}
        placeholder="Paste the student resume text here…"
        className="w-full h-40 border border-[#D8D0C4] rounded-lg p-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-[#0F766E] bg-[#FFFDFC]"
      />

      <button
        onClick={handleGenerate}
        disabled={loading || !resume.trim()}
        className="mt-3 rounded-xl bg-[#0F766E] px-5 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] disabled:opacity-40 transition-colors"
        style={{ minHeight: "44px" }}
      >
        {loading ? "Generating brief…" : "Generate brief"}
      </button>

      {error && (
        <div className="mt-4 rounded-lg border border-[#B42318]/25 bg-[#B42318]/10 px-4 py-3 text-sm text-[#B42318]">
          {error}
        </div>
      )}

      {brief && (
        <div className="mt-6 rounded-xl border border-[#D8D0C4] bg-[#FFFDFC] p-5">
          <h3 className="text-sm font-semibold text-[#1F2937] mb-3">Prep Brief</h3>
          <div className="text-sm leading-7 text-[#1F2937]">
            <MarkdownMessage content={brief} />
          </div>
        </div>
      )}
    </div>
  )
}
