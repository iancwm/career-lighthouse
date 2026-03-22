"use client"
import { useEffect, useState } from "react"

interface Doc { doc_id: string; filename: string; chunk_count: number; uploaded_at: string }
interface Props { refreshKey: number }

export default function DocList({ refreshKey }: Props) {
  const [docs, setDocs] = useState<Doc[]>([])
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  useEffect(() => {
    fetch(`${apiUrl}/api/docs`).then(r => r.json()).then(setDocs)
  }, [refreshKey])

  async function handleDelete(docId: string) {
    await fetch(`${apiUrl}/api/docs/${encodeURIComponent(docId)}`, { method: "DELETE" })
    setDocs(docs.filter(d => d.doc_id !== docId))
  }

  if (!docs.length) return <p className="text-sm text-gray-400 mt-4">No documents uploaded yet.</p>

  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium text-gray-600 mb-2">Knowledge Base ({docs.length} documents)</h3>
      <ul className="space-y-1">
        {docs.map(doc => (
          <li key={doc.doc_id} className="flex items-center justify-between text-sm bg-white border rounded px-3 py-2">
            <span className="truncate">{doc.filename}</span>
            <span className="text-gray-400 mx-3">{doc.chunk_count} chunks</span>
            <button onClick={() => handleDelete(doc.doc_id)} className="text-red-500 hover:text-red-700 text-xs">✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
