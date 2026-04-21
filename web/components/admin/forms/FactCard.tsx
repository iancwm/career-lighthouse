"use client"

import FactDataView from "./FactDataView"

interface Fact {
  slug: string
  type: string
  data: Record<string, unknown>
  confidence: number
  source: string
  timestamp: string
  deleted?: boolean
}

interface FactCardProps {
  fact: Fact
  onDelete?: (slug: string) => void
}

function getKeyField(fact: Fact): string {
  const { type, data } = fact
  switch (type) {
    case "alumni":
      return data.name ? String(data.name) : "(unnamed)"
    case "timeline_phase":
      return data.phase_name ? String(data.phase_name) : "(unnamed)"
    case "interview_stage":
      return data.name ? String(data.name) : `Stage ${data.order || "?"}`
    case "compensation":
      return data.role_level ? String(data.role_level) : "(unnamed)"
    case "skill_requirement":
      return "(skill)"
    default:
      return "(unknown)"
  }
}

function getTypeColor(type: string): string {
  const colors: Record<string, string> = {
    alumni: "bg-purple-100 text-purple-700 border-purple-200",
    timeline_phase: "bg-blue-100 text-blue-700 border-blue-200",
    interview_stage: "bg-green-100 text-green-700 border-green-200",
    compensation: "bg-orange-100 text-orange-700 border-orange-200",
    skill_requirement: "bg-pink-100 text-pink-700 border-pink-200",
  }
  return colors[type] || "bg-gray-100 text-gray-700 border-gray-200"
}

export default function FactCard({ fact, onDelete }: FactCardProps) {
  const keyField = getKeyField(fact)
  const typeColor = getTypeColor(fact.type)
  const sourceLabel = {
    counselor: "Counselor",
    inferred: "Inferred",
    direct_from_alumni: "Alumni",
  }[fact.source] || fact.source

  return (
    <div className="group flex items-start justify-between gap-3 rounded-lg border border-gray-200 p-3 bg-white hover:bg-gray-50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border ${typeColor}`}>
            {fact.type.replace(/_/g, " ")}
          </span>
          <span className="text-xs text-gray-500">{sourceLabel}</span>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <code className="text-xs font-mono text-gray-600 truncate">{fact.slug}</code>
          <span className="text-xs text-gray-500">{keyField}</span>
        </div>
        <FactDataView data={fact.data} className="mt-2" />
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-500">Confidence: <span className="font-semibold text-gray-700">{fact.confidence}%</span></span>
          <span className="text-gray-400">{new Date(fact.timestamp).toLocaleDateString()}</span>
        </div>
      </div>

      {onDelete && (
        <button
          onClick={() => onDelete(fact.slug)}
          className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 transition-opacity focus:outline-none focus:ring-2 focus:ring-red-400 rounded"
          aria-label={`Delete ${fact.slug}`}
          title="Delete fact"
        >
          ✕
        </button>
      )}
    </div>
  )
}
