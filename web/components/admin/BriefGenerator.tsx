"use client"
import { useState } from "react"
import { adminFetch } from "@/lib/admin-api"

export default function BriefGenerator() {
  const [resume, setResume] = useState("")
  const [brief, setBrief] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleGenerate() {
    if (!resume.trim()) return
    setLoading(true)
    setBrief("")
    const res = await adminFetch("/api/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text: resume }),
    })
    const data = await res.json()
    setBrief(data.brief)
    setLoading(false)
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Generate Counsellor Brief</h2>
      <p className="text-sm text-gray-500 mb-3">
        Paste a student resume to draft a prep brief with likely fit, risks, and talking points for the next meeting.
      </p>
      <textarea
        value={resume}
        onChange={e => setResume(e.target.value)}
        placeholder="Paste the student resume text here…"
        className="w-full h-40 border rounded p-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <button
        onClick={handleGenerate}
        disabled={loading || !resume.trim()}
        className="mt-2 px-5 py-2 bg-blue-600 text-white rounded disabled:opacity-50 text-sm"
      >
        {loading ? "Generating brief…" : "Generate brief"}
      </button>
      {brief && (
        <div className="mt-4 bg-white border rounded p-4 text-sm whitespace-pre-wrap leading-relaxed">
          {brief}
        </div>
      )}
    </div>
  )
}
