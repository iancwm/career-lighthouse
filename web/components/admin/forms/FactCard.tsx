"use client"

import FactDataView from "./FactDataView"
import LifecycleBadge from "../LifecycleBadge"
import ProvenancePanel from "../ProvenancePanel"
import {
  Fact,
  getFactKeyValue,
  getFactSourceLabel,
  getFactTypeBadgeClass,
  getFactTypeLabel,
  normalizeFactLifecycle,
} from "@/types/facts"

interface FactCardProps {
  fact: Fact
  supersededBy?: string | null
  historyHref?: string | null
  onDelete?: (slug: string) => void
}

export default function FactCard({ fact, supersededBy, historyHref, onDelete }: FactCardProps) {
  const lifecycle = normalizeFactLifecycle(fact)
  const keyField = getFactKeyValue(fact)
  const typeColor = getFactTypeBadgeClass(fact.type)
  const sourceLabel = getFactSourceLabel(fact.source)
  const textMuted = lifecycle !== "active"

  return (
    <div
      className={`group flex items-start justify-between gap-3 rounded-lg border p-3 transition-colors ${
        textMuted ? "border-[#D8D0C4] bg-[#FFFDFC] text-[#5F6B76]" : "border-gray-200 bg-white hover:bg-gray-50"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          <span className={`inline-block rounded-full border px-2.5 py-1 text-xs font-medium ${typeColor}`}>
            {getFactTypeLabel(fact.type)}
          </span>
          <LifecycleBadge lifecycle={fact.lifecycle} deleted={fact.deleted} />
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <code className="text-xs font-mono text-gray-600 truncate">{fact.slug}</code>
          <span className="text-xs text-gray-500">{keyField}</span>
        </div>
        <div className={textMuted ? "opacity-80" : ""}>
          <FactDataView data={fact.data} className="mt-2" />
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="text-gray-500">
            Confidence: <span className="font-semibold text-gray-700">{fact.confidence}%</span>
          </span>
          <span className="text-gray-400">{new Date(fact.timestamp).toLocaleDateString()}</span>
        </div>
        <div className="mt-3">
          <ProvenancePanel
            source={sourceLabel}
            sourceDate={fact.source_timestamp || fact.timestamp}
            lastUpdated={fact.last_updated || fact.source_timestamp || fact.timestamp}
            supersededBy={supersededBy || fact.superseded_by || "Unknown"}
            auditHref={fact.audit_url || historyHref}
          />
        </div>
      </div>

      {onDelete && (
        <button
          onClick={() => onDelete(fact.slug)}
          className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 flex-shrink-0 min-h-11 min-w-11 p-2.5 text-gray-400 hover:text-red-500 transition-opacity focus:outline-none focus:ring-2 focus:ring-red-400 rounded"
          aria-label={`Delete ${fact.slug}`}
          title="Delete fact"
        >
          ✕
        </button>
      )}
    </div>
  )
}
