"use client"
import { useState } from "react"

interface ChunkResult {
  source_filename: string
  excerpt: string
  score: number
}

interface Props {
  apiUrl: string | undefined
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 0.5
      ? "bg-green-100 text-green-800"
      : score >= 0.35
      ? "bg-amber-100 text-amber-800"
      : "bg-red-100 text-red-800"
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-medium ${color}`}>
      {score.toFixed(3)}
    </span>
  )
}

export default function TestQueryBox({ apiUrl }: Props) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<ChunkResult[] | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/kb/test-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      })
      if (!res.ok) {
        setResults([])
        return
      }
      setResults(await res.json())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Test Query</h3>
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a student question…"
          className="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {results !== null && (
        results.length === 0 ? (
          <p className="text-sm text-gray-400">
            No chunks matched. Check that the KB has indexed content.
          </p>
        ) : (
          <ul className="space-y-2">
            {results.map((r, i) => (
              <li key={i} className="border rounded p-3 bg-white text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <ScoreBadge score={r.score} />
                  <span className="text-gray-500 text-xs truncate">{r.source_filename}</span>
                </div>
                <p className="text-gray-700 text-xs leading-relaxed">{r.excerpt}</p>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  )
}
