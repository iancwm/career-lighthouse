"use client"

interface LowConfidenceQuery {
  ts: string
  query_text: string
  max_score: number
  doc_matched: string | null
}

interface Props {
  avgMatchScore: number | null
  queries: LowConfidenceQuery[]
}

export default function LowConfidenceLog({ avgMatchScore, queries }: Props) {
  // avgMatchScore null = no log data yet; non-null but empty = no weak queries
  if (avgMatchScore === null) {
    return (
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Weak Queries (7d)</h3>
        <p className="text-sm text-gray-400">
          No data yet — use the student chat to generate query history.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Weak Queries (7d)
        <span className="ml-2 text-xs font-normal text-gray-400">
          score &lt; 0.35
        </span>
      </h3>
      {queries.length === 0 ? (
        <p className="text-sm text-green-700">No weak matches in the last 7 days.</p>
      ) : (
        <ul className="space-y-2">
          {queries.map((q, i) => (
            <li key={i} className="border rounded p-3 bg-white text-sm">
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-700 truncate flex-1 mr-2">{q.query_text}</span>
                <span className="text-xs font-mono bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                  {q.max_score.toFixed(3)}
                </span>
              </div>
              {/* Score bar */}
              <div className="w-full bg-gray-100 rounded-full h-1 mt-1">
                <div
                  className="bg-red-400 h-1 rounded-full"
                  style={{ width: `${Math.min(q.max_score * 100, 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {new Date(q.ts).toLocaleString()}
                {q.doc_matched && ` · ${q.doc_matched}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
