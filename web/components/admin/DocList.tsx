"use client"

import { useEffect, useState } from "react"
import { adminFetch } from "@/lib/admin-api"
import LifecycleBadge from "@/components/admin/LifecycleBadge"

interface Doc {
  doc_id?: string | null
  source_id?: string | null
  filename: string
  lifecycle?: "active" | "superseded" | "archived" | null
  chunk_count?: number | null
  uploaded_at?: string | null
  uploaded_by?: string | null
  superseded_by?: string | null
  linked_knowledge_object?: string | null
}

interface Props {
  refreshKey: number
  onDeleted?: () => void
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Unknown"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Unknown"
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed)
}

function getDocKey(doc: Doc): string {
  return doc.doc_id || doc.source_id || doc.filename
}

function normalizeDocs(payload: unknown): Doc[] {
  if (Array.isArray(payload)) return payload as Doc[]
  if (payload && typeof payload === "object" && Array.isArray((payload as { docs?: unknown }).docs)) {
    return (payload as { docs: Doc[] }).docs
  }
  return []
}

export default function DocList({ refreshKey, onDeleted }: Props) {
  const [docs, setDocs] = useState<Doc[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    adminFetch("/api/docs")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`docs:${response.status}`)
        }
        return response.json()
      })
      .then((payload) => {
        if (cancelled) return
        setDocs(normalizeDocs(payload))
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the document inventory.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshKey])

  async function handleDelete(doc: Doc) {
    const key = getDocKey(doc)
    const response = await adminFetch(`/api/docs/${encodeURIComponent(key)}`, { method: "DELETE" })
    if (!response.ok) return
    setDocs((current) =>
      current.map((item) =>
        getDocKey(item) === key
          ? { ...item, lifecycle: "archived", chunk_count: 0 }
          : item
      )
    )
    onDeleted?.()
  }

  return (
    <section className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-[0_12px_30px_rgba(31,41,55,0.06)]">
      <div className="flex flex-col gap-2 border-b border-[var(--cl-line)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Document inventory</p>
          <h3 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Ledger-backed sources</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
            Keep an eye on active, superseded, and archived files. Delete moves a document out of the active set without hiding history.
          </p>
        </div>
        <p className="text-sm text-[var(--cl-muted)]">
          {loading ? "Loading inventory…" : `${docs.length} records`}
        </p>
      </div>

      {error && (
        <div className="mt-4 rounded-2xl border border-[var(--cl-error)]/25 bg-[var(--cl-error)]/10 px-4 py-3 text-sm text-[var(--cl-error)]">
          {error}
        </div>
      )}

      {!loading && !error && docs.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-6 text-sm leading-6 text-[var(--cl-muted)]">
          No source documents uploaded yet.
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {docs.map((doc) => {
            const key = getDocKey(doc)
            const lifecycleLabel = doc.lifecycle ? undefined : "Unknown"
            return (
              <li
                key={key}
                className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] px-4 py-4 shadow-[0_8px_18px_rgba(31,41,55,0.04)] transition-colors hover:border-[var(--cl-accent)]/30"
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="truncate font-medium text-[var(--cl-ink)]">{doc.filename}</h4>
                      <LifecycleBadge lifecycle={doc.lifecycle ?? null} label={lifecycleLabel} />
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--cl-muted)]">
                      <span>
                        <span className="font-mono-display text-[var(--cl-ink)]">{doc.chunk_count ?? "Unknown"}</span> chunks
                      </span>
                      <span>Uploaded {formatDate(doc.uploaded_at)}</span>
                      {doc.uploaded_by && <span>By {doc.uploaded_by}</span>}
                      {doc.linked_knowledge_object && <span>Object {doc.linked_knowledge_object}</span>}
                    </div>
                    {doc.superseded_by && (
                      <p className="text-sm text-[var(--cl-muted)]">
                        Superseded by <span className="font-medium text-[var(--cl-ink)]">{doc.superseded_by}</span>
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    className="inline-flex min-h-11 items-center justify-center rounded-full border border-[var(--cl-error)]/30 bg-[var(--cl-error)]/10 px-4 text-sm font-medium text-[var(--cl-error)] transition-colors hover:border-[var(--cl-error)] hover:bg-[var(--cl-error)]/15 focus:outline-none focus:ring-2 focus:ring-[var(--cl-error)] focus:ring-offset-2 focus:ring-offset-[var(--cl-surface)]"
                    aria-label={`Delete document ${doc.filename}`}
                  >
                    Delete
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
