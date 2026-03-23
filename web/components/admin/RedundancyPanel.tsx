"use client"

interface OverlapPair {
  doc_a: string
  doc_b: string
  overlap_pct: number
  recommendation: string
}

interface Props {
  pairs: OverlapPair[]
}

export default function RedundancyPanel({ pairs }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1">
        Redundant Documents
        <span
          title="Overlapping documents waste token budget and can produce contradictory answers."
          className="text-gray-400 cursor-help text-xs"
        >
          ⓘ
        </span>
      </h3>
      {pairs.length === 0 ? (
        <p className="text-sm text-green-700">No overlapping documents detected.</p>
      ) : (
        <ul className="space-y-2">
          {pairs.map((p, i) => (
            <li key={i} className="border rounded p-3 bg-amber-50 text-sm">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-amber-800">
                  {(p.overlap_pct * 100).toFixed(0)}% overlap
                </span>
              </div>
              <p className="text-gray-700 text-xs">
                <span className="font-medium">{p.doc_a}</span>
                {" ↔ "}
                <span className="font-medium">{p.doc_b}</span>
              </p>
              <p className="text-xs text-amber-700 mt-1">{p.recommendation}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
