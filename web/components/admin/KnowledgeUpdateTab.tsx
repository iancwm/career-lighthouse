"use client"
import { useRef, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

// ── Types ─────────────────────────────────────────────────────────────────

interface ProfileFieldChange {
  old: string | null
  new: string
}

interface NewChunk {
  text: string
  source_type: string
  source_label: string
  career_type: string | null
  chunk_id: string
}

interface AlreadyCovered {
  excerpt: string
  source_doc: string
}

interface KBAnalysisResult {
  interpretation_bullets: string[]
  profile_updates: Record<string, Record<string, ProfileFieldChange>>
  employer_updates: Record<string, Record<string, ProfileFieldChange>>
  new_chunks: NewChunk[]
  already_covered: AlreadyCovered[]
}

// Mutable diff state for counsellor edits
interface DiffState {
  result: KBAnalysisResult
  profileEdits: Record<string, Record<string, string>>    // slug → field → edited new value
  employerEdits: Record<string, Record<string, string>>   // slug → field → edited new value
  chunkEdits: string[]                                     // parallel to result.new_chunks
}

// ── Component ─────────────────────────────────────────────────────────────

export default function KnowledgeUpdateTab({ onCommitted }: { onCommitted?: () => void }) {
  const [inputMode, setInputMode] = useState<"note" | "file">("note")
  const [noteText, setNoteText] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [state, setState] = useState<"idle" | "analysing" | "diff" | "error_analyse" | "error_commit" | "success">("idle")
  const [statusText, setStatusText] = useState("Comparing against knowledge base...")
  const [diff, setDiff] = useState<DiffState | null>(null)
  const [successMsg, setSuccessMsg] = useState("")
  const [alreadyCoveredOpen, setAlreadyCoveredOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const canAnalyse = inputMode === "note" ? noteText.trim().length > 0 : selectedFile !== null

  function resetToIdle() {
    if (statusTimerRef.current) clearTimeout(statusTimerRef.current)
    if (successTimerRef.current) clearTimeout(successTimerRef.current)
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setState("idle")
    setDiff(null)
    setAlreadyCoveredOpen(false)
  }

  async function handleAnalyse() {
    if (statusTimerRef.current) clearTimeout(statusTimerRef.current)
    if (successTimerRef.current) clearTimeout(successTimerRef.current)
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setState("analysing")
    setStatusText("Comparing against knowledge base...")
    statusTimerRef.current = setTimeout(() => setStatusText("Generating diff..."), 2000)

    const form = new FormData()
    if (inputMode === "note") {
      form.append("text", noteText.trim())
      form.append("source_type", "note")
    } else if (selectedFile) {
      form.append("file", selectedFile)
      form.append("source_type", "file")
    }

    try {
      const res = await fetch(`${API_URL}/api/kb/analyse`, { method: "POST", body: form, signal: controller.signal })
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current)
      if (!res.ok) {
        setState("error_analyse")
        return
      }
      const result: KBAnalysisResult = await res.json()
      // Initialise editable state from Claude's output
      const profileEdits: Record<string, Record<string, string>> = {}
      for (const [slug, fields] of Object.entries(result.profile_updates)) {
        profileEdits[slug] = {}
        for (const [field, change] of Object.entries(fields)) {
          profileEdits[slug][field] = change.new
        }
      }
      const employerEdits: Record<string, Record<string, string>> = {}
      for (const [slug, fields] of Object.entries(result.employer_updates ?? {})) {
        employerEdits[slug] = {}
        for (const [field, change] of Object.entries(fields)) {
          employerEdits[slug][field] = change.new
        }
      }
      const chunkEdits = result.new_chunks.map((c) => c.text)
      setDiff({ result, profileEdits, employerEdits, chunkEdits })
      setState("diff")
      setAlreadyCoveredOpen(false)
    } catch (err) {
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current)
      if (err instanceof Error && err.name === "AbortError") return  // intentional cancel
      setState("error_analyse")
    }
  }

  async function handleCommit() {
    if (!diff) return
    if (successTimerRef.current) clearTimeout(successTimerRef.current)

    // Build commit body from edited state
    const profileUpdates: Record<string, Record<string, ProfileFieldChange>> = {}
    for (const [slug, fields] of Object.entries(diff.result.profile_updates)) {
      profileUpdates[slug] = {}
      for (const [field, change] of Object.entries(fields)) {
        profileUpdates[slug][field] = {
          old: change.old,
          new: diff.profileEdits[slug]?.[field] ?? change.new,
        }
      }
    }
    const employerUpdates: Record<string, Record<string, ProfileFieldChange>> = {}
    for (const [slug, fields] of Object.entries(diff.result.employer_updates ?? {})) {
      employerUpdates[slug] = {}
      for (const [field, change] of Object.entries(fields)) {
        employerUpdates[slug][field] = {
          old: change.old,
          new: diff.employerEdits[slug]?.[field] ?? change.new,
        }
      }
    }
    const newChunks = diff.result.new_chunks.map((chunk, i) => ({
      ...chunk,
      text: diff.chunkEdits[i] ?? chunk.text,
    }))

    try {
      const res = await fetch(`${API_URL}/api/kb/commit-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_updates: profileUpdates, employer_updates: employerUpdates, new_chunks: newChunks }),
      })
      if (!res.ok) {
        setState("error_commit")
        return
      }
      const data = await res.json()
      const parts: string[] = []
      if (data.chunks_added > 0) parts.push(`${data.chunks_added} chunk${data.chunks_added !== 1 ? "s" : ""} added`)
      if (data.profiles_updated?.length > 0) parts.push(`${data.profiles_updated.length} profile${data.profiles_updated.length !== 1 ? "s" : ""} updated`)
      if (data.employers_updated?.length > 0) parts.push(`${data.employers_updated.length} employer${data.employers_updated.length !== 1 ? "s" : ""} updated`)
      setSuccessMsg(parts.length > 0 ? `Saved — ${parts.join(", ")}` : "Saved — no changes committed")
      setState("success")
      setNoteText("")
      setSelectedFile(null)
      setDiff(null)
      onCommitted?.()
      successTimerRef.current = setTimeout(() => setState("idle"), 4000)
    } catch {
      setState("error_commit")
    }
  }

  const newChunkCount = diff?.result.new_chunks.length ?? 0
  const profileFieldCount = diff
    ? Object.values(diff.result.profile_updates).reduce((n, f) => n + Object.keys(f).length, 0)
    : 0
  const employerFieldCount = diff
    ? Object.values(diff.result.employer_updates ?? {}).reduce((n, f) => n + Object.keys(f).length, 0)
    : 0
  const alreadyCoveredCount = diff?.result.already_covered.length ?? 0

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Review New Knowledge Before Saving</h2>
      <p className="text-sm text-gray-500 mb-4 max-w-3xl">
        Paste a counsellor note or upload a file. We will suggest searchable notes and structured fact updates for you to review before anything is saved.
      </p>

      {state === "success" && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {successMsg}
        </div>
      )}

      <div className="flex gap-6">
        {/* Left pane — 40% */}
        <div className="w-2/5 flex flex-col gap-4">
          {/* Input mode toggle */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              onClick={() => { setInputMode("note"); setSelectedFile(null) }}
              className={`flex-1 py-2 font-medium transition-colors ${inputMode === "note" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
              disabled={state === "analysing"}
            >
              Counsellor note
            </button>
            <button
              onClick={() => setInputMode("file")}
              className={`flex-1 py-2 font-medium transition-colors ${inputMode === "file" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
              disabled={state === "analysing"}
            >
              Uploaded file
            </button>
          </div>

          {/* Input area */}
          {inputMode === "note" ? (
            <textarea
              className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 min-h-[160px]"
              placeholder="Example: 'Goldman changed their EP sponsorship threshold to 50+ COMPASS for 2026.'"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              disabled={state === "analysing"}
            />
          ) : (
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-blue-400 transition-colors"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                const f = e.dataTransfer.files[0]
                if (f) setSelectedFile(f)
              }}
            >
              {selectedFile ? (
                <p className="text-sm text-gray-700 font-medium">{selectedFile.name}</p>
              ) : (
                <>
                  <p className="text-gray-500 text-sm">Drag and drop or click to choose a file</p>
                  <p className="text-xs text-gray-400 mt-1">Accepted formats: PDF, DOCX, TXT</p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setSelectedFile(f) }}
                disabled={state === "analysing"}
              />
            </div>
          )}

          <button
            onClick={handleAnalyse}
            disabled={!canAnalyse || state === "analysing"}
            className="w-full py-3 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Review proposed changes
          </button>

          {/* Interpretation bullets — shown in diff state */}
          {state === "diff" && diff && diff.result.interpretation_bullets.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="text-xs font-medium text-gray-500 mb-2">Summary of what will change:</p>
              <ul className="space-y-1">
                {diff.result.interpretation_bullets.map((b, i) => (
                  <li key={i} className="text-xs text-gray-700 flex gap-2">
                    <span className="text-blue-400 mt-0.5 shrink-0">•</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right pane — 60% */}
        <div className="w-3/5">
          {state === "idle" && (
            <div className="h-full min-h-[240px] flex items-center justify-center rounded-xl border-2 border-dashed border-gray-200">
              <p className="text-sm text-gray-400">Your review summary will appear here</p>
            </div>
          )}

          {state === "analysing" && (
            <div className="h-full min-h-[240px] flex flex-col items-center justify-center gap-3 rounded-xl border border-gray-200">
              <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-gray-500">{statusText}</p>
              <button onClick={resetToIdle} className="text-xs text-gray-400 hover:text-gray-600 underline mt-1">
                Cancel
              </button>
            </div>
          )}

          {(state === "error_analyse") && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
              <p>We could not prepare the review. Please try again or make the note more specific.</p>
              <button
                onClick={handleAnalyse}
                className="mt-3 px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                Retry
              </button>
            </div>
          )}

          {(state === "error_commit") && diff && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
              <p>We could not save these updates. Please retry.</p>
              <button
                onClick={handleCommit}
                className="mt-3 px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                Retry
              </button>
            </div>
          )}

          {(state === "diff" || state === "error_commit") && diff && (
            <div className="flex flex-col gap-4">
              {/* Summary bar */}
              <p className="text-xs text-gray-500">
                {newChunkCount} new chunk{newChunkCount !== 1 ? "s" : ""}
                {" · "}
                {profileFieldCount} career profile field{profileFieldCount !== 1 ? "s" : ""} updated
                {employerFieldCount > 0 && (
                  <> {" · "} {employerFieldCount} employer field{employerFieldCount !== 1 ? "s" : ""} updated</>
                )}
                {" · "}
                {alreadyCoveredCount} already covered
              </p>

              {/* Career Profile Changes */}
              {profileFieldCount > 0 && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Career Profile Updates</h3>
                  <div className="space-y-3">
                    {Object.entries(diff.result.profile_updates).map(([slug, fields]) =>
                      Object.entries(fields).map(([field, change]) => (
                        <div key={`${slug}-${field}`} className="rounded-lg border border-gray-200 p-3 text-xs">
                          <p className="font-medium text-gray-600 mb-1">
                            {slug} / {field}
                          </p>
                          {change.old && (
                            <p className="text-gray-400 line-through mb-1 leading-relaxed">{change.old}</p>
                          )}
                          <textarea
                            className="w-full border border-blue-200 bg-blue-50 rounded p-2 text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 leading-relaxed"
                            rows={3}
                            value={diff.profileEdits[slug]?.[field] ?? change.new}
                            onChange={(e) => {
                              const val = e.target.value
                              setDiff((prev) => {
                                if (!prev) return prev
                                return {
                                  ...prev,
                                  profileEdits: {
                                    ...prev.profileEdits,
                                    [slug]: { ...prev.profileEdits[slug], [field]: val },
                                  },
                                }
                              })
                            }}
                          />
                        </div>
                      ))
                    )}
                  </div>
                </section>
              )}

              {/* Employer Fact Updates */}
              {employerFieldCount > 0 && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Employer Fact Updates</h3>
                  <div className="space-y-3">
                    {Object.entries(diff.result.employer_updates ?? {}).map(([slug, fields]) =>
                      Object.entries(fields).map(([field, change]) => (
                        <div key={`${slug}-${field}`} className="rounded-lg border border-gray-200 p-3 text-xs">
                          <p className="font-medium text-gray-600 mb-1">
                            {slug} / {field}
                          </p>
                          {change.old && (
                            <p className="text-gray-400 line-through mb-1 leading-relaxed">{change.old}</p>
                          )}
                          <textarea
                            className="w-full border border-blue-200 bg-blue-50 rounded p-2 text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 leading-relaxed"
                            rows={3}
                            value={diff.employerEdits[slug]?.[field] ?? change.new}
                            onChange={(e) => {
                              const val = e.target.value
                              setDiff((prev) => {
                                if (!prev) return prev
                                return {
                                  ...prev,
                                  employerEdits: {
                                    ...prev.employerEdits,
                                    [slug]: { ...prev.employerEdits[slug], [field]: val },
                                  },
                                }
                              })
                            }}
                          />
                        </div>
                      ))
                    )}
                  </div>
                </section>
              )}

              {/* New Knowledge Chunks */}
              {newChunkCount > 0 && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">New Searchable Notes</h3>
                  <div className="space-y-2">
                    {diff.result.new_chunks.map((chunk, i) => (
                      <div key={chunk.chunk_id || i} className="rounded-lg border border-gray-200 p-3 text-xs">
                        {chunk.career_type && (
                          <span className="inline-block mb-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs">
                            {chunk.career_type}
                          </span>
                        )}
                        <textarea
                          className="w-full border border-gray-200 rounded p-2 text-gray-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 leading-relaxed"
                          rows={4}
                          value={diff.chunkEdits[i] ?? chunk.text}
                          onChange={(e) => {
                            const val = e.target.value
                            setDiff((prev) => {
                              if (!prev) return prev
                              const edits = [...prev.chunkEdits]
                              edits[i] = val
                              return { ...prev, chunkEdits: edits }
                            })
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Already Covered */}
              {alreadyCoveredCount > 0 && (
                <section>
                  <button
                    onClick={() => setAlreadyCoveredOpen((o) => !o)}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    <span>{alreadyCoveredOpen ? "▾" : "▸"}</span>
                    Already covered by existing documents ({alreadyCoveredCount})
                  </button>
                  {alreadyCoveredOpen && (
                    <div className="mt-2 space-y-2">
                      {diff.result.already_covered.map((ac, i) => (
                        <div key={i} className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-500">
                          <p className="font-medium text-gray-400 mb-1">{ac.source_doc}</p>
                          <p className="leading-relaxed">{ac.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {/* Nothing to commit */}
              {newChunkCount === 0 && profileFieldCount === 0 && employerFieldCount === 0 && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                  No new updates suggested. This content appears to already be covered.
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-3 pt-2 border-t border-gray-100">
                <button
                  onClick={handleCommit}
                  disabled={newChunkCount === 0 && profileFieldCount === 0 && employerFieldCount === 0}
                  className="px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  Save reviewed changes
                </button>
                <button
                  onClick={() => {
                    setDiff(null)
                    setState("idle")
                  }}
                  className="px-4 py-2.5 border border-gray-300 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  Start over
                </button>
                <button
                  onClick={resetToIdle}
                  className="px-4 py-2.5 text-red-600 text-sm font-medium rounded-xl hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-400"
                >
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
