"use client"
import { useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"

interface Doc { doc_id: string; filename: string; chunk_count: number; uploaded_at: string }
interface Props { refreshKey: number; onDeleted?: () => void }

export default function DocList({ refreshKey, onDeleted }: Props) {
  const [docs, setDocs] = useState<Doc[]>([])

  useEffect(() => {
    adminFetch("/api/docs").then(r => r.json()).then(setDocs)
  }, [refreshKey])

  async function handleDelete(docId: string) {
    const res = await adminFetch(`/api/docs/${encodeURIComponent(docId)}`, { method: "DELETE" })
    if (!res.ok) return
    setDocs(docs.filter(d => d.doc_id !== docId))
    onDeleted?.()
  }

  if (!docs.length) return <p className="text-sm text-gray-400 mt-4">No source documents uploaded yet.</p>

  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium text-gray-600 mb-1">Indexed Documents ({docs.length})</h3>
      <p className="text-xs text-gray-500 mb-2">
        These files are searchable in chat. Delete a file here if it is outdated or duplicated.
      </p>
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
