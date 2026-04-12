"use client"
import { useCallback, useEffect, useRef, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024 // 10MB
const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]
const SESSION_PAGE_SIZE = 20

interface KnowledgeSession {
  id: string
  status: string
  raw_input: string
  intent_cards: Array<{ card_id: string; domain: string; summary: string; status: string }>
  created_by: string
  created_at: string
  updated_at: string
}

interface ParsedFile {
  filename: string
  size: number
  text: string
}

interface SessionInboxProps {
  onSelectSession: (sessionId: string) => void
}

type UploadState = "idle" | "uploading" | "parsed" | "error"

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function SessionInbox({ onSelectSession }: SessionInboxProps) {
  const [sessions, setSessions] = useState<KnowledgeSession[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [rawInput, setRawInput] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [showAllSessions, setShowAllSessions] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>("idle")
  const [parsedFile, setParsedFile] = useState<ParsedFile | null>(null)
  const [uploadError, setUploadError] = useState("")
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  // ---------- File upload handlers ----------

  async function handleFileUpload(file: File) {
    // Client-side size check
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadState("error")
      setUploadError("File exceeds maximum upload size (10MB).")
      return
    }

    // Client-side type check
    if (!ACCEPTED_TYPES.includes(file.type) && !file.name.match(/\.(pdf|docx|txt)$/i)) {
      setUploadState("error")
      setUploadError(
        "Filename contains invalid characters. Use letters, numbers, spaces, dots, hyphens, underscores, or parentheses."
      )
      return
    }

    setUploadState("uploading")
    setUploadError("")

    try {
      const formData = new FormData()
      formData.append("file", file)

      const res = await fetch(`${API_URL}/api/sessions/parse-file`, {
        method: "POST",
        body: formData,
      })

      if (!res.ok) {
        const text = await res.text()
        if (res.status === 413) {
          setUploadState("error")
          setUploadError("File exceeds maximum upload size (10MB).")
        } else if (res.status === 400) {
          setUploadState("error")
          setUploadError(text || "Filename contains invalid characters. Use letters, numbers, spaces, dots, hyphens, underscores, or parentheses.")
        } else if (res.status === 422) {
          setUploadState("error")
          setUploadError(text || "Could not extract text from this file. Try pasting the content manually.")
        } else {
          setUploadState("error")
          setUploadError(text || "Could not parse file.")
        }
        return
      }

      const data = await res.json()
      setParsedFile({
        filename: data.filename,
        size: file.size,
        text: data.text,
      })
      setUploadState("parsed")
    } catch {
      setUploadState("error")
      setUploadError("Could not extract text from this file. Try pasting the content manually.")
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileUpload(file)
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFileUpload(file)
    // Reset input so the same file can be re-selected
    e.target.value = ""
  }

  function handleUseParsedText() {
    if (parsedFile) {
      setRawInput(parsedFile.text)
      setUploadState("idle")
      setParsedFile(null)
      // Focus the textarea after copying
      setTimeout(() => textareaRef.current?.focus(), 50)
    }
  }

  function handleRemoveFile() {
    setUploadState("idle")
    setParsedFile(null)
    setUploadError("")
  }

  function scrollToTextarea() {
    textareaRef.current?.scrollIntoView({ behavior: "smooth" })
    setTimeout(() => textareaRef.current?.focus(), 300)
  }

  if (loading) return <p className="text-sm text-muted">Loading sessions…</p>

  const displayedSessions = showAllSessions ? sessions : sessions.slice(0, SESSION_PAGE_SIZE)

  return (
    <div>
      {error && (
        <div className="mb-4 rounded border border-error-200 bg-error-50 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded border border-success-200 bg-success-50 px-4 py-3 text-sm text-success">
          {notice}
        </div>
      )}

      {/* New Session Form */}
      <div className="mb-6 rounded-xl border border-line bg-canvas p-4">
        <h3 className="text-sm font-semibold text-ink mb-2">New Publishing Session</h3>
        <p className="text-sm text-muted mb-3">
          Paste your meeting notes or upload a document to get started.
        </p>

        {/* 2-column grid: paste + upload */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Left: Paste textarea */}
          <div>
            <textarea
              ref={textareaRef}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              className="w-full rounded border border-line bg-surface px-3 py-2 text-sm min-h-[160px] focus:outline-none focus:ring-2 focus:ring-teal-500"
              placeholder="Example: Met with Goldman Sachs — they raised EP requirement from EP3 to EP4. Consulting market feels more competitive this year…"
            />
          </div>

          {/* Right: Upload zone */}
          <div>
            {uploadState === "idle" && (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center min-h-[160px] rounded border-2 border-dashed cursor-pointer transition-colors ${
                  dragOver
                    ? "border-teal-500 bg-teal-50"
                    : "border-line bg-canvas hover:border-muted"
                }`}
              >
                <svg
                  className="w-8 h-8 text-muted mb-2"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                  />
                </svg>
                <p className="text-sm text-ink font-medium">Upload a document</p>
                <p className="text-xs text-muted mt-1">PDF, DOCX, TXT (max 10 MB)</p>
                <p className="text-xs text-muted mt-0.5">Drag & drop or click to browse</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                  onChange={handleFileInputChange}
                  className="hidden"
                />
              </div>
            )}

            {uploadState === "uploading" && (
              <div className="flex flex-col items-center justify-center min-h-[160px] rounded border-2 border-dashed border-line bg-canvas">
                <div className="animate-pulse text-sm text-muted">Parsing document…</div>
              </div>
            )}

            {uploadState === "error" && (
              <div className="flex flex-col items-center justify-center min-h-[160px] rounded border-2 border-dashed border-error-200 bg-error-50">
                <p className="text-sm text-error text-center px-4">{uploadError}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleRemoveFile()
                  }}
                  className="mt-3 text-sm text-teal-600 hover:text-teal-700 font-medium"
                >
                  Try another file
                </button>
              </div>
            )}
          </div>
        </div>

        {/* File parse preview block */}
        {uploadState === "parsed" && parsedFile && (
          <div className="mb-4 rounded-lg border border-line bg-surface p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink truncate">{parsedFile.filename}</p>
                <p className="text-xs text-muted">{formatFileSize(parsedFile.size)}</p>
              </div>
            </div>
            <div className="max-h-40 overflow-y-auto rounded border border-line bg-surface-2 px-3 py-2 text-xs text-ink whitespace-pre-wrap font-mono">
              {parsedFile.text}
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={handleUseParsedText}
                className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 transition-colors"
                style={{ minHeight: "44px" }}
              >
                Use this text
              </button>
              <button
                onClick={handleRemoveFile}
                className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-muted hover:text-ink transition-colors"
                style={{ minHeight: "44px" }}
              >
                Remove file
              </button>
            </div>
          </div>
        )}

        {/* Create Session button */}
        <button
          onClick={createSession}
          disabled={creating || !rawInput.trim()}
          className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-40 transition-colors"
          style={{ minHeight: "44px" }}
        >
          {creating ? "Creating…" : "Create Session"}
        </button>
      </div>

      {/* Sessions List */}
      {sessions.length === 0 ? (
        /* Empty state */
        <div className="rounded-xl border border-line bg-surface-2 p-8 text-center">
          <p className="text-2xl mb-3">📝</p>
          <h4 className="text-lg font-semibold text-ink mb-2">No sessions yet</h4>
          <p className="text-sm text-muted max-w-md mx-auto mb-6">
            Paste your meeting notes or upload a document above to get started.
            The system will extract individual update cards for each employer
            and track mentioned.
          </p>
          <button
            onClick={scrollToTextarea}
            className="rounded-xl bg-teal-600 px-6 py-2 text-sm font-medium text-white hover:bg-teal-700 transition-colors"
            style={{ minHeight: "44px" }}
          >
            Start a session
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {displayedSessions.map((session) => {
              const pendingCards = session.intent_cards.filter((c) => c.status === "pending").length
              return (
                <button
                  key={session.id}
                  onClick={() => onSelectSession(session.id)}
                  className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-left hover:border-muted transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0 flex-1 mr-4">
                      <p className="text-sm font-medium text-ink">
                        {session.status === "analyzed" ? "Analyzed" : "In Progress"}
                      </p>
                      <p className="text-xs text-muted mt-1 truncate">
                        {session.raw_input.slice(0, 100)}
                        {session.raw_input.length > 100 ? "…" : ""}
                      </p>
                      <p className="text-xs text-muted mt-0.5 font-mono">
                        {new Date(session.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          session.status === "analyzed"
                            ? "bg-teal-50 text-teal-700"
                            : "bg-surface-2 text-muted"
                        }`}
                      >
                        {session.status}
                      </span>
                      {pendingCards > 0 && (
                        <p className="text-xs text-muted mt-1">{pendingCards} pending</p>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Show more button */}
          {sessions.length > SESSION_PAGE_SIZE && !showAllSessions && (
            <div className="mt-4 text-center">
              <button
                onClick={() => setShowAllSessions(true)}
                className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-muted hover:text-ink transition-colors"
                style={{ minHeight: "44px" }}
              >
                Show more ({sessions.length - SESSION_PAGE_SIZE} more sessions)
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
