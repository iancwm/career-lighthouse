"use client"

interface StatCardsProps {
  totalDocs: number
  totalChunks: number
  lowConfidenceCount: number
  avgMatchScore: number | null
  diversityScore: number | null
}

function scoreColor(value: number | null, greenThresh: number, amberThresh: number): string {
  if (value === null) return "text-gray-400"
  if (value >= greenThresh) return "text-green-700"
  if (value >= amberThresh) return "text-amber-600"
  return "text-red-600"
}

export default function StatCards({
  totalDocs,
  totalChunks,
  lowConfidenceCount,
  avgMatchScore,
  diversityScore,
}: StatCardsProps) {
  const cards = [
    {
      label: "Documents",
      value: totalDocs.toString(),
      color: "text-gray-900",
    },
    {
      label: "Chunks",
      value: totalChunks.toString(),
      color: "text-gray-900",
    },
    {
      label: "Weak Queries (7d)",
      value: lowConfidenceCount.toString(),
      color: lowConfidenceCount > 5 ? "text-red-600" : "text-gray-900",
    },
    {
      label: "Avg Match Score",
      value: avgMatchScore !== null ? avgMatchScore.toFixed(2) : "—",
      color: scoreColor(avgMatchScore, 0.5, 0.35),
    },
    {
      label: "Retrieval Diversity",
      value: diversityScore !== null ? diversityScore.toFixed(1) : "—",
      color: scoreColor(diversityScore, 3.0, 1.5),
    },
  ]

  return (
    <div className="grid grid-cols-5 gap-3 mb-6">
      {cards.map((c) => (
        <div key={c.label} className="border rounded-lg p-4 bg-white">
          <p className="text-xs text-gray-500 mb-1">{c.label}</p>
          <p className={`text-xl font-semibold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}
