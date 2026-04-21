"use client"

type FactData = Record<string, unknown>

interface FactDataViewProps {
  data: FactData
  className?: string
}

const IGNORED_KEYS = new Set([
  "slug",
  "type",
  "confidence",
  "source",
  "timestamp",
  "trace_id",
  "deleted",
  "id",
  "status",
])

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === "string") return value.trim().length === 0
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length === 0
  return false
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value.trim()
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  if (Array.isArray(value)) {
    return value
      .map((item) => formatValue(item))
      .filter((item) => item.length > 0)
      .join(", ")
  }
  if (typeof value === "object") {
    const parts = Object.entries(value as Record<string, unknown>)
      .filter(([key, nestedValue]) => !IGNORED_KEYS.has(key) && !isEmptyValue(nestedValue))
      .map(([key, nestedValue]) => `${humanizeKey(key)}: ${formatValue(nestedValue)}`)
    if (parts.length > 0) return parts.join("; ")
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

export function getVisibleFactDataEntries(data: FactData): Array<{ key: string; value: string }> {
  return Object.entries(data)
    .filter(([key, value]) => !IGNORED_KEYS.has(key) && !isEmptyValue(value))
    .map(([key, value]) => ({ key: humanizeKey(key), value: formatValue(value) }))
}

export default function FactDataView({ data, className = "" }: FactDataViewProps) {
  const entries = getVisibleFactDataEntries(data)
  if (entries.length === 0) return null

  return (
    <div className={`mt-2 rounded-md border border-gray-100 bg-gray-50 px-3 py-2 ${className}`.trim()}>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-400">Data</p>
      <dl className="space-y-1.5">
        {entries.map(({ key, value }) => (
          <div key={key} className="grid grid-cols-[7rem,1fr] gap-2 text-xs">
            <dt className="font-medium text-gray-500">{key}</dt>
            <dd className="break-words whitespace-pre-wrap text-gray-700">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
