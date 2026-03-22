"use client"
import { useState } from "react"

interface Props { onUploaded: () => void }

export default function KnowledgeUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState("")
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (!files.length) return
    setUploading(true)
    setMessage("")
    for (const file of files) {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${apiUrl}/api/ingest`, { method: "POST", body: form })
      const data = await res.json()
      setMessage(prev => prev + `✓ ${file.name} (${data.chunk_count} chunks)\n`)
    }
    setUploading(false)
    onUploaded()
  }

  async function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    setMessage("")
    for (const file of files) {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${apiUrl}/api/ingest`, { method: "POST", body: form })
      const data = await res.json()
      setMessage(prev => prev + `✓ ${file.name} (${data.chunk_count} chunks)\n`)
    }
    setUploading(false)
    onUploaded()
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Upload Knowledge</h2>
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
      >
        <p className="text-gray-500 mb-2">Drag &amp; drop files here</p>
        <p className="text-sm text-gray-400">PDF, DOCX, TXT accepted</p>
        <input type="file" multiple accept=".pdf,.docx,.txt" className="hidden" id="file-input" onChange={handleFileInput} />
        <label htmlFor="file-input" className="mt-3 inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer text-sm">
          Browse Files
        </label>
      </div>
      {uploading && <p className="mt-2 text-sm text-blue-600">Uploading…</p>}
      {message && <pre className="mt-2 text-sm text-green-700 whitespace-pre-wrap">{message}</pre>}
    </div>
  )
}
