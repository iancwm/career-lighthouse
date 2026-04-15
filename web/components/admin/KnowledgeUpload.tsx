"use client"
import { useState } from "react"
import { adminFetch } from "@/lib/admin-api"

interface Props { onUploaded: () => void }

export default function KnowledgeUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState("")
  const [warnings, setWarnings] = useState<string[]>([])

  async function uploadFiles(files: File[]) {
    setUploading(true)
    setMessage("")
    setWarnings([])
    for (const file of files) {
      const form = new FormData()
      form.append("file", file)
      const res = await adminFetch("/api/ingest", { method: "POST", body: form })
      if (!res.ok) {
        setMessage((prev) => prev + `✗ ${file.name}: upload failed (${res.status})\n`)
        continue
      }
      const data = await res.json()
      setMessage((prev) => prev + `✓ ${file.name} (${data.chunk_count} chunks)\n`)
      if (data.similarity_warning) {
        setWarnings((prev) => [...prev, `${file.name}: ${data.similarity_warning}`])
      }
    }
    setUploading(false)
    onUploaded()
  }

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (!files.length) return
    await uploadFiles(files)
  }

  async function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    await uploadFiles(files)
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Upload Source Documents</h2>
      <p className="text-sm text-gray-500 mb-3">
        Add PDFs, DOCX files, or text notes that should be searchable in student chat.
      </p>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
      >
        <p className="text-gray-600 mb-2">Drag and drop files here</p>
        <p className="text-sm text-gray-400">Accepted formats: PDF, DOCX, TXT</p>
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.txt"
          className="hidden"
          id="file-input"
          onChange={handleFileInput}
        />
        <label
          htmlFor="file-input"
          className="mt-3 inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer text-sm"
        >
          Choose files
        </label>
      </div>
      <p className="mt-2 text-xs text-gray-400">
        Uploaded documents are indexed into the knowledge base. They do not change employer facts or career profile summaries automatically.
      </p>
      {uploading && <p className="mt-2 text-sm text-blue-600">Uploading files…</p>}
      {message && (
        <pre className="mt-2 text-sm text-green-700 whitespace-pre-wrap">{message}</pre>
      )}
      {warnings.map((w, i) => (
        <div
          key={i}
          className="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          ⚠️ {w}
        </div>
      ))}
    </div>
  )
}
