"use client"
import { useState } from "react"
import FactDataView from "../forms/FactDataView"
import {
  Fact,
  getFactKeyValue,
  getFactTypeBadgeClass,
  getFactTypeLabel,
  getFactSourceLabel,
} from "@/types/facts"

interface ExtractedFactsModalProps {
  extracted: Fact[]
  existing: Fact[]
  onAdd: (facts: Fact[]) => void
  onClose: () => void
  isLoading?: boolean
  error?: string
}

export default function ExtractedFactsModal({
  extracted,
  existing,
  onAdd,
  onClose,
  isLoading,
  error,
}: ExtractedFactsModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(extracted.map((f) => f.slug)))

  // Deduplicate: facts already in list by slug
  const existingSlugs = new Set(existing.map((f) => f.slug))
  const newFacts = extracted.filter((f) => !existingSlugs.has(f.slug))
  const duplicates = extracted.filter((f) => existingSlugs.has(f.slug))

  function toggle(slug: string) {
    const next = new Set(selected)
    if (next.has(slug)) {
      next.delete(slug)
    } else {
      next.add(slug)
    }
    setSelected(next)
  }

  function handleAdd() {
    const factsToAdd = extracted.filter((f) => selected.has(f.slug))
    onAdd(factsToAdd)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Extract facts from notes</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 focus:outline-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
                <p className="text-sm text-gray-600">Extracting facts from notes...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-4 mb-4">
              <p className="text-sm text-red-700">
                <span className="font-medium">Extraction failed:</span> {error}
              </p>
            </div>
          )}

          {!isLoading && extracted.length === 0 && !error && (
            <div className="text-center py-12">
              <p className="text-sm text-gray-500">No facts could be extracted from the notes.</p>
              <p className="text-xs text-gray-400 mt-2">Try adding more detailed information to the counsellor notes.</p>
            </div>
          )}

          {!isLoading && extracted.length > 0 && (
            <>
              {/* New facts */}
              {newFacts.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">New facts ({newFacts.length})</h3>
                  <div className="space-y-2.5">
                    {newFacts.map((fact) => (
                      <label
                        key={fact.slug}
                        className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 hover:bg-blue-50 cursor-pointer transition-colors"
                      >
                          <input
                            type="checkbox"
                            checked={selected.has(fact.slug)}
                            onChange={() => toggle(fact.slug)}
                            className="w-4 h-4 mt-0.5 rounded"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                            <span className={`inline-block rounded-full border px-2.5 py-1 text-xs font-medium ${getFactTypeBadgeClass(fact.type)}`}>
                              {getFactTypeLabel(fact.type)}
                            </span>
                          </div>
                          <div className="flex items-baseline gap-2 text-sm mb-1">
                            <code className="font-mono text-xs text-gray-600 truncate">{fact.slug}</code>
                            <span className="text-xs text-gray-500">{getFactKeyValue(fact)}</span>
                          </div>
                          <FactDataView data={fact.data} className="mt-2" />
                          <p className="text-xs text-gray-500">
                            Confidence: {fact.confidence}% · {getFactSourceLabel(fact.source)}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Duplicate facts */}
              {duplicates.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Already in list ({duplicates.length})</h3>
                  <div className="space-y-2.5">
                    {duplicates.map((fact) => (
                      <div
                        key={fact.slug}
                        className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50 opacity-60"
                      >
                          <input type="checkbox" disabled className="w-4 h-4 mt-0.5 rounded" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                            <span className={`inline-block rounded-full border px-2.5 py-1 text-xs font-medium ${getFactTypeBadgeClass(fact.type)}`}>
                              {getFactTypeLabel(fact.type)}
                            </span>
                          </div>
                          <div className="flex items-baseline gap-2 text-sm mb-1">
                            <code className="font-mono text-xs text-gray-600 truncate">{fact.slug}</code>
                            <span className="text-xs text-gray-500">{getFactKeyValue(fact)}</span>
                          </div>
                          <FactDataView data={fact.data} className="mt-2" />
                          <p className="text-xs text-gray-500">
                            Confidence: {fact.confidence}% · {getFactSourceLabel(fact.source)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 text-gray-700 text-sm font-medium hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            disabled={selected.size === 0 || isLoading}
            className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Add {selected.size > 0 && `${selected.size}`} fact{selected.size !== 1 ? "s" : ""}
          </button>
        </div>
      </div>
    </div>
  )
}
