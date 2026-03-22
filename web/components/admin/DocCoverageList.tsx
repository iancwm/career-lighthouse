"use client"

interface DocCoverageItem {
  filename: string
  chunk_count: number
  coverage_status: "good" | "thin"
  has_overlap_warning: boolean
}

interface Props {
  docs: DocCoverageItem[]
}

export default function DocCoverageList({ docs }: Props) {
  if (!docs.length) {
    return <p className="text-sm text-gray-400">No documents uploaded yet.</p>
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Document Coverage
      </h3>
      <ul className="space-y-1">
        {docs.map((doc) => (
          <li
            key={doc.filename}
            className="flex items-center justify-between text-sm bg-white border rounded px-3 py-2"
          >
            <span className="truncate flex-1 mr-2">{doc.filename}</span>
            <span className="text-gray-400 text-xs mr-2">{doc.chunk_count} chunks</span>
            {doc.has_overlap_warning && (
              <span
                title="This document overlaps with another — see Redundancy panel"
                className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded mr-2"
              >
                overlap
              </span>
            )}
            <span
              className={`text-xs px-2 py-0.5 rounded font-medium ${
                doc.coverage_status === "good"
                  ? "bg-green-100 text-green-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {doc.coverage_status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
