"use client"
import { useRef, useState, type ChangeEvent } from "react"
import { adminFetch } from "@/lib/admin-api"
import MarkdownMessage from "@/components/student/MarkdownMessage"
import { ActionStatus } from "@/components/admin/ui/ActionStatus"

export default function ResumeReviewTab() {
  const [resume, setResume] = useState("")
  const [brief, setBrief] = useState("")
  const [loading, setLoading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [error, setError] = useState("")
  const [uploadError, setUploadError] = useState("")
  const [fileName, setFileName] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  async function handleFileUpload(file: File) {
    setExtracting(true)
    setUploadError("")
    try {
      const form = new FormData()
      form.append("file", file)
      const res = await adminFetch("/api/sessions/parse-file", {
        method: "POST",
        body: form,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail || "Could not extract text from this file.")
      }
      const data = await res.json()
      setResume(data.text || "")
      setFileName(data.filename || file.name)
      textareaRef.current?.focus()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Could not extract text from this file.")
    } finally {
      setExtracting(false)
    }
  }

  function handleFileInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) void handleFileUpload(file)
  }

  function scrollToInput() {
    textareaRef.current?.scrollIntoView({ behavior: "smooth" })
    setTimeout(() => textareaRef.current?.focus(), 300)
  }

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-lg font-semibold mb-1">Have an upcoming student meeting?</h2>
        <p className="text-sm text-[#5F6B76]">
          Upload a resume file or paste the text first, then generate a short prep brief with fit, risks, and talking points.
        </p>
      </div>

      <div className="mb-4 rounded-xl border border-[#D8D0C4] bg-[#FFFDFC] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,.txt,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="hidden"
            onChange={handleFileInputChange}
            disabled={extracting || loading}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={extracting || loading}
            className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[#0F766E] px-4 py-2 text-sm font-medium text-[#0F766E] hover:bg-[#F0F7F6] disabled:opacity-40"
            style={{ minHeight: "44px" }}
          >
            {extracting ? <ActionStatus label="Extracting…" /> : "Upload .docx or .txt"}
          </button>
          <button
            type="button"
            onClick={scrollToInput}
            className="rounded-lg border border-[#D8D0C4] px-4 py-2 text-sm font-medium text-[#1F2937] hover:bg-[#F7F4EE]"
            style={{ minHeight: "44px" }}
          >
            Paste text instead
          </button>
        </div>
        {fileName && (
          <p className="mt-3 text-xs text-[#5F6B76]">
            Loaded from {fileName}
          </p>
        )}
        {uploadError && (
          <p className="mt-3 text-sm text-[#B42318]">{uploadError}</p>
        )}
      </div>

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
        className="mt-3 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#0F766E] px-5 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] disabled:opacity-40 transition-colors"
        style={{ minHeight: "44px" }}
      >
        {loading ? <ActionStatus variant="on-dark" label="Generating brief…" /> : "Generate brief"}
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
