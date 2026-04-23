"use client"

interface StaleSourceEvidence {
  filename: string
  reason: string
  chunk_count?: number | null
  last_seen_at?: string | null
}

interface StaleSourceGuidanceModalProps {
  evidence: StaleSourceEvidence[]
  onClose: () => void
}

function CauseSummary({ evidence }: { evidence: StaleSourceEvidence[] }) {
  const buckets = new Map<string, number>()

  for (const item of evidence) {
    const reason = item.reason.toLowerCase()
    let label = "Other stale-source issue"
    if (reason.includes("superseded")) label = "Superseded source still indexed"
    if (reason.includes("archived")) label = "Archived source still indexed"
    if (reason.includes("recent retrieval")) label = "Recent retrieval still points at old material"
    buckets.set(label, (buckets.get(label) ?? 0) + 1)
  }

  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {Array.from(buckets.entries()).map(([label, count]) => (
        <li key={label} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] px-4 py-3">
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--cl-muted)]">{label}</p>
          <p className="mt-2 font-display text-2xl text-[var(--cl-ink)]">{count}</p>
        </li>
      ))}
    </ul>
  )
}

export default function StaleSourceGuidanceModal({ evidence, onClose }: StaleSourceGuidanceModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Stale sources guidance"
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] shadow-[0_24px_80px_rgba(15,23,42,0.22)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--cl-line)] px-6 py-5">
          <div>
            <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Stale sources</p>
            <h2 className="mt-2 font-display text-2xl text-[var(--cl-ink)]">Why this is red, and how to fix it</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--cl-muted)]">
              The source ledger says some material is no longer current, but the vector index still contains chunks that can surface in retrieval.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--cl-line)] bg-white/80 px-3 py-2 text-sm text-[var(--cl-ink)] transition-colors hover:border-[var(--cl-accent)]/60 hover:bg-white"
            aria-label="Close stale sources guidance"
          >
            Close
          </button>
        </div>

        <div className="grid gap-6 overflow-y-auto p-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="space-y-4">
            <div className="rounded-3xl border border-[var(--cl-error)]/20 bg-[var(--cl-error)]/8 p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--cl-error)]">What is happening</p>
              <p className="mt-3 text-sm leading-6 text-[var(--cl-ink)]">
                These sources are flagged because their ledger status is superseded or archived, but at least one chunk is still present in Qdrant.
                That means retrieval may still surface older material until the stale chunks are cleaned up.
              </p>
            </div>

            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
              <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Cause summary</p>
              <div className="mt-4">
                <CauseSummary evidence={evidence} />
              </div>
            </div>

            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
              <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Evidence list</p>
              <ul className="mt-4 space-y-3">
                {evidence.map((item) => (
                  <li key={`${item.filename}-${item.last_seen_at ?? item.reason}`} className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-[var(--cl-ink)]">{item.filename}</p>
                        <p className="mt-1 text-sm leading-6 text-[var(--cl-muted)]">{item.reason}</p>
                      </div>
                      <div className="text-sm text-[var(--cl-muted)] sm:text-right">
                        <p>{item.chunk_count ?? "Unknown"} chunk{item.chunk_count === 1 ? "" : "s"}</p>
                        <p>{item.last_seen_at ? `Last seen ${item.last_seen_at}` : "Last seen unknown"}</p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <aside className="space-y-4">
            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
              <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">How to remediate</p>
              <ol className="mt-4 space-y-3 text-sm leading-6 text-[var(--cl-muted)]">
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  1. Open the source ledger entry for each filename and confirm whether it should stay active, be superseded, or be archived.
                </li>
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  2. If the record is already superseded or archived, re-ingest or delete the old indexed chunks so Qdrant stops returning stale material.
                </li>
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  3. If this was caused by a recent upload, wait for ingestion to finish and then refresh KB health.
                </li>
                <li className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface-2)] p-4">
                  4. Reopen this panel after the refresh. The stale count should drop to zero once the old chunks are gone.
                </li>
              </ol>
            </div>

            <div className="rounded-3xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5">
              <p className="font-mono-display text-[11px] uppercase tracking-[0.26em] text-[var(--cl-secondary)]">Helpful rule of thumb</p>
              <p className="mt-3 text-sm leading-6 text-[var(--cl-muted)]">
                Active sources are the only ones that should appear in current citations. Superseded or archived sources can stay on disk for audit history,
                but their old chunks need to be removed or replaced before the red warning can clear.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
